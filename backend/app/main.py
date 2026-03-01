"""
app/main.py — FastAPI application entry point.
Registers routers, CORS middleware, global exception handlers, and /health.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.db import AsyncSessionLocal
from app.exceptions import (
    BudgetExceededException,
    ContextTooLargeException,
    NoModelAvailableException,
    ProviderErrorException,
    ProviderRateLimitException,
)
from app.routers import chat, analytics

# ── App instance ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="TACO — LLM Token Analytics & Cost Optimizer",
    description="Middleware proxy that tracks token usage and routes LLM requests cost-efficiently.",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # Docker nginx
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(chat.router)
app.include_router(analytics.router)


# ── Global Exception Handlers ─────────────────────────────────────────────────
@app.exception_handler(BudgetExceededException)
async def budget_exceeded_handler(request: Request, exc: BudgetExceededException):
    return JSONResponse(
        status_code=402,
        content={
            "error": "budget_exceeded",
            "spent_usd": exc.spent_usd,
            "limit_usd": exc.limit_usd,
            "entity_id": exc.entity_id,
            "prompt_tokens": exc.prompt_tokens,
        },
    )


@app.exception_handler(ContextTooLargeException)
async def context_too_large_handler(request: Request, exc: ContextTooLargeException):
    return JSONResponse(
        status_code=413,
        content={
            "error": "context_too_large",
            "estimated_tokens": exc.estimated_tokens,
            "context_window": exc.context_window,
            "model": exc.model,
        },
    )


@app.exception_handler(ProviderRateLimitException)
async def rate_limit_handler(request: Request, exc: ProviderRateLimitException):
    return JSONResponse(
        status_code=429,
        content={"error": "provider_rate_limit", "provider": exc.provider},
    )


@app.exception_handler(ProviderErrorException)
async def provider_error_handler(request: Request, exc: ProviderErrorException):
    return JSONResponse(
        status_code=502,
        content={
            "error": "provider_error",
            "provider": exc.provider,
            "status_code": exc.status_code,
            "message": exc.message,
        },
    )


@app.exception_handler(NoModelAvailableException)
async def no_model_handler(request: Request, exc: NoModelAvailableException):
    return JSONResponse(
        status_code=503,
        content={"error": "no_model_available", "tier": exc.tier},
    )


# ── Health Endpoint ────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
async def health_check():
    """Returns service status and DB connectivity."""
    db_status = "disconnected"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "db": db_status,
        "version": settings.app_version,
    }
