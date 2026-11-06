import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)
    conversation_id: uuid.UUID | None = None
    document_ids: list[uuid.UUID] | None = None


class SourceOut(BaseModel):
    label: int
    document_id: uuid.UUID
    document_name: str
    page_number: int
    section: str | None = None
    chunk_id: uuid.UUID | None = None
    score: float | None = None
    snippet: str | None = None


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    answer: str
    sources: list[SourceOut]
    refused: bool
    rewritten_question: str | None = None
    tool_used: str | None = None


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    sources: list[SourceOut] = []


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    message_count: int


class ConversationDetail(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    messages: list[MessageOut]
