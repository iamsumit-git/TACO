"""
app/models/budget.py — ORM model for budgets table.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db import Base


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(20), nullable=False)   # 'user' | 'org'
    entity_id = Column(String(255), nullable=False)
    limit_usd = Column(Numeric(10, 4), nullable=False)
    period = Column(String(20), nullable=False)         # 'daily' | 'weekly' | 'monthly'
    action = Column(String(20), nullable=False)         # 'block' | 'alert'
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
