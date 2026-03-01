"""
app/routers/analytics.py — Analytics endpoints.

GET /analytics/overview   — Spend summary for a user/org/period
GET /analytics/timeseries — Daily cost/request breakdown
GET /analytics/requests   — Paginated request log
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import logging
from sqlalchemy import func, select, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.model_pricing import ModelPricing
from app.models.request_log import RequestLog
from app.schemas.analytics import (
    ModelBreakdown,
    OverviewResponse,
    PaginatedRequests,
    RequestLogRow,
    TimeseriesPoint,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _period_start(period: str = "30d") -> datetime:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if period == "7d":
        return now - timedelta(days=7)
    elif period == "mtd":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # 30d default
        return now - timedelta(days=30)


def _build_base_filter(stmt, user_id, org_id, since):
    stmt = stmt.where(RequestLog.created_at >= since)
    if user_id:
        stmt = stmt.where(RequestLog.user_id == user_id)
    if org_id:
        stmt = stmt.where(RequestLog.org_id == org_id)
    return stmt


@router.get("/overview", response_model=OverviewResponse)
async def overview(
    user_id: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    period: str = Query("30d"),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated spend overview for a user/org within a time period."""
    try:
        since = _period_start(period)

        # Core aggregates
        agg_stmt = _build_base_filter(
            select(
                func.coalesce(func.sum(RequestLog.cost_usd), 0).label("total_cost"),
                func.count(RequestLog.id).label("total_requests"),
                func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
            ),
            user_id, org_id, since,
        )
        agg_result = await db.execute(agg_stmt)
        agg = agg_result.one()

        total_cost = float(agg.total_cost)
        total_requests = int(agg.total_requests)
        total_tokens = int(agg.total_tokens)
        avg_cost = total_cost / total_requests if total_requests > 0 else 0.0

        # Cheap tier percentage
        cheap_stmt = _build_base_filter(
            select(func.count(RequestLog.id)),
            user_id, org_id, since,
        ).where(RequestLog.task_type == "simple")
        cheap_result = await db.execute(cheap_stmt)
        cheap_count = cheap_result.scalar() or 0
        cheap_pct = (cheap_count / total_requests * 100) if total_requests > 0 else 0.0

        # Savings estimate
        cheap_cost_stmt = _build_base_filter(
            select(func.coalesce(func.sum(RequestLog.cost_usd), 0)),
            user_id, org_id, since,
        ).where(RequestLog.task_type == "simple")
        cheap_cost_res = await db.execute(cheap_cost_stmt)
        cheap_cost = float(cheap_cost_res.scalar() or 0)
        savings_usd = cheap_cost * 9.0

        # Top models
        top_models_stmt = _build_base_filter(
            select(
                RequestLog.model_used,
                func.count(RequestLog.id).label("req_count"),
                func.coalesce(func.sum(RequestLog.cost_usd), 0).label("cost"),
            ),
            user_id, org_id, since,
        ).group_by(RequestLog.model_used).order_by(
            func.count(RequestLog.id).desc()
        ).limit(5)

        top_result = await db.execute(top_models_stmt)
        top_models = [
            ModelBreakdown(
                model=r.model_used or "unknown",
                request_count=r.req_count,
                cost_usd=float(r.cost),
            )
            for r in top_result.all()
        ]

        return OverviewResponse(
            total_cost_usd=total_cost,
            total_requests=total_requests,
            total_tokens=total_tokens,
            avg_cost_per_request=avg_cost,
            cheap_tier_pct=cheap_pct,
            savings_usd=savings_usd,
            top_models=top_models,
        )

    except Exception as e:
        logging.exception("Error in /analytics/overview")
        return JSONResponse(
            status_code=500,
            content={"error": "internal", "message": str(e)},
        )


@router.get("/timeseries", response_model=list[TimeseriesPoint])
async def timeseries(
    user_id: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    days: int = Query(30),
    db: AsyncSession = Depends(get_db),
):
    """Daily cost + request count for the last N days."""
    try:
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

        stmt = select(
            cast(RequestLog.created_at, Date).label("day"),
            func.coalesce(func.sum(RequestLog.cost_usd), 0).label("cost"),
            func.count(RequestLog.id).label("req_count"),
            func.coalesce(func.sum(RequestLog.total_tokens), 0).label("tokens"),
        ).where(RequestLog.created_at >= since)

        if user_id:
            stmt = stmt.where(RequestLog.user_id == user_id)
        if org_id:
            stmt = stmt.where(RequestLog.org_id == org_id)

        stmt = stmt.group_by(
            cast(RequestLog.created_at, Date)
        ).order_by("day")

        result = await db.execute(stmt)

        return [
            TimeseriesPoint(
                date=str(r.day),
                cost_usd=float(r.cost),
                request_count=int(r.req_count),
                total_tokens=int(r.tokens),
            )
            for r in result.all()
        ]

    except Exception as e:
        logging.exception("Error in /analytics/timeseries")
        return JSONResponse(
            status_code=500,
            content={"error": "internal", "message": str(e)},
        )


@router.get("/requests", response_model=PaginatedRequests)
async def requests_log(
    user_id: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated request log with optional filters."""
    try:
        offset = (page - 1) * limit

        base = select(RequestLog)
        count_base = select(func.count(RequestLog.id))

        if user_id:
            base = base.where(RequestLog.user_id == user_id)
            count_base = count_base.where(RequestLog.user_id == user_id)
        if org_id:
            base = base.where(RequestLog.org_id == org_id)
            count_base = count_base.where(RequestLog.org_id == org_id)
        if model:
            base = base.where(RequestLog.model_used == model)
            count_base = count_base.where(RequestLog.model_used == model)

        total_result = await db.execute(count_base)
        total = total_result.scalar() or 0

        rows_result = await db.execute(
            base.order_by(RequestLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = rows_result.scalars().all()

        return PaginatedRequests(
            items=[
                RequestLogRow(
                    id=str(r.id),
                    user_id=r.user_id,
                    org_id=r.org_id,
                    task_type=r.task_type,
                    provider=r.provider,
                    model_used=r.model_used,
                    prompt_tokens=r.prompt_tokens,
                    completion_tokens=r.completion_tokens,
                    total_tokens=r.total_tokens,
                    cost_usd=float(r.cost_usd) if r.cost_usd is not None else None,
                    latency_ms=r.latency_ms,
                    was_sliced=r.was_sliced or False,
                    status_code=r.status_code,
                    created_at=r.created_at.isoformat() if r.created_at else "",
                )
                for r in rows
            ],
            total=total,
            page=page,
            limit=limit,
        )

    except Exception as e:
        logging.exception("Error in /analytics/requests")
        return JSONResponse(
            status_code=500,
            content={"error": "internal", "message": str(e)},
        )