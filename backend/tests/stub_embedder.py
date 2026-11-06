"""TEST DOUBLES ONLY. Production always uses OpenAIEmbedder (rag/embeddings.py).

HashEmbedder turns words into a hashed bag-of-words vector, so texts that share words are similar. That is enough
to test the plumbing (storage, SQL, fusion, filters) offline, but it says nothing about real embedding quality.
"""
import hashlib
import math
import re

from app.rag.embeddings import EmbeddingError


class HashEmbedder:
    def __init__(self, dim: int = 1536) -> None:
        self.dim, self.calls, self.texts_embedded = dim, 0, 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.texts_embedded += len(texts)
        return [self._vec(t) for t in texts]

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in re.findall(r"[a-z0-9]+", text.lower()):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]


class FailingEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("The embedding API rejected the API key. Check OPENAI_API_KEY.")
