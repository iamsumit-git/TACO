"""
app/services/router.py — Smart model routing service.

Picks the right model tier (cheap vs smart) based on task_type.
If task_type == 'auto', runs complexity detection:
  - Simple signals: short message (<100 tokens), simple keywords
  - Complex signals: long message (>200 tokens), complex keywords
  - Default: simple (bias toward cheaper)

Returns a RouterResult with model, provider, tier, and auto_detected flag.
Raises NoModelAvailableException if no active model exists for the tier.
"""
from dataclasses import dataclass
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NoModelAvailableException
from app.models.model_pricing import ModelPricing
from app.services.estimator import estimate_tokens

# Keywords that signal a SIMPLE task
SIMPLE_KEYWORDS = {
    "summarize", "translate", "rewrite", "list",
    "classify", "yes", "no", "hello", "hi",
}

# Keywords that signal a COMPLEX task
COMPLEX_KEYWORDS = {
    "debug", "analyze", "analyse", "compare", "explain",
    "architecture", "reason", "code", "implement", "design",
    "optimize", "refactor", "write code", "why",
}

SIMPLE_TOKEN_THRESHOLD = 100
COMPLEX_TOKEN_THRESHOLD = 200


@dataclass
class RouterResult:
    model: str
    provider: str
    tier: str              # 'cheap' | 'smart'
    auto_detected: bool


def _detect_complexity(messages: List[dict], model: str = "gpt-4o-mini") -> str:
    """
    Heuristic complexity detection for 'auto' mode.

    Returns 'simple' or 'complex'.
    """
    # Concatenate all message content
    full_text = " ".join(m.get("content", "") for m in messages).lower()
    token_result = estimate_tokens(messages, model=model)
    token_count = token_result.estimated_tokens

    # Check keywords
    has_complex = any(kw in full_text for kw in COMPLEX_KEYWORDS)
    has_simple = any(kw in full_text for kw in SIMPLE_KEYWORDS)

    if token_count > COMPLEX_TOKEN_THRESHOLD or has_complex:
        return "complex"
    if token_count < SIMPLE_TOKEN_THRESHOLD and not has_complex:
        return "simple"

    # Ambiguous → default to simple (cheap)
    return "simple"


async def route_request(
    db: AsyncSession,
    task_type: str,
    messages: List[dict],
) -> RouterResult:
    """
    Determine the best model to use for this request.

    Args:
        db:        Async DB session (reads model_pricing table)
        task_type: 'simple' | 'complex' | 'auto'
        messages:  The conversation messages (used only for auto-detection)

    Returns:
        RouterResult with model name, provider, tier, and auto_detected flag.

    Raises:
        NoModelAvailableException if no active model exists for the required tier.
    """
    auto_detected = False
    task_to_tier = {"simple": "cheap", "complex": "smart"}

    if task_type == "auto":
        detected = _detect_complexity(messages)
        tier = task_to_tier[detected]
        auto_detected = True
    elif task_type == "simple":
        tier = "cheap"
    else:
        tier = "smart"

    # Query DB: cheapest active model for this tier
    # "Cheapest" = lowest sum of input + output cost per 1k
    result = await db.execute(
        select(ModelPricing)
        .where(
            ModelPricing.tier == tier,
            ModelPricing.is_active.is_(True),
        )
        .order_by(
            (ModelPricing.input_cost_per_1k + ModelPricing.output_cost_per_1k).asc()
        )
    )
    model_row = result.scalars().first()

    if model_row is None:
        raise NoModelAvailableException(tier=tier)

    return RouterResult(
        model=model_row.model,
        provider=model_row.provider,
        tier=tier,
        auto_detected=auto_detected,
    )
