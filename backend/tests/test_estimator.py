"""
tests/test_estimator.py — Unit tests for the token estimator and budget check.

Tests 1-4: estimator.py (pure logic, no DB)
Tests 5-6: budget_check.py (mocked async DB session)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.estimator import estimate_tokens
from app.exceptions import BudgetExceededException


# ─── Estimator Tests ──────────────────────────────────────────────────────────

def test_short_message_low_token_count():
    """Test 1: Short message 'Hello' → estimated_tokens < 10."""
    messages = [{"role": "user", "content": "Hello"}]
    result = estimate_tokens(messages, model="gpt-4o-mini")
    assert result.estimated_tokens < 10, (
        f"Expected < 10 tokens for 'Hello', got {result.estimated_tokens}"
    )
    assert result.method == "tiktoken"


def test_fifty_word_message_reasonable_count():
    """Test 2: 50-word message → estimated tokens roughly match manual count."""
    content = "The quick brown fox jumps over the lazy dog. " * 5  # ~50 words
    messages = [{"role": "user", "content": content}]
    result = estimate_tokens(messages, model="gpt-4o-mini")
    # Rough range: 50 words ≈ 60–80 tokens + 4 overhead = 64–84
    assert 50 <= result.estimated_tokens <= 120, (
        f"50-word message expected 50–120 tokens, got {result.estimated_tokens}"
    )


def test_many_messages_scale_linearly():
    """Test 3: 20 messages of 100 words each → tokens scale proportionally."""
    content = ("word " * 100).strip()  # 100 words
    one_msg = [{"role": "user", "content": content}]
    twenty_msgs = [{"role": "user", "content": content}] * 20

    result_one = estimate_tokens(one_msg, model="gpt-4o-mini")
    result_twenty = estimate_tokens(twenty_msgs, model="gpt-4o-mini")

    # 20x messages should yield roughly 20x tokens (within 20% tolerance)
    ratio = result_twenty.estimated_tokens / result_one.estimated_tokens
    assert 18 <= ratio <= 22, (
        f"Expected ratio ~20x for 20 messages, got {ratio:.1f}x"
    )


def test_claude_model_uses_heuristic():
    """Test 4: claude-* model uses heuristic method, not tiktoken."""
    messages = [{"role": "user", "content": "Explain quantum computing in detail."}]
    result = estimate_tokens(messages, model="claude-haiku-4-5-20251001")
    assert result.method == "heuristic", (
        f"Expected 'heuristic' method for claude model, got '{result.method}'"
    )
    assert result.estimated_tokens > 0


def test_gemini_model_uses_heuristic():
    """Test 4b: gemini-* model also uses heuristic method."""
    messages = [{"role": "user", "content": "Summarize this article."}]
    result = estimate_tokens(messages, model="gemini-1.5-flash")
    assert result.method == "heuristic"


# ─── Budget Check Tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_budget_in_db_passes_through():
    """Test 5: Budget check with no budget in DB → passes without exception."""
    from app.services.budget_check import check_budget

    # Mock DB that returns None for budget query
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Should not raise
    await check_budget(
        db=mock_db,
        user_id="user-no-budget",
        org_id=None,
        estimated_cost_usd=0.50,
    )


@pytest.mark.asyncio
async def test_budget_exceeded_raises_exception():
    """Test 6: Budget check with exceeded limit → raises BudgetExceededException."""
    from app.services.budget_check import check_budget
    from app.models.budget import Budget
    from decimal import Decimal

    # Fake budget: $0.10 daily limit
    fake_budget = Budget()
    fake_budget.entity_type = "user"
    fake_budget.entity_id = "user-tight"
    fake_budget.limit_usd = Decimal("0.10")
    fake_budget.period = "daily"
    fake_budget.action = "block"

    mock_db = AsyncMock()

    # First call returns budget, second call returns spent amount
    budget_result = MagicMock()
    budget_result.scalar_one_or_none.return_value = fake_budget

    spent_result = MagicMock()
    spent_result.scalar.return_value = Decimal("0.09")  # Already spent $0.09

    mock_db.execute = AsyncMock(side_effect=[budget_result, spent_result])

    with pytest.raises(BudgetExceededException) as exc_info:
        await check_budget(
            db=mock_db,
            user_id="user-tight",
            org_id=None,
            estimated_cost_usd=0.02,  # $0.09 + $0.02 = $0.11 > $0.10 limit
        )

    assert exc_info.value.limit_usd == 0.10
    assert exc_info.value.spent_usd == pytest.approx(0.09, rel=1e-3)
