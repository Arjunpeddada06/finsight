
"""Hybrid retrieval using pgvector and PostgreSQL full-text search."""

import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embeddings import Embedder, get_embedder
from app.rag.reranker import reciprocal_rank_fusion


_STOP = {
    "the", "a", "an", "of", "and", "or", "in", "on", "to",
    "for", "is", "was", "what", "were", "how", "did", "by",
    "with", "at", "as",
}

_COLS = """
c.id,
c.document_id,
d.title,
d.filename,
c.page_number,
c.section,
c.content,
c.metadata->>'kind' AS kind,
1 - (c.embedding <=> CAST(:qv AS vector)) AS sim
"""


@dataclass
class SearchHit:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    page_number: int
    section: str | None
    content: str
    kind: str
    similarity: float | None
    score: float
    matched_by: list[str] = field(default_factory=list)


def keyword_tsquery(query: str) -> str | None:
    """Convert query terms into a PostgreSQL tsquery."""

    terms = [
        term
        for term in re.findall(r"[A-Za-z0-9]+", query.lower())
        if len(term) > 1 and term not in _STOP
    ]

    return " | ".join(dict.fromkeys(terms)) or None


def _vec_literal(vector: list[float]) -> str:
    return "[" + ",".join(
        f"{value:.7f}" for value in vector
    ) + "]"


def _filters(
    document_ids: list[uuid.UUID] | None,
    kind: str | None,
    params: dict,
) -> str:
    sql = ""

    if document_ids:
        sql += " AND c.document_id = ANY(:doc_ids)"
        params["doc_ids"] = document_ids

    if kind:
        sql += " AND c.metadata->>'kind' = :kind"
        params["kind"] = kind

    return sql


async def search_chunks(
    session: AsyncSession,
    queries: str | list[str],
    *,
    document_ids: list[uuid.UUID] | None = None,
    top_k: int = 5,
    kind: str | None = None,
    embedder: Embedder | None = None,
) -> list[SearchHit]:
    """Perform hybrid vector and keyword retrieval."""

    if isinstance(queries, str):
        qs = [queries.strip()] if queries.strip() else []
    else:
        qs = [
            query.strip()
            for query in queries
            if query and query.strip()
        ]

    if not qs:
        return []

    embedder = embedder or get_embedder()

    # Generate query embeddings.
    vectors = await embedder.embed(qs)

    pool = max(top_k * 4, 20)

    rows: dict[uuid.UUID, dict] = {}
    rankings: list[list[uuid.UUID]] = []
    origin: dict[uuid.UUID, set[str]] = {}

    for query, vector in zip(qs, vectors):

        params = {
            "qv": _vec_literal(vector),
            "n": pool,
        }

        filters = _filters(document_ids, kind, params)

        base = (
            "SELECT "
            + _COLS
            + " FROM document_chunks c "
            + "JOIN documents d ON d.id = c.document_id"
        )

        # Vector similarity search.
        vector_sql = (
            f"{base} "
            f"WHERE c.embedding IS NOT NULL{filters} "
            "ORDER BY c.embedding <=> CAST(:qv AS vector) "
            "LIMIT :n"
        )

        vector_result = await session.execute(
            text(vector_sql),
            params,
        )

        vector_rows = vector_result.mappings().all()

        rankings.append([
            row["id"] for row in vector_rows
        ])

        for row in vector_rows:
            rows.setdefault(row["id"], dict(row))
            origin.setdefault(row["id"], set()).add("vector")

        # PostgreSQL full-text keyword search.
        tsquery = keyword_tsquery(query)

        if tsquery:
            params2 = dict(params)
            params2["tsq"] = tsquery

            keyword_sql = (
                f"{base}, to_tsquery('english', :tsq) AS tq "
                "WHERE to_tsvector('english', c.content) @@ tq "
                f"{filters} "
                "ORDER BY ts_rank_cd("
                "to_tsvector('english', c.content), tq"
                ") DESC "
                "LIMIT :n"
            )

            keyword_result = await session.execute(
                text(keyword_sql),
                params2,
            )

            keyword_rows = keyword_result.mappings().all()

            rankings.append([
                row["id"] for row in keyword_rows
            ])

            for row in keyword_rows:
                rows.setdefault(row["id"], dict(row))
                origin.setdefault(row["id"], set()).add("keyword")

    # Reciprocal Rank Fusion.
    fused = reciprocal_rank_fusion(rankings)

    top = sorted(
        fused,
        key=fused.get,
        reverse=True,
    )[:top_k]

    results = []

    for chunk_id in top:
        row = rows[chunk_id]

        similarity = row["sim"]

        results.append(
            SearchHit(
                chunk_id=chunk_id,
                document_id=row["document_id"],
                document_name=(
                    row["title"] or row["filename"]
                ),
                page_number=row["page_number"],
                section=row["section"],
                content=row["content"],
                kind=row["kind"] or "text",
                similarity=(
                    None
                    if similarity is None
                    else round(float(similarity), 4)
                ),
                score=round(fused[chunk_id], 5),
                matched_by=sorted(origin[chunk_id]),
            )
        )

    return results
