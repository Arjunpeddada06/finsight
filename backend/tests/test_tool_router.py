import pytest

from app.agents.tool_router import run_calculator, wants_calculation, wants_comparison


class FakeLLM:
    def __init__(self, response):
        self.response = response
    async def complete(self, messages, *, temperature=0.0):
        return self.response


def test_intent_detection():
    assert wants_calculation("Calculate revenue growth")
    assert wants_calculation("What is the debt-to-equity ratio?")
    assert wants_comparison("Compare revenue in FY2024 vs FY2025")
    assert not wants_calculation("Summarise the company profile")


@pytest.mark.asyncio
async def test_calculator_uses_report_values_and_returns_exact_result():
    llm = FakeLLM('{"metric":"revenue_growth","values":{"old_value":10000,"new_value":12000},"citations":[1]}')
    outcome = await run_calculator(llm, "Calculate revenue growth", [(1, "Revenue FY2024: 10,000. Revenue FY2025: 12,000.")])
    assert outcome.kind == "calculator"
    assert outcome.result == 20.0
    assert outcome.citation_labels == [1]
    assert "20%" in outcome.text
    assert "(12,000 − 10,000)" in outcome.text


@pytest.mark.asyncio
async def test_calculator_rejects_unverifiable_values():
    llm = FakeLLM('{"metric":"revenue_growth","values":{"old_value":10000,"new_value":99999},"citations":[1]}')
    with pytest.raises(ValueError, match="could not be verified"):
        await run_calculator(llm, "Calculate revenue growth", [(1, "Revenue FY2024: 10,000. Revenue FY2025: 12,000.")])


@pytest.mark.asyncio
async def test_calculator_rejects_unknown_citation():
    llm = FakeLLM('{"metric":"revenue_growth","values":{"old_value":10000,"new_value":12000},"citations":[4]}')
    with pytest.raises(ValueError, match="source that was not supplied"):
        await run_calculator(llm, "Calculate revenue growth", [(1, "Revenue FY2024: 10,000. Revenue FY2025: 12,000.")])
