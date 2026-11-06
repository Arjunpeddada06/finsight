from pydantic import BaseModel, Field


class CalculateRequest(BaseModel):
    metric: str = Field(min_length=2, max_length=64, examples=["revenue_growth"])
    values: dict[str, float] = Field(examples=[{"old_value": 10000, "new_value": 12000}])


class CalculateResponse(BaseModel):
    metric: str
    label: str
    inputs: dict[str, float]
    formula: str
    steps: list[str]
    result: float
    unit: str
    display: str
    notes: list[str]


class MetricInfo(BaseModel):
    metric: str
    label: str
    params: list[str]
    unit: str
    description: str
