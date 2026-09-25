import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, DateTime, JSON

from app.db.base import Base


class ApplicationDB(Base):
    __tablename__ = "applications"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String(64), nullable=False, index=True)
    opportunity_id = Column(String(64), nullable=False, index=True)
    status = Column(String(64), nullable=False, default="APPLIED")  # SAVED, APPLIED, INTERVIEW, REJECTED, OFFER
    applied_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    notes = Column(Text, nullable=True)
    metadata_info = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# --- Pydantic Schemas ---

class ApplicationCreate(BaseModel):
    profile_id: str
    opportunity_id: str
    status: str = "APPLIED"  # SAVED, APPLIED, INTERVIEW, REJECTED, OFFER
    notes: Optional[str] = None
    applied_at: Optional[datetime] = None


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None  # SAVED, APPLIED, INTERVIEW, REJECTED, OFFER
    notes: Optional[str] = None


class ApplicationResponse(BaseModel):
    id: str
    profile_id: str
    opportunity_id: str
    status: str
    applied_at: Optional[datetime] = None
    notes: Optional[str] = None
    metadata_info: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Opportunity details joined for frontend display convenience
    opportunity: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}
