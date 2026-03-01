"""
app/models/model_pricing.py — ORM model for model_pricing table.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Numeric, Integer, String

from app.db import Base


class ModelPricing(Base):
    __tablename__ = "model_pricing"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False, unique=True)
    tier = Column(String(20), nullable=False)           # 'cheap' | 'smart'
    input_cost_per_1k = Column(Numeric(10, 8), nullable=False)
    output_cost_per_1k = Column(Numeric(10, 8), nullable=False)
    context_window = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
