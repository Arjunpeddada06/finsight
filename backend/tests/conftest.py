import os
import tempfile
from pathlib import Path

# Must be set before the app imports its cached settings.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://finsight:change-me@localhost:5432/finsight")
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="finsight-test-")

import pytest
import httpx
from sqlalchemy import text

from app.database import engine, init_db
from app.main import app
from app.ratelimit import limiter
from app.rag.embeddings import set_embedder
from app.rag.llm import set_llm
from tests.stub_llm import ScriptedLLM
from tests.stub_embedder import HashEmbedder

limiter.enabled = False  # the suite makes many requests; test_rate_limit.py turns it back on explicitly

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_PDF = FIXTURES / "sample_report.pdf"


@pytest.fixture
async def client():
    """HTTP client against the real app and a real Postgres. Skips if the database is unreachable."""
    await engine.dispose()  # drop pooled connections that belong to a previous test's event loop
    try:
        await init_db()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except OSError as exc:  # connection refused / host unreachable only; real errors must fail the test
        await engine.dispose()
        pytest.skip(f"Postgres not available: {exc}")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c
    await engine.dispose()  # asyncpg pools are bound to the per-test event loop


@pytest.fixture(autouse=True)
def embedder():
    """Every test gets an offline test-double embedder; tests may swap it via set_embedder()."""
    stub = HashEmbedder()
    set_embedder(stub)
    yield stub
    set_embedder(None)


@pytest.fixture(autouse=True)
def llm():
    """Every test gets an offline scripted LLM; tests may swap it via set_llm()."""
    stub = ScriptedLLM()
    set_llm(stub)
    yield stub
    set_llm(None)
