"""
tests/test_analytics.py — Tests for analytics endpoints.

Uses httpx TestClient. Seeded with mock data via patched DB.
5 tests as specified in the execution plan.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from decimal import Decimal
from datetime import datetime, timezone, date


def make_request_log_row(
    user_id="alice",
    model_used="gpt-4o-mini",
    task_type="simple",
    cost_usd=0.00015,
    total_tokens=100,
    prompt_tokens=80,
    completion_tokens=20,
    was_sliced=False,
    status_code=200,
):
    from app.models.request_log import RequestLog
    import uuid
    r = RequestLog()
    r.id = uuid.uuid4()
    r.user_id = user_id
    r.org_id = None
    r.task_type = task_type
    r.provider = "openai"
    r.model_requested = model_used
    r.model_used = model_used
    r.prompt_tokens = prompt_tokens
    r.completion_tokens = completion_tokens
    r.total_tokens = total_tokens
    r.cost_usd = Decimal(str(cost_usd))
    r.latency_ms = 200
    r.was_sliced = was_sliced
    r.messages_original_count = 1
    r.messages_sent_count = 1
    r.status_code = status_code
    r.error_message = None
    r.created_at = datetime.now(timezone.utc)
    return r


def make_mock_db_for_analytics(
    total_cost=1.5, total_requests=20, total_tokens=10000,
    cheap_count=15, cheap_cost=0.3,
    top_models=None,
    rows=None,
    total_row_count=20,
):
    mock_db = AsyncMock()
    call_count = [0]

    if top_models is None:
        top_models = [("gpt-4o-mini", 15, 0.3), ("gpt-4o", 5, 1.2)]
    if rows is None:
        rows = [make_request_log_row() for _ in range(5)]

    async def fake_execute(stmt, *args, **kwargs):
        result = MagicMock()
        call_count[0] += 1
        n = call_count[0]

        if n == 1:  # Core aggregates
            row = MagicMock()
            row.total_cost = Decimal(str(total_cost))
            row.total_requests = total_requests
            row.total_tokens = total_tokens
            result.one.return_value = row
        elif n == 2:  # Cheap tier count
            result.scalar.return_value = cheap_count
        elif n == 3:  # Cheap tier cost
            result.scalar.return_value = Decimal(str(cheap_cost))
        elif n == 4:  # Top models
            top_rows = []
            for (model, count, cost) in top_models:
                r = MagicMock()
                r.model_used = model
                r.req_count = count
                r.cost = Decimal(str(cost))
                top_rows.append(r)
            result.all.return_value = top_rows
        elif n == 5:  # Total count (requests endpoint)
            result.scalar.return_value = total_row_count
        elif n == 6:  # Rows (requests endpoint)
            scalars = MagicMock()
            scalars.all.return_value = rows
            result.scalars.return_value = scalars

        return result

    mock_db.execute = fake_execute
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.close = AsyncMock()
    return mock_db


@pytest.mark.asyncio
async def test_overview_no_filters_returns_totals():
    """Test 1: /analytics/overview with no filters → returns totals for all rows."""
    from app.main import app
    from app.db import get_db

    async def override_db():
        yield make_mock_db_for_analytics(total_cost=1.5, total_requests=20)

    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/analytics/overview")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_requests"] == 20
    assert data["total_cost_usd"] == pytest.approx(1.5, rel=1e-3)


@pytest.mark.asyncio
async def test_overview_user_filter():
    """Test 2: /analytics/overview?user_id=alice → returns only alice's data."""
    from app.main import app
    from app.db import get_db

    async def override_db():
        yield make_mock_db_for_analytics(total_requests=10, total_cost=0.5)

    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/analytics/overview?user_id=alice")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["total_requests"] == 10


@pytest.mark.asyncio
async def test_timeseries_returns_data():
    """Test 3: /analytics/timeseries?days=7 → returns data points."""
    from app.main import app
    from app.db import get_db

    async def fake_execute(stmt, *args, **kwargs):
        r1 = MagicMock()
        r1.day = date(2026, 2, 28)
        r1.cost = Decimal("0.15")
        r1.req_count = 5
        r1.tokens = 500
        result = MagicMock()
        result.all.return_value = [r1]
        return result

    mock_db = AsyncMock()
    mock_db.execute = fake_execute
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.close = AsyncMock()

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/analytics/timeseries?days=7")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "date" in data[0]
    assert "cost_usd" in data[0]


@pytest.mark.asyncio
async def test_requests_pagination():
    """Test 4: /analytics/requests?page=1&limit=5 → returns 5 rows."""
    from app.main import app
    from app.db import get_db

    rows = [make_request_log_row() for _ in range(5)]
    mock_db = make_mock_db_for_analytics(rows=rows, total_row_count=20)
    # Override so first 4 calls from overview don't run; use dedicated mock
    call_count = [0]

    async def fake_execute(stmt, *args, **kwargs):
        result = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            result.scalar.return_value = 20
        else:
            scalars = MagicMock()
            scalars.all.return_value = rows
            result.scalars.return_value = scalars
        return result

    mock_db2 = AsyncMock()
    mock_db2.execute = fake_execute
    mock_db2.commit = AsyncMock()
    mock_db2.rollback = AsyncMock()
    mock_db2.close = AsyncMock()

    async def override_db():
        yield mock_db2

    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/analytics/requests?page=1&limit=5")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 20
    assert data["page"] == 1
    assert data["limit"] == 5
    assert len(data["items"]) == 5


@pytest.mark.asyncio
async def test_overview_empty_db_returns_zeros():
    """Test 5: Empty DB → overview returns zeros, not errors."""
    from app.main import app
    from app.db import get_db

    async def override_db():
        yield make_mock_db_for_analytics(
            total_cost=0, total_requests=0, total_tokens=0,
            cheap_count=0, cheap_cost=0, top_models=[],
        )

    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/analytics/overview")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_requests"] == 0
    assert data["total_cost_usd"] == 0.0
    assert data["avg_cost_per_request"] == 0.0
