"""
app/services/logger.py — Cost logger for request_logs table.

Fetches pricing from model_pricing, calculates cost_usd, and INSERTs
a row into request_logs. Designed to run as a FastAPI BackgroundTask
so the response is returned to the caller immediately.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_pricing import ModelPricing
from app.models.request_log import RequestLog


async def log_request(
    db: AsyncSession,
    user_id: str,
    org_id: Optional[str],
    task_type: str,
    provider: str,
    model_requested: str,
    model_used: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    latency_ms: int,
    was_sliced: bool,
    messages_original_count: int,
    messages_sent_count: int,
    status_code: int,
    error_message: Optional[str] = None,
) -> None:
    """
    Calculate cost and insert a row into request_logs.

    This function is safe to call as a FastAPI BackgroundTask.
    If pricing is not found, cost_usd is stored as 0.
    """
    # Look up pricing for the model actually used
    pricing_result = await db.execute(
        select(ModelPricing).where(ModelPricing.model == model_used)
    )
    pricing = pricing_result.scalar_one_or_none()

    if pricing:
        cost_usd = (
            (prompt_tokens / 1000) * float(pricing.input_cost_per_1k)
            + (completion_tokens / 1000) * float(pricing.output_cost_per_1k)
        )
    else:
        cost_usd = 0.0

    log_row = RequestLog(
        id=uuid.uuid4(),
        user_id=user_id,
        org_id=org_id,
        task_type=task_type,
        provider=provider,
        model_requested=model_requested,
        model_used=model_used,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        was_sliced=was_sliced,
        messages_original_count=messages_original_count,
        messages_sent_count=messages_sent_count,
        status_code=status_code,
        error_message=error_message,
        created_at=datetime.now(timezone.utc),
    )

    db.add(log_row)
    await db.commit()
