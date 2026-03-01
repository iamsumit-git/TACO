"""
app/services/budget_check.py — Check if a user/org exceeds their spend budget.

Queries the `budgets` table for a configured limit, then sums `cost_usd` from
`request_logs` within the matching period window.

Raises BudgetExceededException if spent + estimated_cost >= limit.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BudgetExceededException
from app.models.budget import Budget
from app.models.request_log import RequestLog


def _period_start(period: str) -> datetime:
    """Return the UTC datetime at the start of the given budget period."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if period == "daily":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "weekly":
        days_since_monday = now.weekday()
        start = now - timedelta(days=days_since_monday)
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "monthly":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        # Default: daily
        return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def check_budget(
    db: AsyncSession,
    user_id: str,
    org_id: Optional[str],
    estimated_cost_usd: float,
) -> None:
    """
    Check whether sending this request would exceed any budget limits.

    Checks user-level budget first, then org-level if applicable.
    Raises BudgetExceededException if limit would be breached.
    Does nothing (returns None) if no budget is configured.
    """
    entities = [("user", user_id)]
    if org_id:
        entities.append(("org", org_id))

    for entity_type, entity_id in entities:
        # Find budget config for this entity
        budget_result = await db.execute(
            select(Budget).where(
                Budget.entity_type == entity_type,
                Budget.entity_id == entity_id,
            )
        )
        budget = budget_result.scalar_one_or_none()

        if budget is None:
            continue  # No budget configured — allow through

        period_start = _period_start(budget.period)

        # Sum cost already spent in this period
        if entity_type == "user":
            filter_col = RequestLog.user_id
        else:
            filter_col = RequestLog.org_id

        spent_result = await db.execute(
            select(func.coalesce(func.sum(RequestLog.cost_usd), 0)).where(
                filter_col == entity_id,
                RequestLog.created_at >= period_start,
            )
        )
        spent_usd = float(spent_result.scalar())

        if spent_usd + estimated_cost_usd >= float(budget.limit_usd):
            raise BudgetExceededException(
                spent_usd=spent_usd,
                limit_usd=float(budget.limit_usd),
                entity_id=entity_id,
            )
