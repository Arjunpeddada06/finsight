
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.financial_agent import answer_question
from app.config import get_settings
from app.database import get_session
from app.models import (
    Conversation,
    Document,
    DocumentChunk,
    Message,
    Source,
)
from app.rag.embeddings import EmbeddingError
from app.rag.llm import LLMError
from app.ratelimit import limiter
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationOut,
    MessageOut,
    SourceOut,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:

    settings = get_settings()

    conversation: Conversation | None = None
    history: list[tuple[str, str]] = []

    # Load existing conversation and chat history.
    if body.conversation_id:
        conversation = await session.get(
            Conversation,
            body.conversation_id,
        )

        if conversation is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Conversation not found.",
            )

        recent = await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(
                Message.created_at.desc(),
                Message.role.asc(),
            )
            .limit(settings.history_messages)
        )

        history = [
            (message.role, message.content)
            for message in reversed(list(recent))
        ]

    # Generate the answer using the financial RAG agent.
    try:
        answer = await answer_question(
            session,
            body.message,
            history=history,
            document_ids=body.document_ids,
        )

    except (EmbeddingError, LLMError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            str(exc),
        ) from exc

    try:
        # Persist only after a successful answer.
        if conversation is None:
            conversation = Conversation(
                title=body.message.strip()[:60],
            )

            session.add(conversation)
            await session.flush()

        # Save user message.
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=body.message,
        )

        session.add(user_message)

        # Save assistant response.
        reply = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=answer.text,
        )

        session.add(reply)

        await session.flush()

        # Collect referenced document IDs.
        document_ids = {
            source.document_id
            for source in answer.sources
        }

        # Lock documents while saving citations.
        # This prevents ingestion from replacing their chunks
        # during citation persistence.
        if document_ids:
            await session.execute(
                select(Document.id)
                .where(Document.id.in_(document_ids))
                .order_by(Document.id)
                .with_for_update(read=True)
            )

        # Collect retrieved chunk IDs.
        chunk_ids = {
            source.chunk_id
            for source in answer.sources
            if source.chunk_id is not None
        }

        existing_chunk_ids = set()

        # Verify that referenced chunks still exist.
        if chunk_ids:
            result = await session.execute(
                select(DocumentChunk.id).where(
                    DocumentChunk.id.in_(chunk_ids)
                )
            )

            existing_chunk_ids = set(
                result.scalars().all()
            )

        # Save citations safely.
        # Missing chunks retain their document/page citation,
        # but their chunk_id is stored as NULL.
        for source in answer.sources:

            safe_chunk_id = (
                source.chunk_id
                if source.chunk_id in existing_chunk_ids
                else None
            )

            session.add(
                Source(
                    message_id=reply.id,
                    document_id=source.document_id,
                    page_number=source.page_number,
                    chunk_id=safe_chunk_id,
                    relevance_score=source.score,
                    label=source.label,
                )
            )

        # Commit the complete conversation turn.
        await session.commit()

    except Exception:
        await session.rollback()

        log.exception(
            "Failed to save chat response and citations"
        )

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "The answer was generated, but saving the conversation failed. Please try again.",
        )

    return ChatResponse(
        conversation_id=conversation.id,
        message_id=reply.id,
        answer=answer.text,
        refused=answer.refused,
        rewritten_question=answer.rewritten_question,
        tool_used=answer.tool_used,
        sources=[
            SourceOut(**source.__dict__)
            for source in answer.sources
        ],
    )


@router.get(
    "/history",
    response_model=list[ConversationOut],
)
async def chat_history(
    session: AsyncSession = Depends(get_session),
) -> list[ConversationOut]:

    counts = (
        select(
            Message.conversation_id,
            func.count().label("n"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )

    rows = await session.execute(
        select(
            Conversation,
            func.coalesce(counts.c.n, 0),
        )
        .outerjoin(
            counts,
            counts.c.conversation_id == Conversation.id,
        )
        .order_by(Conversation.created_at.desc())
        .limit(200)
    )

    return [
        ConversationOut(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            message_count=count,
        )
        for conversation, count in rows
    ]


@router.delete(
    "/history",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_history(
    session: AsyncSession = Depends(get_session),
) -> Response:

    await session.execute(
        delete(Conversation)
    )

    await session.commit()

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
)
async def get_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ConversationDetail:

    conversation = await session.get(
        Conversation,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Conversation not found.",
        )

    messages = list(
        await session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation.id
            )
            .order_by(
                Message.created_at,
                Message.role.desc(),
            )
        )
    )

    message_ids = [
        message.id
        for message in messages
    ]

    by_message: dict[uuid.UUID, list[SourceOut]] = {}

    if message_ids:
        src_rows = await session.execute(
            select(
                Source,
                Document.title,
                Document.filename,
                DocumentChunk.content,
                DocumentChunk.section,
            )
            .join(
                Document,
                Document.id == Source.document_id,
            )
            .outerjoin(
                DocumentChunk,
                DocumentChunk.id == Source.chunk_id,
            )
            .where(
                Source.message_id.in_(message_ids)
            )
            .order_by(Source.label)
        )

        for source, title, filename, content, section in src_rows:

            by_message.setdefault(
                source.message_id,
                [],
            ).append(
                SourceOut(
                    label=source.label or 0,
                    document_id=source.document_id,
                    document_name=title or filename,
                    page_number=source.page_number,
                    section=section,
                    chunk_id=source.chunk_id,
                    score=source.relevance_score,
                    snippet=content[:240] if content else None,
                )
            )

    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        messages=[
            MessageOut(
                id=message.id,
                role=message.role,
                content=message.content,
                created_at=message.created_at,
                sources=by_message.get(message.id, []),
            )
            for message in messages
        ],
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:

    conversation = await session.get(
        Conversation,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Conversation not found.",
        )

    await session.delete(conversation)
    await session.commit()

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )
