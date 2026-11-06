import pytest

from app.services.calculation_service import CalculationError, calculate_financial_metric as calc, fmt, round_half_up


def test_spec_examples():
    r = calc("revenue_growth", {"old_value": 1000, "new_value": 1200})
    assert r.result == 20.0 and r.display == "20%" and r.formula == "(1,200 − 1,000) / 1,000 × 100 = 20%"
    assert calc("profit_margin", {"profit": 200, "revenue": 1000}).result == 20.0


def test_sample_report_values():
    assert calc("yoy_growth", {"old_value": 8500, "new_value": 10000}).display == "17.65%"
    assert calc("yoy_growth", {"old_value": 10000, "new_value": 12000}).result == 20.0
    assert calc("net_profit_margin", {"net_profit": 1305, "revenue": 12000}).display == "10.88%"
    assert calc("gross_margin", {"gross_profit": 4920, "revenue": 12000}).result == 41.0
    assert calc("operating_margin", {"operating_profit": 1980, "revenue": 12000}).result == 16.5
    assert calc("eps_growth", {"old_eps": 10.05, "new_eps": 13.05}).display == "29.85%"
    assert calc("cagr", {"begin_value": 8500, "end_value": 12000, "years": 2}).display == "18.82%"
    d = calc("debt_to_equity", {"total_debt": 3800, "total_equity": 8200})
    assert d.result == 0.46 and d.display == "0.4634x" and d.unit == "x"
    assert calc("current_ratio", {"current_assets": 7300, "current_liabilities": 4000}).result == 1.83  # half-up, not 1.82


def test_steps_and_inputs_are_returned():
    r = calc("percentage_change", {"old_value": 10000, "new_value": 12000})
    assert r.steps[0] == "Change = 12,000 − 10,000 = 2,000" and r.inputs == {"old_value": 10000.0, "new_value": 12000.0}


def test_decrease_and_negative_base():
    assert calc("percentage_change", {"old_value": 200, "new_value": 150}).result == -25.0
    r = calc("percentage_change", {"old_value": -100, "new_value": -50})
    assert r.result == 50.0 and r.notes  # loss halved = improvement, explained


def test_metric_name_is_normalised():
    assert calc("Revenue Growth", {"old_value": 1, "new_value": 2}).metric == "revenue_growth"
    assert calc("debt-to-equity", {"total_debt": 1, "total_equity": 2}).result == 0.5


@pytest.mark.parametrize("metric,values,msg", [
    ("percentage_change", {"old_value": 0, "new_value": 5}, "old value is zero"),
    ("profit_margin", {"profit": 5, "revenue": 0}, "Revenue is zero"),
    ("debt_to_equity", {"total_debt": 5, "total_equity": 0}, "Total equity is zero"),
    ("current_ratio", {"current_assets": 5, "current_liabilities": 0}, "Current liabilities is zero"),
    ("cagr", {"begin_value": 0, "end_value": 5, "years": 2}, "positive starting value"),
    ("cagr", {"begin_value": 5, "end_value": 9, "years": 0}, "greater than zero"),
    ("cagr", {"begin_value": 5, "end_value": -1, "years": 2}, "non-negative"),
    ("nonsense", {"a": 1}, "Unknown metric"),
    ("profit_margin", {"profit": 5}, "Missing: revenue"),
    ("profit_margin", {"profit": 5, "revenue": 10, "tax": 1}, "Unexpected values"),
    ("profit_margin", {"profit": float("nan"), "revenue": 10}, "finite number"),
    ("profit_margin", {"profit": True, "revenue": 10}, "finite number"),
])
def test_invalid_inputs_raise_readable_errors(metric, values, msg):
    with pytest.raises(CalculationError, match=msg):
        calc(metric, values)


def test_rounding_and_formatting():
    assert round_half_up(2.675) == 2.68 and round_half_up(1.825) == 1.83
    assert fmt(12000.0) == "12,000" and fmt(0.46341) == "0.4634" and fmt(-25.0) == "-25"


async def test_calculate_api(client):
    r = await client.post("/api/calculate", json={"metric": "revenue_growth", "values": {"old_value": 10000, "new_value": 12000}})
    assert r.status_code == 200
    j = r.json()
    assert j["result"] == 20.0 and j["display"] == "20%" and j["formula"].startswith("(12,000 − 10,000)")
    bad = await client.post("/api/calculate", json={"metric": "profit_margin", "values": {"profit": 1, "revenue": 0}})
    assert bad.status_code == 422 and "Revenue is zero" in bad.json()["detail"]
    assert (await client.post("/api/calculate", json={"metric": "cagr", "values": {"begin_value": "abc"}})).status_code == 422
    metrics = (await client.get("/api/calculate/metrics")).json()
    assert {m["metric"] for m in metrics} >= {"cagr", "debt_to_equity", "current_ratio", "eps_growth"}
