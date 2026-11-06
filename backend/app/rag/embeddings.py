
"""Gemini embedding client for FinSight RAG."""

import logging
import math
from typing import Protocol

from google import genai
from google.genai import types

from app.config import Settings, get_settings

log = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """User-readable embedding failure."""


class Embedder(Protocol):
    async def embed(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_QUERY",
    ) -> list[list[float]]: ...


class GeminiEmbedder:
    def __init__(
        self,
        settings: Settings | None = None,
        client=None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def _get_client(self):
        if not self.settings.gemini_api_key:
            raise EmbeddingError(
                "GEMINI_API_KEY is not configured. "
                "Add your Gemini API key to .env and restart the backend."
            )

        if self._client is None:
            self._client = genai.Client(
                api_key=self.settings.gemini_api_key
            )

        return self._client

    async def embed(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_QUERY",
    ) -> list[list[float]]:

        if not texts:
            return []

        client = self._get_client()
        size = max(1, self.settings.embedding_batch_size)

        vectors = []

        for i in range(0, len(texts), size):
            batch = texts[i:i + size]

            try:
                response = await client.aio.models.embed_content(
                    model=self.settings.embedding_model,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=self.settings.embedding_dimensions,
                    ),
                )

            except Exception as exc:
                log.exception("Gemini embedding request failed")
                raise EmbeddingError(
                    f"Gemini embedding request failed: {str(exc)[:250]}"
                ) from exc

            if not response.embeddings:
                raise EmbeddingError(
                    "Gemini returned no embeddings."
                )

            if len(response.embeddings) != len(batch):
                raise EmbeddingError(
                    "Gemini returned a different number of vectors than requested."
                )

            for item in response.embeddings:
                vector = list(item.values)

                if len(vector) != self.settings.embedding_dimensions:
                    raise EmbeddingError(
                        f"Gemini returned {len(vector)} dimensions, "
                        f"but the database expects "
                        f"{self.settings.embedding_dimensions}."
                    )

                # gemini-embedding-001 requires manual normalization
                # when output_dimensionality is below 3072.
                norm = math.sqrt(sum(x * x for x in vector))

                if norm == 0:
                    raise EmbeddingError(
                        "Gemini returned an invalid zero-length vector."
                    )

                vector = [x / norm for x in vector]
                vectors.append(vector)

        return vectors


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder

    if _embedder is None:
        _embedder = GeminiEmbedder()

    return _embedder


def set_embedder(embedder: Embedder | None) -> None:
    """Replace the process-wide embedder (used by tests)."""
    global _embedder
    _embedder = embedder
