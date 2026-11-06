from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness plus database/pgvector status. Never raises: reports degraded instead."""
    db_ok, vector_ok = False, False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_ok = True
            row = await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname='vector'"))
            vector_ok = row.first() is not None
    except Exception:
        pass
    return {"status": "ok" if db_ok and vector_ok else "degraded", "database": db_ok, "pgvector": vector_ok}
