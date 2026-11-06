"""TEST DOUBLE ONLY. Production always uses OpenAILLM (rag/llm.py).

ScriptedLLM is deterministic: by default it answers by citing the first source label it is shown, so the tests
exercise our retrieval, prompting, citation handling, refusal rules and persistence, not a real model's quality.
"""
import re

from app.rag.llm import LLMError


class ScriptedLLM:
    def __init__(self, answer=None, rewrite=None):
        self.answer, self.rewrite, self.calls = answer, rewrite, []

    async def complete(self, messages, *, temperature=0.0):
        self.calls.append(messages)
        system, user = messages[0]["content"], messages[-1]["content"]
        if system.startswith("Rewrite"):
            return self.rewrite(user) if callable(self.rewrite) else (self.rewrite or user.split("Follow-up message:")[-1].strip())
        if callable(self.answer):
            return self.answer(user)
        if self.answer is not None:
            return self.answer
        label = re.search(r"\[(S\d+)\]", user).group(1)
        return f"The report states the requested figures. [{label}]"

    @property
    def answer_calls(self):
        return [c for c in self.calls if not c[0]["content"].startswith("Rewrite")]


class FailingLLM:
    async def complete(self, messages, *, temperature=0.0):
        raise LLMError("The LLM API rejected the API key. Check OPENAI_API_KEY.")
