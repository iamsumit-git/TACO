"""
app/models/request_log.py — ORM model for request_logs table.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Numeric, Integer, Text, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db import Base


class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    org_id = Column(String(255), nullable=True)
    task_type = Column(String(50), nullable=True)
    provider = Column(String(50), nullable=True)
    model_requested = Column(String(100), nullable=True)
    model_used = Column(String(100), nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    cost_usd = Column(Numeric(10, 8), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    was_sliced = Column(Boolean, default=False)
    messages_original_count = Column(Integer, nullable=True)
    messages_sent_count = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
