"""
tests/test_router.py — Unit tests for the Smart Router service.

6 tests as specified in the execution plan.
All DB calls are mocked — no real database required.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal

from app.services.router import route_request
from app.exceptions import NoModelAvailableException
from app.models.model_pricing import ModelPricing


def make_db_with_model(
    model: str,
    provider: str,
    tier: str,
    input_cost: float = 0.0001,
    output_cost: float = 0.0004,
) -> AsyncMock:
    """Create a mock DB session that returns one ModelPricing row."""
    fake_model = ModelPricing()
    fake_model.model = model
    fake_model.provider = provider
    fake_model.tier = tier
    fake_model.input_cost_per_1k = Decimal(str(input_cost))
    fake_model.output_cost_per_1k = Decimal(str(output_cost))
    fake_model.is_active = True

    scalars_mock = MagicMock()
    scalars_mock.first.return_value = fake_model

    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=result_mock)
    return mock_db


def make_db_empty() -> AsyncMock:
    """Create a mock DB that returns no models (simulates all disabled)."""
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = None

    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=result_mock)
    return mock_db


# ── Test 1: simple task_type → cheap tier ────────────────────────────────────
@pytest.mark.asyncio
async def test_simple_task_type_returns_cheap_tier():
    """Test 1: task_type='simple' → returns a cheap-tier model."""
    db = make_db_with_model("gpt-4o-mini", "openai", "cheap")
    messages = [{"role": "user", "content": "Say hi."}]

    result = await route_request(db=db, task_type="simple", messages=messages)

    assert result.tier == "cheap"
    assert result.model == "gpt-4o-mini"
    assert result.auto_detected is False


# ── Test 2: complex task_type → smart tier ───────────────────────────────────
@pytest.mark.asyncio
async def test_complex_task_type_returns_smart_tier():
    """Test 2: task_type='complex' → returns a smart-tier model."""
    db = make_db_with_model("gpt-4o", "openai", "smart")
    messages = [{"role": "user", "content": "Explain quantum physics in detail."}]

    result = await route_request(db=db, task_type="complex", messages=messages)

    assert result.tier == "smart"
    assert result.model == "gpt-4o"
    assert result.auto_detected is False


# ── Test 3: auto with simple message → cheap ─────────────────────────────────
@pytest.mark.asyncio
async def test_auto_short_simple_message_routes_to_cheap():
    """Test 3: task_type='auto', message='Summarize this email' → routes to cheap."""
    db = make_db_with_model("gpt-4o-mini", "openai", "cheap")
    messages = [{"role": "user", "content": "Summarize this email"}]

    result = await route_request(db=db, task_type="auto", messages=messages)

    assert result.tier == "cheap"
    assert result.auto_detected is True


# ── Test 4: auto with complex keywords → smart ───────────────────────────────
@pytest.mark.asyncio
async def test_auto_complex_keywords_routes_to_smart():
    """Test 4: task_type='auto', complex keywords → routes to smart."""
    db = make_db_with_model("gpt-4o", "openai", "smart")
    messages = [
        {"role": "user",
         "content": "Debug this Python code and explain the architecture of the system."}
    ]

    result = await route_request(db=db, task_type="auto", messages=messages)

    assert result.tier == "smart"
    assert result.auto_detected is True


# ── Test 5: auto with very long message → smart ──────────────────────────────
@pytest.mark.asyncio
async def test_auto_long_message_routes_to_smart():
    """Test 5: task_type='auto', very long message (>200 tokens) → routes to smart."""
    db = make_db_with_model("gpt-4o", "openai", "smart")
    # Generate a message well above 200 tokens (~800 words)
    long_content = "The quick brown fox jumps over the lazy dog. " * 100
    messages = [{"role": "user", "content": long_content}]

    result = await route_request(db=db, task_type="auto", messages=messages)

    assert result.tier == "smart"
    assert result.auto_detected is True


# ── Test 6: no models available → exception ──────────────────────────────────
@pytest.mark.asyncio
async def test_no_models_available_raises_exception():
    """Test 6: All cheap models disabled in DB → raises NoModelAvailableException."""
    db = make_db_empty()
    messages = [{"role": "user", "content": "Hello!"}]

    with pytest.raises(NoModelAvailableException) as exc_info:
        await route_request(db=db, task_type="simple", messages=messages)

    assert exc_info.value.tier == "cheap"
