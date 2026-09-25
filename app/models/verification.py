import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, Float, DateTime, JSON

from app.db.base import Base


class VerificationDB(Base):
    __tablename__ = "verifications"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    opportunity_id = Column(String(64), nullable=False, index=True)
    status = Column(String(64), nullable=False)  # VERIFIED, NEEDS_REVIEW, SUSPICIOUS
    confidence = Column(Float, nullable=False)  # 0 to 100
    signals = Column(JSON, default=dict)
    risk_factors = Column(JSON, default=list)
    explanation = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# --- Pydantic Schemas ---

class VerificationSignals(BaseModel):
    company_information: bool = True
    official_domain: bool = True
    application_url: bool = True
    complete_description: bool = True
    deadline_detected: bool = True
    no_suspicious_payment: bool = True
    domain_consistency: bool = True


class VerificationAnalyzeRequest(BaseModel):
    opportunity_id: Optional[str] = None
    url: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    application_url: Optional[str] = None
    company_domain: Optional[str] = None
    force_refresh: bool = False


class VerificationResponse(BaseModel):
    id: Optional[str] = None
    opportunity_id: Optional[str] = None
    status: str  # VERIFIED, NEEDS_REVIEW, SUSPICIOUS
    confidence: float
    signals: Dict[str, Any] = Field(default_factory=dict)
    risk_factors: List[str] = Field(default_factory=list)
    explanation: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
