"""
app/services/provider.py — Async LLM provider calls.

Supports OpenAI and Anthropic. Uses httpx.AsyncClient.
Records latency_ms. Normalizes responses into a unified ProviderResponse.
Raises ProviderRateLimitException (429) or ProviderErrorException (other errors).
"""
import time
from dataclasses import dataclass
from typing import List, Optional

import httpx

from app.config import settings
from app.exceptions import ProviderErrorException, ProviderRateLimitException


@dataclass
class ProviderResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    status_code: int


def _openai_messages(messages: List[dict]) -> List[dict]:
    """OpenAI accepts messages as-is (role + content dicts)."""
    return [{"role": m["role"], "content": m["content"]} for m in messages]


def _anthropic_messages(messages: List[dict]):
    """
    Anthropic separates the system message from the messages array.
    Returns (system_prompt_str_or_None, filtered_messages).
    """
    system_prompt = None
    convo = []
    for m in messages:
        if m.get("role") == "system":
            system_prompt = m["content"]
        else:
            convo.append({"role": m["role"], "content": m["content"]})
    return system_prompt, convo


async def call_provider(
    model: str,
    provider: str,
    messages: List[dict],
    max_tokens: Optional[int] = None,
    temperature: float = 0.7,
) -> ProviderResponse:
    """
    Call the appropriate LLM provider and return a normalized ProviderResponse.

    Raises:
        ProviderRateLimitException: on HTTP 429
        ProviderErrorException:     on any other non-2xx response
    """
    if provider == "openai":
        return await _call_openai(model, messages, max_tokens, temperature)
    elif provider == "anthropic":
        return await _call_anthropic(model, messages, max_tokens, temperature)
    else:
        raise ProviderErrorException(
            provider=provider,
            status_code=0,
            message=f"Unknown provider: {provider}",
        )


async def _call_openai(
    model: str,
    messages: List[dict],
    max_tokens: Optional[int],
    temperature: float,
) -> ProviderResponse:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": _openai_messages(messages),
        "temperature": temperature,
    }
    if max_tokens:
        body["max_tokens"] = max_tokens

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=body)
    latency_ms = int((time.monotonic() - start) * 1000)

    _raise_if_error(resp, "openai")

    data = resp.json()
    usage = data.get("usage", {})
    return ProviderResponse(
        content=data["choices"][0]["message"]["content"],
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
        latency_ms=latency_ms,
        status_code=resp.status_code,
    )


async def _call_anthropic(
    model: str,
    messages: List[dict],
    max_tokens: Optional[int],
    temperature: float,
) -> ProviderResponse:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    system_prompt, convo = _anthropic_messages(messages)
    body = {
        "model": model,
        "messages": convo,
        "max_tokens": max_tokens or 1024,
        "temperature": temperature,
    }
    if system_prompt:
        body["system"] = system_prompt

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=body)
    latency_ms = int((time.monotonic() - start) * 1000)

    _raise_if_error(resp, "anthropic")

    data = resp.json()
    usage = data.get("usage", {})
    return ProviderResponse(
        content=data["content"][0]["text"],
        prompt_tokens=usage.get("input_tokens", 0),
        completion_tokens=usage.get("output_tokens", 0),
        total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        latency_ms=latency_ms,
        status_code=resp.status_code,
    )


def _raise_if_error(resp: httpx.Response, provider: str) -> None:
    """Raise appropriate exceptions for non-2xx responses."""
    if resp.status_code == 429:
        raise ProviderRateLimitException(provider=provider)
    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise ProviderErrorException(
            provider=provider,
            status_code=resp.status_code,
            message=str(detail),
        )
