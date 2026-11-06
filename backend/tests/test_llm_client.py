import httpx
import openai
import pytest

from app.config import Settings
from app.rag.llm import LLMError, OpenAILLM

REQ = httpx.Request("POST", "http://x")


class _Msg:
    def __init__(self, c): self.message = type("M", (), {"content": c})()


class _FakeClient:
    """Mimics only the openai client's surface to test our retry and error translation."""
    def __init__(self, replies):
        self.replies, self.kwargs = list(replies), []
        self.chat = type("C", (), {"completions": self})()

    async def create(self, **kw):
        self.kwargs.append(kw)
        r = self.replies.pop(0)
        if isinstance(r, Exception): raise r
        return type("R", (), {"choices": [_Msg(r)]})()


def _s(**kw):
    return Settings(_env_file=None, **{**dict(openai_api_key="k", llm_model="m"), **kw})


async def test_missing_config_is_explained():
    with pytest.raises(LLMError, match="LLM_MODEL"):
        await OpenAILLM(_s(llm_model="")).complete([{"role": "user", "content": "x"}])
    with pytest.raises(LLMError, match="OPENAI_API_KEY"):
        await OpenAILLM(_s(openai_api_key="")).complete([{"role": "user", "content": "x"}])


async def test_returns_trimmed_text_and_sends_temperature_zero():
    c = _FakeClient(["  hello  "])
    assert await OpenAILLM(_s(), c).complete([{"role": "user", "content": "x"}]) == "hello"
    assert c.kwargs[0]["temperature"] == 0.0 and c.kwargs[0]["model"] == "m"


async def test_retries_without_temperature_for_models_that_reject_it():
    bad = openai.BadRequestError("Unsupported value: 'temperature' does not support 0", response=httpx.Response(400, request=REQ), body=None)
    c = _FakeClient([bad, "ok"])
    assert await OpenAILLM(_s(), c).complete([{"role": "user", "content": "x"}]) == "ok"
    assert "temperature" in c.kwargs[0] and "temperature" not in c.kwargs[1]


async def test_other_bad_requests_are_not_retried_and_are_explained():
    bad = openai.BadRequestError("context length exceeded", response=httpx.Response(400, request=REQ), body=None)
    c = _FakeClient([bad])
    with pytest.raises(LLMError, match="context length"):
        await OpenAILLM(_s(), c).complete([{"role": "user", "content": "x"}])
    assert len(c.kwargs) == 1


@pytest.mark.parametrize("exc,msg", [
    (openai.AuthenticationError("bad", response=httpx.Response(401, request=REQ), body=None), "rejected the API key"),
    (openai.RateLimitError("slow", response=httpx.Response(429, request=REQ), body=None), "rate limit or quota"),
    (openai.NotFoundError("no", response=httpx.Response(404, request=REQ), body=None), "was not found"),
    (openai.APIConnectionError(request=REQ), "Could not reach"),
])
async def test_api_errors_are_translated(exc, msg):
    with pytest.raises(LLMError, match=msg):
        await OpenAILLM(_s(), _FakeClient([exc])).complete([{"role": "user", "content": "x"}])


async def test_empty_answer_is_an_error():
    with pytest.raises(LLMError, match="empty"):
        await OpenAILLM(_s(), _FakeClient(["   "])).complete([{"role": "user", "content": "x"}])
