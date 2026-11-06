import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import DocumentStatus


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    filename: str
    title: str | None
    company: str | None
    report_type: str | None
    fiscal_year: str | None
    page_count: int | None
    status: DocumentStatus
    error: str | None
    created_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    page_size: int


class TableSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    page_number: int
    table_type: str | None
    title: str | None
    markdown: str | None


class DocumentDetail(DocumentOut):
    tables: list[TableSummary] = []
    chunk_count: int = 0
