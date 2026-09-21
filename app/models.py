from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from app.db.postgres import Base

class VirtualKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_hash = Column(String, unique=True, index=True, nullable=False)
    budget_tokens = Column(Integer, default=10000)
    used_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    gateway_key_hash = Column(String, index=True, nullable=False)
    model = Column(String, nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow)
