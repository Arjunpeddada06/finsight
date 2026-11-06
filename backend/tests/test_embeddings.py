import openai
import pytest

from app.config import Settings
from app.rag.embeddings import EmbeddingError, OpenAIEmbedder


class _Item:
    def __init__(self, index, n): self.index, self.embedding = index, [0.1] * n


class _Resp:
    def __init__(self, data): self.data = data


class _FakeClient:
    """Mimics the openai client's surface only to test batching/validation logic."""
    def __init__(self, dim=8, error=None):
        self.dim, self.error, self.batches = dim, error, []
        self.embeddings = self

    async def create(self, model, input, **kw):
        self.batches.append((model, list(input), kw))
        if self.error: raise self.error
        return _Resp([_Item(i, self.dim) for i in reversed(range(len(input)))])  # out of order on purpose


def _settings(**kw):
    base = dict(openai_api_key="k", embedding_model="text-embedding-3-small", embedding_dimensions=8, embedding_batch_size=3)
    return Settings(_env_file=None, **{**base, **kw})


async def test_missing_model_and_key_give_readable_errors():
    with pytest.raises(EmbeddingError, match="EMBEDDING_MODEL"):
        await OpenAIEmbedder(_settings(embedding_model="")).embed(["x"])
    with pytest.raises(EmbeddingError, match="OPENAI_API_KEY"):
        await OpenAIEmbedder(_settings(openai_api_key="")).embed(["x"])


async def test_batches_are_split_ordered_and_dimensions_requested():
    client = _FakeClient()
    out = await OpenAIEmbedder(_settings(), client).embed([str(i) for i in range(7)])
    assert len(out) == 7
    assert [len(b[1]) for b in client.batches] == [3, 3, 1]
    assert client.batches[0][2] == {"dimensions": 8}  # text-embedding-3 models accept a dimensions argument


async def test_dimensions_not_sent_for_other_models():
    client = _FakeClient()
    await OpenAIEmbedder(_settings(embedding_model="nomic-embed-text"), client).embed(["a"])
    assert client.batches[0][2] == {}


async def test_dimension_mismatch_is_explained():
    with pytest.raises(EmbeddingError, match="EMBEDDING_DIMENSIONS"):
        await OpenAIEmbedder(_settings(), _FakeClient(dim=4)).embed(["a"])


async def test_api_errors_are_translated():
    import httpx
    req = httpx.Request("POST", "http://x")
    err = openai.AuthenticationError("bad", response=httpx.Response(401, request=req), body=None)
    with pytest.raises(EmbeddingError, match="rejected the API key"):
        await OpenAIEmbedder(_settings(), _FakeClient(error=err)).embed(["a"])
    conn = openai.APIConnectionError(request=req)
    with pytest.raises(EmbeddingError, match="Could not reach"):
        await OpenAIEmbedder(_settings(), _FakeClient(error=conn)).embed(["a"])


async def test_empty_input_makes_no_call():
    client = _FakeClient()
    assert await OpenAIEmbedder(_settings(), client).embed([]) == []
    assert client.batches == []
