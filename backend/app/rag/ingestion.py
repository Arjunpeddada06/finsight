
"""Document ingestion pipeline. Runs in the background so uploads return immediately.

Stages: processing -> extracting -> embedding -> ready.
Any failure stores a readable error and sets 'failed'.
"""

import asyncio
import logging
import uuid

from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import (
    Document,
    DocumentChunk,
    DocumentPage,
    DocumentStatus,
    FinancialTable,
)
from app.rag.chunking import Chunk, build_chunks
from app.rag.embeddings import EmbeddingError, get_embedder
from app.services.pdf_service import PDFError, extract_pages, guess_metadata
from app.services.table_service import extract_tables

log = logging.getLogger(__name__)


async def _set_status(
    session,
    doc: Document,
    status: DocumentStatus,
    error: str | None = None,
) -> None:
    doc.status = status
    doc.error = error
    await session.commit()


async def _embed_with_reuse(
    session,
    chunks: list[Chunk],
) -> list[list[float]]:
    """Reuse stored embeddings for identical chunk text."""

    contents = list({chunk.content for chunk in chunks})
    known: dict[str, list[float]] = {}

    if contents:
        rows = await session.execute(
            select(
                DocumentChunk.content,
                DocumentChunk.embedding,
            ).where(
                DocumentChunk.content.in_(contents),
                DocumentChunk.embedding.isnot(None),
            )
        )

        known = {
            content: [float(value) for value in embedding]
            for content, embedding in rows
        }

    missing = [content for content in contents if content not in known]

    if missing:
        embeddings = await get_embedder().embed(
            missing,
            task_type="RETRIEVAL_DOCUMENT",
        )

        known.update(zip(missing, embeddings))

        log.info(
            "Embedded %d new texts, reused %d",
            len(missing),
            len(contents) - len(missing),
        )

    return [known[chunk.content] for chunk in chunks]


async def process_document(document_id: uuid.UUID) -> None:
    async with SessionLocal() as session:
        doc = await session.get(Document, document_id)

        if doc is None:
            return

        try:
            await _set_status(
                session,
                doc,
                DocumentStatus.processing,
            )

            await _set_status(
                session,
                doc,
                DocumentStatus.extracting,
            )

            # Run blocking PDF operations outside the event loop.
            pages = await asyncio.to_thread(
                extract_pages,
                doc.file_path,
            )

            tables = await asyncio.to_thread(
                extract_tables,
                doc.file_path,
                {page.page_number: page.text for page in pages},
            )

            # Replace extracted pages and tables.
            await session.execute(
                delete(DocumentPage).where(
                    DocumentPage.document_id == doc.id
                )
            )

            await session.execute(
                delete(FinancialTable).where(
                    FinancialTable.document_id == doc.id
                )
            )

            session.add_all(
                DocumentPage(
                    document_id=doc.id,
                    page_number=page.page_number,
                    text=page.text,
                )
                for page in pages
            )

            session.add_all(
                FinancialTable(
                    document_id=doc.id,
                    page_number=table.page_number,
                    table_type=table.table_type,
                    title=table.title,
                    data={
                        "columns": table.columns,
                        "rows": table.rows,
                    },
                    markdown=table.markdown,
                )
                for table in tables
            )

            metadata = guess_metadata(pages)

            doc.page_count = len(pages)
            doc.company = doc.company or metadata["company"]
            doc.fiscal_year = doc.fiscal_year or metadata["fiscal_year"]
            doc.report_type = doc.report_type or metadata["report_type"]

            await session.commit()

            await _set_status(
                session,
                doc,
                DocumentStatus.embedding,
            )

            chunks = build_chunks(pages, tables)
            vectors = await _embed_with_reuse(session, chunks)

            # Lock the document before replacing its chunks.
            # Chat citation persistence takes a shared lock on this row.
            await session.execute(
                select(Document.id)
                .where(Document.id == doc.id)
                .with_for_update()
            )

            # Replace old chunks only after all new embeddings exist.
            await session.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.document_id == doc.id
                )
            )

            session.add_all(
                DocumentChunk(
                    document_id=doc.id,
                    page_number=chunk.page_number,
                    section=chunk.section,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    embedding=vector,
                    meta=chunk.meta,
                )
                for chunk, vector in zip(chunks, vectors)
            )

            await session.commit()

            await _set_status(
                session,
                doc,
                DocumentStatus.ready,
            )

            log.info(
                "Document %s ready: %d pages, %d tables, %d chunks",
                doc.id,
                len(pages),
                len(tables),
                len(chunks),
            )

        except EmbeddingError as exc:
            await session.rollback()

            await _set_status(
                session,
                doc,
                DocumentStatus.failed,
                f"Text was extracted, but embedding failed: {exc}",
            )

        except PDFError as exc:
            await session.rollback()

            await _set_status(
                session,
                doc,
                DocumentStatus.failed,
                str(exc),
            )

        except Exception:
            log.exception(
                "Ingestion failed for %s",
                document_id,
            )

            await session.rollback()

            await _set_status(
                session,
                doc,
                DocumentStatus.failed,
                "Processing failed unexpectedly. Try uploading again.",
            )
