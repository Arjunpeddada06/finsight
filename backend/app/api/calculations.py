from fastapi import APIRouter, HTTPException, status

from app.schemas.calculations import CalculateRequest, CalculateResponse, MetricInfo
from app.services.calculation_service import METRICS, CalculationError, calculate_financial_metric

router = APIRouter(tags=["calculations"])


@router.get("/calculate/metrics", response_model=list[MetricInfo])
async def list_metrics() -> list[MetricInfo]:
    return [MetricInfo(metric=k, label=s.label, params=list(s.params), unit=s.unit, description=s.description) for k, s in METRICS.items()]


@router.post("/calculate", response_model=CalculateResponse)
async def calculate(body: CalculateRequest) -> CalculateResponse:
    """calculate_financial_metric: exact, explainable maths. Never computed by the language model."""
    try:
        return CalculateResponse(**calculate_financial_metric(body.metric, body.values).__dict__)
    except CalculationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
