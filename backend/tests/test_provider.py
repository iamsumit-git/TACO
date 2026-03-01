"""
tests/test_provider.py — Unit tests for provider.py and logger.py.

All httpx calls are mocked — no real API keys needed.
5 tests as specified in the execution plan.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

import httpx

from app.exceptions import ProviderRateLimitException, ProviderErrorException


def make_openai_response(content: str = "Hello!", prompt_tokens: int = 10, completion_tokens: int = 5):
    """Build a fake OpenAI-shaped httpx Response."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
    return mock_resp


def make_anthropic_response(content: str = "Bonjour!", input_tokens: int = 8, output_tokens: int = 3):
    """Build a fake Anthropic-shaped httpx Response."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "content": [{"text": content}],
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }
    return mock_resp


def make_error_response(status_code: int, detail: dict):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = status_code
    mock_resp.json.return_value = detail
    return mock_resp


# ── Test 1: Mock OpenAI response → logger writes correct row ─────────────────
@pytest.mark.asyncio
async def test_openai_mock_response_correct_parse():
    """Test 1: Mock httpx OpenAI response → ProviderResponse parsed correctly."""
    from app.services.provider import call_provider

    with patch("app.services.provider.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=make_openai_response("Hi there!", 20, 10))
        mock_client_cls.return_value = mock_client

        result = await call_provider(
            model="gpt-4o-mini",
            provider="openai",
            messages=[{"role": "user", "content": "Say hello"}],
        )

    assert result.content == "Hi there!"
    assert result.prompt_tokens == 20
    assert result.completion_tokens == 10
    assert result.total_tokens == 30
    assert result.status_code == 200
    assert result.latency_ms >= 0


# ── Test 2: Mock Anthropic response → correct parse ──────────────────────────
@pytest.mark.asyncio
async def test_anthropic_mock_response_correct_parse():
    """Test 2: Mock httpx Anthropic response → ProviderResponse parsed correctly."""
    from app.services.provider import call_provider

    with patch("app.services.provider.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=make_anthropic_response("Bonjour!", 15, 4))
        mock_client_cls.return_value = mock_client

        result = await call_provider(
            model="claude-haiku-4-5-20251001",
            provider="anthropic",
            messages=[{"role": "user", "content": "Translate hello to French"}],
        )

    assert result.content == "Bonjour!"
    assert result.prompt_tokens == 15
    assert result.completion_tokens == 4
    assert result.total_tokens == 19
    assert result.status_code == 200


# ── Test 3: Cost calculation accuracy ────────────────────────────────────────
@pytest.mark.asyncio
async def test_cost_calculation_is_correct():
    """Test 3: 1000 prompt + 500 completion on gpt-4o-mini → correct $ amount."""
    from app.services.logger import log_request
    from app.models.model_pricing import ModelPricing

    # gpt-4o-mini: $0.00015/1k input, $0.00060/1k output
    # cost = (1000/1000 * 0.00015) + (500/1000 * 0.00060)
    # cost = 0.00015 + 0.00030 = 0.00045
    expected_cost = 0.00045

    fake_pricing = ModelPricing()
    fake_pricing.model = "gpt-4o-mini"
    fake_pricing.provider = "openai"
    fake_pricing.tier = "cheap"
    fake_pricing.input_cost_per_1k = Decimal("0.00015000")
    fake_pricing.output_cost_per_1k = Decimal("0.00060000")
    fake_pricing.is_active = True

    pricing_scalar = MagicMock()
    pricing_scalar.scalar_one_or_none.return_value = fake_pricing

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=pricing_scalar)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    await log_request(
        db=mock_db,
        user_id="test-user",
        org_id=None,
        task_type="simple",
        provider="openai",
        model_requested="gpt-4o-mini",
        model_used="gpt-4o-mini",
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
        latency_ms=250,
        was_sliced=False,
        messages_original_count=1,
        messages_sent_count=1,
        status_code=200,
    )

    # Verify the row added has correct cost
    mock_db.add.assert_called_once()
    added_row = mock_db.add.call_args[0][0]
    assert abs(float(added_row.cost_usd) - expected_cost) < 1e-8, (
        f"Expected cost {expected_cost}, got {added_row.cost_usd}"
    )


# ── Test 4: Provider 429 → ProviderRateLimitException ───────────────────────
@pytest.mark.asyncio
async def test_provider_429_raises_rate_limit_exception():
    """Test 4: Provider returns 429 → raises ProviderRateLimitException."""
    from app.services.provider import call_provider

    rate_limit_resp = make_error_response(429, {"error": "rate_limit_exceeded"})

    with patch("app.services.provider.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=rate_limit_resp)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ProviderRateLimitException) as exc_info:
            await call_provider(
                model="gpt-4o-mini",
                provider="openai",
                messages=[{"role": "user", "content": "Hello"}],
            )

    assert exc_info.value.status_code == 429


# ── Test 5: Provider 500 → ProviderErrorException ───────────────────────────
@pytest.mark.asyncio
async def test_provider_500_raises_error_exception():
    """Test 5: Provider returns 500 → raises ProviderErrorException."""
    from app.services.provider import call_provider

    error_resp = make_error_response(500, {"error": "internal_server_error"})

    with patch("app.services.provider.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=error_resp)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ProviderErrorException) as exc_info:
            await call_provider(
                model="gpt-4o-mini",
                provider="openai",
                messages=[{"role": "user", "content": "Hello"}],
            )

    assert exc_info.value.status_code == 500
