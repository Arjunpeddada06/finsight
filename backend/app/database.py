from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create extension + tables. Replace with Alembic migrations once the schema settles."""
    from sqlalchemy import text

    import app.models  # noqa: F401  (register models)

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight migration for databases created by an earlier phase.
        await conn.execute(text("ALTER TABLE sources ADD COLUMN IF NOT EXISTS label integer"))
        # Full-text index for the keyword half of hybrid search (create_all does not add indexes to existing tables).
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_chunks_fts ON document_chunks USING gin (to_tsvector('english', content))"
        ))
