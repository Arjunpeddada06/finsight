"""Deterministic financial calculator. The LLM must call this instead of doing arithmetic itself.

Every result carries the formula with the real numbers filled in and the calculation steps, so the answer can show
its working. Rounding is half-up to 2 decimals (Decimal), so 1.825 becomes 1.83 rather than a float artefact.
"""
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal


class CalculationError(ValueError):
    """Raised with a user-readable message for unknown metrics, missing inputs or impossible maths."""


@dataclass
class CalcResult:
    metric: str
    label: str
    inputs: dict[str, float]
    formula: str
    steps: list[str]
    result: float
    unit: str  # "%" or "x"
    display: str
    notes: list[str] = field(default_factory=list)


def round_half_up(x: float, places: int = 2) -> float:
    return float(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def fmt(x: float) -> str:
    """12000.0 -> '12,000'; 0.4634 -> '0.4634'; 18.8219 -> '18.82'."""
    places = 2 if abs(x) >= 1 or x == 0 else 4
    s = f"{round_half_up(x, places):,.{places}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


@dataclass
class _Out:
    value: float
    formula: str
    steps: list[str]
    notes: list[str] = field(default_factory=list)


def _nonzero(x: float, what: str) -> None:
    if x == 0:
        raise CalculationError(f"{what} is zero, so this result is undefined.")


def _pct_change(old: float, new: float) -> _Out:
    _nonzero(old, "The old value")
    diff = new - old
    ratio = diff / abs(old)
    value = ratio * 100
    base = fmt(old) if old > 0 else f"|{fmt(old)}|"
    notes = ["The old value is negative, so the percentage change is measured against its absolute value."] if old < 0 else []
    return _Out(value, f"({fmt(new)} − {fmt(old)}) / {base} × 100 = {fmt(value)}%",
                [f"Change = {fmt(new)} − {fmt(old)} = {fmt(diff)}", f"Change ÷ old value = {fmt(diff)} ÷ {fmt(abs(old))} = {fmt(ratio)}",
                 f"× 100 = {fmt(value)}%"], notes)


def _margin(numerator: float, revenue: float, what: str) -> _Out:
    _nonzero(revenue, "Revenue")
    value = numerator / revenue * 100
    return _Out(value, f"{fmt(numerator)} / {fmt(revenue)} × 100 = {fmt(value)}%",
                [f"{what} ÷ revenue = {fmt(numerator)} ÷ {fmt(revenue)} = {fmt(numerator / revenue)}", f"× 100 = {fmt(value)}%"])


def _cagr(begin: float, end: float, years: float) -> _Out:
    if begin <= 0:
        raise CalculationError("CAGR needs a positive starting value.")
    if end < 0:
        raise CalculationError("CAGR needs a non-negative ending value.")
    if years <= 0:
        raise CalculationError("The number of years must be greater than zero.")
    value = ((end / begin) ** (1 / years) - 1) * 100
    return _Out(value, f"(({fmt(end)} / {fmt(begin)})^(1/{fmt(years)}) − 1) × 100 = {fmt(value)}%",
                [f"End ÷ begin = {fmt(end)} ÷ {fmt(begin)} = {fmt(end / begin)}", f"Raise to 1/{fmt(years)}: {fmt((end / begin) ** (1 / years))}",
                 f"Subtract 1 and × 100 = {fmt(value)}%"])


def _ratio(num: float, den: float, num_name: str, den_name: str) -> _Out:
    _nonzero(den, den_name.capitalize())
    value = num / den
    return _Out(value, f"{fmt(num)} / {fmt(den)} = {fmt(value)}", [f"{num_name} ÷ {den_name} = {fmt(num)} ÷ {fmt(den)} = {fmt(value)}"])


@dataclass(frozen=True)
class MetricSpec:
    label: str
    params: tuple[str, ...]
    unit: str
    description: str
    fn: Callable[..., _Out]


METRICS: dict[str, MetricSpec] = {
    "percentage_change": MetricSpec("Percentage change", ("old_value", "new_value"), "%", "(new − old) / |old| × 100", lambda old_value, new_value: _pct_change(old_value, new_value)),
    "revenue_growth": MetricSpec("Revenue growth", ("old_value", "new_value"), "%", "Percentage change in revenue", lambda old_value, new_value: _pct_change(old_value, new_value)),
    "yoy_growth": MetricSpec("Year-on-year growth", ("old_value", "new_value"), "%", "Percentage change versus the previous year", lambda old_value, new_value: _pct_change(old_value, new_value)),
    "eps_growth": MetricSpec("EPS growth", ("old_eps", "new_eps"), "%", "Percentage change in earnings per share", lambda old_eps, new_eps: _pct_change(old_eps, new_eps)),
    "profit_margin": MetricSpec("Profit margin", ("profit", "revenue"), "%", "profit / revenue × 100", lambda profit, revenue: _margin(profit, revenue, "Profit")),
    "gross_margin": MetricSpec("Gross margin", ("gross_profit", "revenue"), "%", "gross profit / revenue × 100", lambda gross_profit, revenue: _margin(gross_profit, revenue, "Gross profit")),
    "operating_margin": MetricSpec("Operating margin", ("operating_profit", "revenue"), "%", "operating profit / revenue × 100", lambda operating_profit, revenue: _margin(operating_profit, revenue, "Operating profit")),
    "net_profit_margin": MetricSpec("Net profit margin", ("net_profit", "revenue"), "%", "net profit / revenue × 100", lambda net_profit, revenue: _margin(net_profit, revenue, "Net profit")),
    "cagr": MetricSpec("CAGR", ("begin_value", "end_value", "years"), "%", "((end / begin)^(1/years) − 1) × 100", lambda begin_value, end_value, years: _cagr(begin_value, end_value, years)),
    "debt_to_equity": MetricSpec("Debt-to-equity ratio", ("total_debt", "total_equity"), "x", "total debt / total equity", lambda total_debt, total_equity: _ratio(total_debt, total_equity, "Total debt", "total equity")),
    "current_ratio": MetricSpec("Current ratio", ("current_assets", "current_liabilities"), "x", "current assets / current liabilities", lambda current_assets, current_liabilities: _ratio(current_assets, current_liabilities, "Current assets", "current liabilities")),
}


def calculate_financial_metric(metric: str, values: Mapping[str, float]) -> CalcResult:
    key = (metric or "").strip().lower().replace(" ", "_").replace("-", "_")
    spec = METRICS.get(key)
    if spec is None:
        raise CalculationError(f"Unknown metric '{metric}'. Supported: {', '.join(sorted(METRICS))}.")
    missing = [p for p in spec.params if p not in values]
    if missing:
        raise CalculationError(f"{spec.label} needs: {', '.join(spec.params)}. Missing: {', '.join(missing)}.")
    extra = [k for k in values if k not in spec.params]
    if extra:
        raise CalculationError(f"Unexpected values for {spec.label}: {', '.join(extra)}. Expected: {', '.join(spec.params)}.")
    for name in spec.params:
        v = values[name]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise CalculationError(f"'{name}' must be a finite number.")
    out = spec.fn(**{p: float(values[p]) for p in spec.params})
    rounded = round_half_up(out.value)
    display = f"{fmt(out.value)}%" if spec.unit == "%" else f"{fmt(out.value)}x"
    return CalcResult(key, spec.label, {p: float(values[p]) for p in spec.params}, out.formula, out.steps, rounded, spec.unit, display, out.notes)
