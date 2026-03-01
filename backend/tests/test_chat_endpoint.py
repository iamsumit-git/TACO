"""
tests/test_chat_endpoint.py — Integration tests for POST /v1/chat.

Uses httpx AsyncClient against the full FastAPI app.
All provider and DB calls mocked via pytest monkeypatch / patch.
7 tests as specified in the execution plan.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from decimal import Decimal
from contextlib import asynccontextmanager

from httpx import AsyncClient, ASGITransport


def make_router_result(model="gpt-4o-mini", provider="openai", tier="cheap"):
    from app.services.router import RouterResult
    return RouterResult(model=model, provider=provider, tier=tier, auto_detected=False)


def make_provider_response(content="Hello!", prompt=10, completion=5):
    from app.services.provider import ProviderResponse
    return ProviderResponse(
        content=content, prompt_tokens=prompt, completion_tokens=completion,
        total_tokens=prompt + completion, latency_ms=150, status_code=200,
    )


SIMPLE_BODY = {
    "user_id": "test-user",
    "task_type": "simple",
    "messages": [{"role": "user", "content": "Say hello"}],
}
COMPLEX_BODY = {
    "user_id": "test-user",
    "task_type": "complex",
    "messages": [{"role": "user", "content": "Explain async/await in Python with code examples."}],
}


def make_mock_db():
    """Build a mock async DB session — returns no pricing row (no context window check)."""
    mock_db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    scalars = MagicMock()
    scalars.first.return_value = None
    result.scalars.return_value = scalars
    result.scalar.return_value = Decimal("0")
    mock_db.execute = AsyncMock(return_value=result)
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.close = AsyncMock()
    return mock_db


def make_async_session_local():
    """Return a mock AsyncSessionLocal that works as 'async with AsyncSessionLocal() as s:'"""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    @asynccontextmanager
    async def _ctx():
        yield mock_session

    mock_cls = MagicMock(return_value=_ctx())
    return mock_cls


# ── Tests ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_valid_simple_request_returns_200():
    """Test 1: Valid request, simple task → 200 with content + usage."""
    from app.main import app
    from app.db import get_db

    async def override_db():
        yield make_mock_db()

    app.dependency_overrides[get_db] = override_db

    with patch("app.routers.chat.route_request", new=AsyncMock(return_value=make_router_result())), \
         patch("app.routers.chat.call_provider", new=AsyncMock(return_value=make_provider_response())), \
         patch("app.routers.chat.check_budget", new=AsyncMock()), \
         patch("app.routers.chat.AsyncSessionLocal", new=make_async_session_local()):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/v1/chat", json=SIMPLE_BODY)

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    assert "usage" in data
    assert data["metadata"]["routed_to_tier"] == "cheap"


@pytest.mark.asyncio
async def test_complex_task_uses_smart_tier():
    """Test 2: Valid complex request → model_used is smart tier."""
    from app.main import app
    from app.db import get_db

    async def override_db():
        yield make_mock_db()

    app.dependency_overrides[get_db] = override_db

    with patch("app.routers.chat.route_request",
               new=AsyncMock(return_value=make_router_result("gpt-4o", "openai", "smart"))), \
         patch("app.routers.chat.call_provider", new=AsyncMock(return_value=make_provider_response())), \
         patch("app.routers.chat.check_budget", new=AsyncMock()), \
         patch("app.routers.chat.AsyncSessionLocal", new=make_async_session_local()):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/v1/chat", json=COMPLEX_BODY)

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["metadata"]["routed_to_tier"] == "smart"
    assert resp.json()["model_used"] == "gpt-4o"


@pytest.mark.asyncio
async def test_auto_short_message_uses_cheap_model():
    """Test 3: task_type='auto', short message → cheap model used."""
    from app.main import app
    from app.db import get_db

    async def override_db():
        yield make_mock_db()

    app.dependency_overrides[get_db] = override_db

    with patch("app.routers.chat.route_request",
               new=AsyncMock(return_value=make_router_result("gpt-4o-mini", "openai", "cheap"))), \
         patch("app.routers.chat.call_provider", new=AsyncMock(return_value=make_provider_response())), \
         patch("app.routers.chat.check_budget", new=AsyncMock()), \
         patch("app.routers.chat.AsyncSessionLocal", new=make_async_session_local()):

        body = {**SIMPLE_BODY, "task_type": "auto", "messages": [{"role": "user", "content": "Hi!"}]}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/v1/chat", json=body)

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["metadata"]["routed_to_tier"] == "cheap"


@pytest.mark.asyncio
async def test_budget_limit_zero_returns_402():
    """Test 4: Budget limit set to $0.00 → returns 402."""
    from app.main import app
    from app.db import get_db
    from app.exceptions import BudgetExceededException

    async def override_db():
        yield make_mock_db()

    app.dependency_overrides[get_db] = override_db

    with patch("app.routers.chat.check_budget",
               new=AsyncMock(side_effect=BudgetExceededException(0.05, 0.00, "test-user"))), \
         patch("app.routers.chat.AsyncSessionLocal", new=make_async_session_local()):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/v1/chat", json=SIMPLE_BODY)

    app.dependency_overrides.clear()

    assert resp.status_code == 402
    assert resp.json()["error"] == "budget_exceeded"


@pytest.mark.asyncio
async def test_missing_user_id_returns_422():
    """Test 5: Missing user_id → returns 422."""
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/v1/chat", json={
            "task_type": "simple",
            "messages": [{"role": "user", "content": "hello"}],
        })

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_provider_error_returns_502():
    """Test 6: Provider mock returns error → returns 502."""
    from app.main import app
    from app.db import get_db
    from app.exceptions import ProviderErrorException

    async def override_db():
        yield make_mock_db()

    app.dependency_overrides[get_db] = override_db

    with patch("app.routers.chat.route_request", new=AsyncMock(return_value=make_router_result())), \
         patch("app.routers.chat.call_provider",
               new=AsyncMock(side_effect=ProviderErrorException("openai", 500, "Internal error"))), \
         patch("app.routers.chat.check_budget", new=AsyncMock()), \
         patch("app.routers.chat.AsyncSessionLocal", new=make_async_session_local()):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/v1/chat", json=SIMPLE_BODY)

    app.dependency_overrides.clear()

    assert resp.status_code == 502
    assert resp.json()["error"] == "provider_error"


@pytest.mark.asyncio
async def test_20_messages_with_window_10_returns_was_sliced():
    """Test 7: 20-message history with window=10 → was_sliced=True in response."""
    from app.main import app
    from app.db import get_db

    async def override_db():
        yield make_mock_db()

    app.dependency_overrides[get_db] = override_db

    messages_20 = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
        for i in range(20)
    ]

    with patch("app.routers.chat.route_request", new=AsyncMock(return_value=make_router_result())), \
         patch("app.routers.chat.call_provider", new=AsyncMock(return_value=make_provider_response())), \
         patch("app.routers.chat.check_budget", new=AsyncMock()), \
         patch("app.routers.chat.AsyncSessionLocal", new=make_async_session_local()):

        body = {**SIMPLE_BODY, "messages": messages_20}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/v1/chat", json=body)

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["metadata"]["was_sliced"] is True
    assert resp.json()["metadata"]["messages_trimmed"] > 0
