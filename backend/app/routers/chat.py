"""
app/routers/chat.py — POST /v1/chat — Full TACO pipeline.

Pipeline:
  1. Validate request (Pydantic)
  2. Token estimator → budget check
  3. Context slicer
  4. Smart router → pick model
  5. Provider call → get response
  6. Schedule cost logger as BackgroundTask
  7. Return normalized response
"""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db, AsyncSessionLocal
from app.exceptions import (
    BudgetExceededException,
    ContextTooLargeException,
    NoModelAvailableException,
    ProviderErrorException,
    ProviderRateLimitException,
)
from app.models.model_pricing import ModelPricing
from app.schemas.chat import ChatRequest, ChatResponse, ResponseMetadata, UsageInfo
from app.services.budget_check import check_budget
from app.services.estimator import estimate_tokens
from app.services.logger import log_request
from app.services.provider import call_provider
from app.services.router import route_request
from app.services.slicer import slice_messages
from sqlalchemy import select

router = APIRouter(prefix="/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Main TACO proxy endpoint.

    Accepts a chat request, routes it to the optimal LLM model,
    tracks token usage and cost, then returns the LLM's response.
    """
    request_id = str(uuid.uuid4())
    messages_raw = [m.model_dump() for m in body.messages]

    # ── STEP 2: Token Estimator ─────────────────────────────────────────────
    # Use requested model (or default cheap) for estimation
    estimate_model = body.model or settings.default_cheap_model
    token_estimate = estimate_tokens(messages_raw, estimate_model)

    # Check model context window
    pricing_result = await db.execute(
        select(ModelPricing).where(ModelPricing.model == estimate_model)
    )
    pricing_row = pricing_result.scalar_one_or_none()
    if pricing_row and token_estimate.estimated_tokens > pricing_row.context_window:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "context_too_large",
                "estimated_tokens": token_estimate.estimated_tokens,
                "context_window": pricing_row.context_window,
                "model": estimate_model,
            },
        )

    # Rough cost estimate for budget check (using cheap defaults)
    rough_cost = token_estimate.estimated_tokens * 0.0000002  # conservative estimate
    await check_budget(
        db=db,
        user_id=body.user_id,
        org_id=body.org_id,
        estimated_cost_usd=rough_cost,
    )

    # ── STEP 3: Context Slicer ──────────────────────────────────────────────
    slicer_result = slice_messages(messages_raw, window_size=settings.slice_window)

    # ── STEP 4: Smart Router ────────────────────────────────────────────────
    route = await route_request(
        db=db,
        task_type=body.task_type,
        messages=slicer_result.messages,
    )

    # ── STEP 5: Provider Call ───────────────────────────────────────────────
    provider_response = await call_provider(
        model=route.model,
        provider=route.provider,
        messages=slicer_result.messages,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
    )

    # ── STEP 6: Background Cost Logger ──────────────────────────────────────
    # Use a fresh DB session in the background task
    async def _log():
        async with AsyncSessionLocal() as bg_session:
            await log_request(
                db=bg_session,
                user_id=body.user_id,
                org_id=body.org_id,
                task_type=body.task_type,
                provider=route.provider,
                model_requested=body.model or route.model,
                model_used=route.model,
                prompt_tokens=provider_response.prompt_tokens,
                completion_tokens=provider_response.completion_tokens,
                total_tokens=provider_response.total_tokens,
                latency_ms=provider_response.latency_ms,
                was_sliced=slicer_result.was_sliced,
                messages_original_count=slicer_result.original_count,
                messages_sent_count=slicer_result.sent_count,
                status_code=provider_response.status_code,
            )

    background_tasks.add_task(_log)

    # ── STEP 7: Return Response ──────────────────────────────────────────────
    # Cost estimate for response (will differ from logged cost slightly)
    resp_cost = (
        (provider_response.prompt_tokens / 1000 * 0.00015)
        + (provider_response.completion_tokens / 1000 * 0.00060)
    )

    return ChatResponse(
        id=request_id,
        model_used=route.model,
        content=provider_response.content,
        usage=UsageInfo(
            prompt_tokens=provider_response.prompt_tokens,
            completion_tokens=provider_response.completion_tokens,
            total_tokens=provider_response.total_tokens,
            cost_usd=resp_cost,
        ),
        metadata=ResponseMetadata(
            was_sliced=slicer_result.was_sliced,
            messages_trimmed=slicer_result.original_count - slicer_result.sent_count,
            latency_ms=provider_response.latency_ms,
            routed_to_tier=route.tier,
        ),
    )
