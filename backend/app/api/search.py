import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.rag.embeddings import EmbeddingError
from app.rag.retriever import search_chunks
from app.ratelimit import limiter
from app.schemas.search import SearchHitOut, SearchRequest, SearchResponse

log = logging.getLogger(__name__)
router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
@limiter.limit("60/minute")
async def search(request: Request, body: SearchRequest, session: AsyncSession = Depends(get_session)) -> SearchResponse:
    """search_financial_documents: hybrid (vector + keyword) retrieval with page-level citations."""
    try:
        hits = await search_chunks(session, body.query, document_ids=body.document_ids, top_k=body.top_k, kind=body.kind)
    except EmbeddingError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return SearchResponse(query=body.query, hits=[SearchHitOut(**h.__dict__) for h in hits])
