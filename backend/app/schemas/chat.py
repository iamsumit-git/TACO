"""
app/schemas/chat.py — Pydantic request/response shapes for /v1/chat.
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="Required caller identifier")
    org_id: Optional[str] = None
    task_type: Literal["simple", "complex", "auto"] = "auto"
    model: Optional[str] = None
    messages: List[Message] = Field(..., min_length=1)
    max_tokens: Optional[int] = None
    temperature: float = 0.7


class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float


class ResponseMetadata(BaseModel):
    was_sliced: bool
    messages_trimmed: int
    latency_ms: int
    routed_to_tier: Literal["cheap", "smart"]


class ChatResponse(BaseModel):
    id: str
    model_used: str
    content: str
    usage: UsageInfo
    metadata: ResponseMetadata
