"""
app/services/estimator.py — Token counting for LLM requests.

Strategy:
  - gpt-*    → tiktoken (exact)
  - claude-* → character / 4 heuristic (Anthropic approximation)
  - gemini-* → character / 4 heuristic
  - +4 tokens per message for role/format framing (OpenAI standard)
"""
from typing import List, Literal
from dataclasses import dataclass

import tiktoken


@dataclass
class EstimatorResult:
    estimated_tokens: int
    model: str
    method: Literal["tiktoken", "heuristic"]


def estimate_tokens(messages: List[dict], model: str) -> EstimatorResult:
    """
    Estimate total token count for a list of messages given a model name.

    Each message dict must have at least a 'content' key (string).
    Role framing overhead: +4 tokens per message.

    Returns an EstimatorResult with the estimated count, model name, and method used.
    """
    per_message_overhead = 4
    total_tokens = 0

    if model.startswith("gpt-"):
        # Use tiktoken for exact counting
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base if exact model not found
            enc = tiktoken.get_encoding("cl100k_base")

        for msg in messages:
            content = msg.get("content", "")
            tokens = len(enc.encode(content))
            total_tokens += tokens + per_message_overhead

        return EstimatorResult(
            estimated_tokens=total_tokens,
            model=model,
            method="tiktoken",
        )

    else:
        # Heuristic for claude-* and gemini-* (and any unknown model)
        for msg in messages:
            content = msg.get("content", "")
            tokens = max(1, len(content) // 4)
            total_tokens += tokens + per_message_overhead

        return EstimatorResult(
            estimated_tokens=total_tokens,
            model=model,
            method="heuristic",
        )
