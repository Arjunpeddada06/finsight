import uuid
from typing import Literal

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    document_ids: list[uuid.UUID] | None = None
    top_k: int = Field(5, ge=1, le=20)
    kind: Literal["text", "table"] | None = None


class SearchHitOut(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    page_number: int
    section: str | None
    content: str
    kind: str
    similarity: float | None
    score: float
    matched_by: list[str]


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHitOut]


class ChunkOut(BaseModel):
    id: uuid.UUID
    page_number: int
    section: str | None
    kind: str
    token_count: int | None
    preview: str
    has_embedding: bool
