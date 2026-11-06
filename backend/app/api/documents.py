import logging
import os
import re
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.models import Document, DocumentChunk, DocumentStatus, FinancialTable
from app.rag.ingestion import process_document
from app.ratelimit import limiter
from app.schemas.search import ChunkOut
from app.schemas.documents import DocumentDetail, DocumentList, DocumentOut, TableSummary
from app.services.pdf_service import PDFError, validate_pdf

log = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

PDF_MAGIC = b"%PDF-"
CHUNK = 1024 * 1024


def safe_title(filename: str) -> str:
    """Display name only: the file on disk is always stored under a random UUID."""
    stem = Path(os.path.basename(filename)).stem
    return re.sub(r"[^\w\s().,&-]", "", stem).strip()[:200] or "document"


async def _get_or_404(session: AsyncSession, document_id: uuid.UUID) -> Document:
    doc = await session.get(Document, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    return doc


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def upload_document(
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> Document:
    settings = get_settings()
    original = os.path.basename(file.filename or "")
    if not original.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF files are supported.")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid4()
    dest = upload_dir / f"{doc_id}.pdf"
    max_bytes = settings.max_upload_mb * 1024 * 1024

    size, first = 0, True
    try:
        async with aiofiles.open(dest, "wb") as out:
            while chunk := await file.read(CHUNK):
                if first:
                    if not chunk.startswith(PDF_MAGIC):
                        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "The file is not a real PDF.")
                    first = False
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File exceeds the {settings.max_upload_mb} MB limit.")
                await out.write(chunk)
        if size == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "The file is empty.")
        try:
            validate_pdf(str(dest))
        except PDFError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except Exception:
        dest.unlink(missing_ok=True)
        raise

    doc = Document(id=doc_id, filename=original[:512], title=safe_title(original), file_path=str(dest))
    session.add(doc)
    await session.commit()
    background.add_task(process_document, doc.id)  # returns immediately; client polls status
    return doc


@router.get("", response_model=DocumentList)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> DocumentList:
    total = await session.scalar(select(func.count()).select_from(Document)) or 0
    rows = await session.scalars(
        select(Document).order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return DocumentList(items=[DocumentOut.model_validate(d) for d in rows], total=total, page=page, page_size=page_size)


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(document_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> DocumentDetail:
    doc = await _get_or_404(session, document_id)
    tables = await session.scalars(
        select(FinancialTable).where(FinancialTable.document_id == doc.id).order_by(FinancialTable.page_number)
    )
    chunk_count = await session.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    # Build from DocumentOut: validating the ORM object directly would lazy-load doc.tables outside async context.
    return DocumentDetail(
        **DocumentOut.model_validate(doc).model_dump(),
        tables=[TableSummary.model_validate(t) for t in tables],
        chunk_count=chunk_count or 0,
    )


@router.get("/{document_id}/chunks", response_model=list[ChunkOut])
async def list_chunks(
    document_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[ChunkOut]:
    """Inspect how a document was chunked (page, section, size, whether a vector exists)."""
    await _get_or_404(session, document_id)
    rows = await session.scalars(
        select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index).offset((page - 1) * page_size).limit(page_size)
    )
    return [
        ChunkOut(id=c.id, page_number=c.page_number, section=c.section, kind=(c.meta or {}).get("kind", "text"),
                 token_count=c.token_count, preview=c.content[:200], has_embedding=c.embedding is not None)
        for c in rows
    ]


@router.get("/{document_id}/file")
async def get_document_file(document_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> FileResponse:
    """Serves the original PDF so citations can open it at a page (#page=N)."""
    doc = await _get_or_404(session, document_id)
    if not Path(doc.file_path).exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The original file is no longer available.")
    return FileResponse(doc.file_path, media_type="application/pdf", filename=doc.filename,
                        content_disposition_type="inline")


@router.post("/{document_id}/process", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def reprocess_document(
    document_id: uuid.UUID, background: BackgroundTasks, session: AsyncSession = Depends(get_session)
) -> Document:
    doc = await _get_or_404(session, document_id)
    if doc.status in (DocumentStatus.processing, DocumentStatus.extracting, DocumentStatus.embedding):
        raise HTTPException(status.HTTP_409_CONFLICT, "This document is already being processed.")
    doc.status, doc.error = DocumentStatus.uploaded, None
    await session.commit()
    background.add_task(process_document, doc.id)
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> None:
    doc = await _get_or_404(session, document_id)
    path = Path(doc.file_path)
    await session.delete(doc)  # cascades to pages, chunks, tables, metrics
    await session.commit()
    path.unlink(missing_ok=True)
