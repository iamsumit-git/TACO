
# 🌮 TACO — LLM Token Analytics & Cost Optimizer

TACO is a full-stack platform for optimizing, monitoring, and controlling costs when using Large Language Models (LLMs) in production. It acts as a smart proxy between your application and LLM providers (OpenAI, Anthropic, Google), providing:

- **Token usage tracking:** Every request is counted and logged, with detailed analytics on tokens, costs, and latency.
- **Smart routing:** Requests are automatically routed to the cheapest suitable model based on your requirements and provider pricing.
- **Context window management:** Oversized prompts are trimmed using a context slicer to fit model limits and reduce cost.
- **Budget enforcement:** Per-user and per-org spend limits are enforced, blocking requests (HTTP 402) when budgets are exceeded.
- **Cost logging:** All requests are logged with cost breakdowns, model selection, and error codes for audit and analysis.
- **Analytics dashboard:** A React-based dashboard shows KPIs, charts, model breakdowns, and request logs for real-time monitoring.

## How TACO Works

1. **Your app sends a chat/completion request to TACO's `/v1/chat` endpoint.**
2. **TACO estimates token usage and cost for the request.**
3. **Budget check:** If the user/org is over budget, the request is blocked (HTTP 402).
4. **Context slicing:** If the prompt is too large, TACO slices it to fit the model's context window.
5. **Smart routing:** TACO selects the cheapest model that meets the requirements (provider, tier, context size).
6. **Provider call:** TACO sends the request to the chosen LLM provider (OpenAI, Anthropic, Google) asynchronously.
7. **Cost logging:** The response, token usage, and cost are logged in the database.
8. **Response:** TACO returns the LLM response to your app, with metadata on cost, model, and slicing.
9. **Analytics:** All requests and costs are available via API endpoints and the dashboard for analysis.

## Features

- **Multi-provider support:** OpenAI, Anthropic, Google Gemini (add more easily)
- **Async FastAPI backend:** High performance, scalable, and easy to extend
- **PostgreSQL database:** Stores all requests, costs, and analytics data
- **React dashboard:** Real-time KPIs, charts, and logs for admins and users
- **Dockerized:** Easy local and production deployment
- **Configurable budgets, models, and routing logic**

## Example Flow

1. User sends a chat request (e.g., "Summarize this document")
2. TACO estimates tokens, checks budget, slices context if needed
3. TACO routes to the cheapest model (e.g., OpenAI GPT-4o-mini)
4. Provider returns response; TACO logs cost and analytics
5. User/admin views dashboard for spend, usage, and request history

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI · SQLAlchemy (async) · uvicorn |
| Database | PostgreSQL 15 (Docker) |
| Token Counting | tiktoken (OpenAI) · char heuristic (Anthropic/Google) |
| HTTP Client | httpx (async) |
| Frontend | React + Vite · TypeScript · Recharts · TailwindCSS |
| Infra | Docker Compose |

## Quick Start (Development)

### 1. Start the database
```bash
cd infra
docker compose up -d taco-postgres

# command to check tables and model pricing
 docker exec taco-postgres psql -U taco -d tacodev -c "\dt"; docker exec taco-postgres psql -U taco -d tacodev -c "SELECT model, tier FROM model_pricing ORDER BY tier, provider;"
```

### 2. Start the backend
```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. Start the frontend
```bash
cd frontend
pnpm install
pnpm dev
```

### 4. Full stack (Docker Compose)
```bash
cd infra
docker compose up --build -d
# Frontend → http://localhost:3000
# Backend  → http://localhost:8000
```

## Smoke Test & Health Verification

After all containers are running and healthy:

1. **Check health endpoint:**
	- `curl http://localhost:8000/health` should return `{status: ok, db: connected, version: ...}`
2. **Test chat endpoint:**
	- POST to `/v1/chat` with valid payloads (simple, complex, auto-detect)
3. **Verify analytics endpoints:**
	- GET `/analytics/overview`, `/analytics/timeseries`, `/analytics/requests` for expected data
4. **Check dashboard:**
	- Open [http://localhost:3000](http://localhost:3000) and confirm KPIs, charts, pagination, and budget/context slicing features
5. **Error handling:**
	- Confirm 402 (budget block), 413/422/502/503 errors are handled gracefully

If any service is not healthy, check logs with:
```bash
docker compose logs backend
docker compose logs frontend
docker compose logs postgres
```

## Project Structure

```
taco/
├── backend/          FastAPI app + services + tests
├── frontend/         React + Vite dashboard
├── infra/            docker-compose.yml + init.sql
└── README.md
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | /health | Health check |
| POST | /v1/chat | LLM proxy with cost tracking |
| GET | /analytics/overview | Spend summary |
| GET | /analytics/timeseries | Daily cost trend |
| GET | /analytics/requests | Paginated request log |


## 🔐 Data & Privacy

TACO is designed to be self-hosted. This means:

- **Your API keys** are stored in your own `.env` file on your own server. They are never transmitted to any external service other than the LLM provider you configured.
- **Your prompts and completions** are not stored by default. TACO only logs metadata: model used, token counts, cost, latency, and your `user_id` tag.
- **Your database** runs in a Docker container on your own infrastructure. No data is sent to TACO's servers — because there are no TACO servers.
- **You can delete everything** by running `docker compose down -v`. Clean slate.

If you enable prompt logging for debugging, that data lives exclusively in your Postgres instance. You control retention, access, and deletion entirely.
