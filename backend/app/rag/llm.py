
"""Chat-completion client for OpenAI-compatible APIs, including Gemini."""
import logging
from typing import Protocol

import openai

from app.config import Settings, get_settings

log = logging.getLogger(__name__)


class LLMError(Exception):
    """User-readable LLM failure."""


class LLM(Protocol):
    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
    ) -> str: ...


class OpenAILLM:
    def __init__(
        self,
        settings: Settings | None = None,
        client: openai.AsyncOpenAI | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def _get_client(self) -> openai.AsyncOpenAI:
        s = self.settings

        if not s.llm_model:
            raise LLMError("LLM_MODEL is not set in .env.")

        api_key = s.openai_api_key or s.gemini_api_key

        if self._client is None:
            if not api_key:
                raise LLMError(
                    "Neither OPENAI_API_KEY nor GEMINI_API_KEY is configured."
                )

            self._client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=s.openai_base_url,
                max_retries=1,
                timeout=45.0,
            )

        return self._client

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
    ) -> str:
        client = self._get_client()

        kwargs = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": temperature,
        }

        try:
            try:
                resp = await client.chat.completions.create(**kwargs)
            except openai.BadRequestError as exc:
                if "temperature" not in str(exc).lower():
                    raise

                kwargs.pop("temperature")
                resp = await client.chat.completions.create(**kwargs)

        except openai.AuthenticationError as exc:
            raise LLMError(
                "Gemini rejected the API key. Check GEMINI_API_KEY."
            ) from exc

        except openai.RateLimitError as exc:
            raise LLMError(
                "Gemini API quota or rate limit reached. "
                "Check your Google AI Studio usage."
            ) from exc

        except openai.NotFoundError as exc:
            raise LLMError(
                f"Model '{self.settings.llm_model}' was not found."
            ) from exc

        except openai.APIStatusError as exc:
            log.exception(
                "LLM server error: HTTP %s", exc.status_code
            )
            if exc.status_code >= 500:
                raise LLMError(
                    "Gemini chat service is temporarily unavailable. "
                    "Please try again shortly."
                ) from exc

            raise LLMError(
                f"Gemini API returned HTTP {exc.status_code}: "
                f"{str(exc)[:200]}"
            ) from exc

        except openai.APIConnectionError as exc:
            raise LLMError(
                "Could not connect to Gemini. Check internet connectivity."
            ) from exc

        except openai.OpenAIError as exc:
            log.exception("LLM API error")
            raise LLMError(
                f"LLM API error: {str(exc)[:200]}"
            ) from exc

        text = (
            resp.choices[0].message.content or ""
        ).strip() if resp.choices else ""

        if not text:
            raise LLMError("The LLM returned an empty answer. Try again.")

        return text


_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm

    if _llm is None:
        _llm = OpenAILLM()

    return _llm


def set_llm(llm: LLM | None) -> None:
    """Replace the process-wide LLM (used by tests)."""
    global _llm
    _llm = llm
