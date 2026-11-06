import uuid
from pathlib import Path

from app.rag.embeddings import set_embedder
from app.rag.retriever import keyword_tsquery
from tests.conftest import SAMPLE_PDF
from tests.stub_embedder import FailingEmbedder


async def _upload(client):
    r = await client.post("/api/documents/upload", files={"file": ("Meridian Report.pdf", SAMPLE_PDF.read_bytes(), "application/pdf")})
    assert r.status_code == 201
    return r.json()["id"]


def test_keyword_query_is_sanitised():
    assert keyword_tsquery("What was Revenue growth in FY2025?") == "revenue | growth | fy2025"
    assert keyword_tsquery("'; DROP TABLE documents; --") == "drop | table | documents"
    assert keyword_tsquery("the of and") is None


async def test_ingestion_creates_embedded_chunks(client, embedder):
    doc_id = await _upload(client)
    d = (await client.get(f"/api/documents/{doc_id}")).json()
    assert d["status"] == "ready" and d["chunk_count"] == 15
    chunks = (await client.get(f"/api/documents/{doc_id}/chunks")).json()
    assert len(chunks) == 15 and all(c["has_embedding"] for c in chunks)
    assert {c["kind"] for c in chunks} == {"text", "table"}
    await client.delete(f"/api/documents/{doc_id}")


async def test_reprocessing_reuses_stored_vectors(client, embedder):
    doc_id = await _upload(client)
    embedded_first = embedder.texts_embedded
    assert embedded_first == 15
    await client.post(f"/api/documents/{doc_id}/process")
    assert embedder.texts_embedded == embedded_first  # nothing re-embedded
    assert (await client.get(f"/api/documents/{doc_id}")).json()["chunk_count"] == 15  # replaced, not doubled
    await client.delete(f"/api/documents/{doc_id}")


async def test_embedding_failure_keeps_extracted_data_and_explains(client):
    set_embedder(FailingEmbedder())
    doc_id = await _upload(client)
    d = (await client.get(f"/api/documents/{doc_id}")).json()
    assert d["status"] == "failed" and "embedding failed" in d["error"] and "OPENAI_API_KEY" in d["error"]
    assert d["page_count"] == 8 and len(d["tables"]) == 5 and d["chunk_count"] == 0
    await client.delete(f"/api/documents/{doc_id}")


async def test_search_finds_the_right_page(client):
    doc_id = await _upload(client)
    r = await client.post("/api/search", json={"query": "What was the debt-to-equity ratio?", "document_ids": [doc_id], "top_k": 3})
    assert r.status_code == 200
    hits = r.json()["hits"]
    assert hits[0]["page_number"] == 5 and "debt-to-equity" in hits[0]["content"].lower()
    assert hits[0]["document_name"] == "Meridian Report" and 0 < hits[0]["similarity"] <= 1
    assert "keyword" in hits[0]["matched_by"] and "vector" in hits[0]["matched_by"]

    r = await client.post("/api/search", json={"query": "Which risks are mentioned? commodity currency interest", "document_ids": [doc_id]})
    assert r.json()["hits"][0]["page_number"] == 7
    await client.delete(f"/api/documents/{doc_id}")


async def test_search_kind_filter_and_table_hit(client):
    doc_id = await _upload(client)
    r = await client.post("/api/search", json={"query": "revenue from operations FY2025 FY2024 FY2023", "document_ids": [doc_id], "kind": "table", "top_k": 5})
    hits = r.json()["hits"]
    assert hits and all(h["kind"] == "table" for h in hits)
    assert hits[0]["page_number"] in (2, 4)  # highlights table or income statement
    await client.delete(f"/api/documents/{doc_id}")


async def test_search_respects_document_filter_and_multi_query(client):
    a, b = await _upload(client), await _upload(client)
    r = await client.post("/api/search", json={"query": "total debt borrowings", "document_ids": [a], "top_k": 10})
    assert {h["document_id"] for h in r.json()["hits"]} == {a}
    r = await client.post("/api/search", json={"query": "total debt borrowings", "document_ids": [a, b], "top_k": 10})
    assert {h["document_id"] for h in r.json()["hits"]} == {a, b}
    for d in (a, b):
        await client.delete(f"/api/documents/{d}")


async def test_search_validation_and_errors(client):
    assert (await client.post("/api/search", json={"query": "x"})).status_code == 422          # too short
    assert (await client.post("/api/search", json={"query": "revenue", "top_k": 99})).status_code == 422
    assert (await client.post("/api/search", json={"query": "revenue", "document_ids": ["nope"]})).status_code == 422
    set_embedder(FailingEmbedder())
    r = await client.post("/api/search", json={"query": "revenue growth"})
    assert r.status_code == 503 and "API key" in r.json()["detail"]


async def test_search_with_no_matching_documents_returns_empty(client):
    r = await client.post("/api/search", json={"query": "revenue", "document_ids": [str(uuid.uuid4())]})
    assert r.status_code == 200 and r.json()["hits"] == []
