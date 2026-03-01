"""
app/schemas/analytics.py — Pydantic response shapes for /analytics/* endpoints.
"""
from typing import List, Optional
from pydantic import BaseModel


class ModelBreakdown(BaseModel):
    model: str
    request_count: int
    cost_usd: float


class OverviewResponse(BaseModel):
    total_cost_usd: float
    total_requests: int
    total_tokens: int
    avg_cost_per_request: float
    cheap_tier_pct: float
    savings_usd: float
    top_models: List[ModelBreakdown]


class TimeseriesPoint(BaseModel):
    date: str
    cost_usd: float
    request_count: int
    total_tokens: int


class RequestLogRow(BaseModel):
    id: str
    user_id: str
    org_id: Optional[str]
    task_type: Optional[str]
    provider: Optional[str]
    model_used: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    cost_usd: Optional[float]
    latency_ms: Optional[int]
    was_sliced: bool
    status_code: Optional[int]
    created_at: str


class PaginatedRequests(BaseModel):
    items: List[RequestLogRow]
    total: int
    page: int
    limit: int
