import os
from pathlib import Path

from app.config import get_settings
from tests.conftest import SAMPLE_PDF


async def _upload(client, name="Meridian Report.pdf", data=None, ctype="application/pdf"):
    data = SAMPLE_PDF.read_bytes() if data is None else data
    return await client.post("/api/documents/upload", files={"file": (name, data, ctype)})


async def test_full_document_lifecycle(client):
    r = await _upload(client)
    assert r.status_code == 201
    doc_id = r.json()["id"]
    assert os.path.exists(Path(get_settings().upload_dir) / f"{doc_id}.pdf")  # stored under UUID, not user filename

    d = (await client.get(f"/api/documents/{doc_id}")).json()  # background task already finished
    assert d["status"] == "ready"
    assert d["page_count"] == 8
    assert d["company"] == "Meridian Industries Limited" and d["fiscal_year"] == "FY2025"
    assert sorted(t["page_number"] for t in d["tables"]) == [2, 3, 4, 5, 6]

    listing = (await client.get("/api/documents?page=1&page_size=5")).json()
    assert listing["total"] >= 1 and any(i["id"] == doc_id for i in listing["items"])

    f = await client.get(f"/api/documents/{doc_id}/file")
    assert f.status_code == 200 and f.headers["content-type"] == "application/pdf" and f.content[:5] == b"%PDF-"

    again = await client.post(f"/api/documents/{doc_id}/process")
    assert again.status_code == 202
    d2 = (await client.get(f"/api/documents/{doc_id}")).json()
    assert d2["status"] == "ready" and len(d2["tables"]) == 5  # replaced, not duplicated

    assert (await client.delete(f"/api/documents/{doc_id}")).status_code == 204
    assert (await client.get(f"/api/documents/{doc_id}")).status_code == 404
    assert not os.path.exists(Path(get_settings().upload_dir) / f"{doc_id}.pdf")


async def test_rejects_non_pdf_extension(client):
    r = await _upload(client, "notes.txt", b"hello", "text/plain")
    assert r.status_code == 415


async def test_rejects_fake_pdf_by_magic_bytes(client):
    r = await _upload(client, "fake.pdf", b"MZ not a pdf at all")
    assert r.status_code == 415


async def test_rejects_corrupt_pdf(client):
    r = await _upload(client, "corrupt.pdf", b"%PDF-1.4\ngarbage garbage")
    assert r.status_code == 422


async def test_rejects_empty_file(client):
    assert (await _upload(client, "empty.pdf", b"")).status_code == 400


async def test_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    assert (await _upload(client)).status_code == 413
    leftovers = [p for p in Path(get_settings().upload_dir).glob("*.pdf")]
    assert all(p.stat().st_size > 0 for p in leftovers)  # rejected upload leaves no partial file


async def test_unknown_document_is_404(client):
    assert (await client.get("/api/documents/00000000-0000-0000-0000-000000000000")).status_code == 404
