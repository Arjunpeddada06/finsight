import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import calculations, chat, documents, health, search
from app.config import get_settings
from app.database import init_db
from app.ratelimit import limiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("finsight")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await init_db()
        log.info("Database initialised")
    except Exception as exc:  # API should still start so /api/health can report the problem
        log.error("Database init failed: %s", exc)
    yield


settings = get_settings()
app = FastAPI(title="FinSight AI", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(health.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(calculations.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
