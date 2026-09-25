import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, Float, DateTime, JSON

from app.db.base import Base


class OpportunityDB(Base):
    __tablename__ = "opportunities"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    company = Column(String(255), nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    location = Column(String(255), nullable=False)
    work_mode = Column(String(64), nullable=False)  # Remote, Hybrid, On-site
    opportunity_type = Column(String(64), nullable=False)  # Internship, Full-time, Part-time
    skills = Column(JSON, default=list)  # List[str]
    eligibility = Column(Text, nullable=True)
    salary = Column(String(255), nullable=True)  # Stipend / salary
    deadline = Column(String(255), nullable=True)
    source_url = Column(String(1024), nullable=True)
    application_url = Column(String(1024), nullable=True)
    company_domain = Column(String(255), nullable=True)
    verification_status = Column(String(64), default="VERIFIED")  # VERIFIED, NEEDS_REVIEW, SUSPICIOUS
    verification_score = Column(Float, default=90.0)

    # Extra enriched fields for frontend UI alignment
    company_logo_color = Column(String(64), nullable=True)
    company_initial = Column(String(16), nullable=True)
    duration = Column(String(64), nullable=True)
    responsibilities = Column(JSON, default=list)
    requirements = Column(JSON, default=list)
    benefits = Column(JSON, default=list)
    verification_checks = Column(JSON, default=list)
    posted_days_ago = Column(Float, default=1.0)
    embedding = Column(JSON, nullable=True)  # Cached vector if pgvector/embedding is computed

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# --- Pydantic Schemas ---

class VerificationCheckItem(BaseModel):
    id: str
    label: str
    status: str  # pass, warning, fail
    detail: str
    timestamp: Optional[str] = None


class OpportunityBase(BaseModel):
    company: str
    title: str
    description: str
    location: str
    work_mode: str
    opportunity_type: str
    skills: List[str] = Field(default_factory=list)
    eligibility: Optional[str] = None
    salary: Optional[str] = None
    deadline: Optional[str] = None
    source_url: Optional[str] = None
    application_url: Optional[str] = None
    company_domain: Optional[str] = None
    verification_status: Optional[str] = "VERIFIED"
    verification_score: Optional[float] = 90.0
    company_logo_color: Optional[str] = None
    company_initial: Optional[str] = None
    duration: Optional[str] = "3-6 months"
    responsibilities: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)
    verification_checks: List[VerificationCheckItem] = Field(default_factory=list)


class OpportunityCreate(OpportunityBase):
    pass


class OpportunityResponse(OpportunityBase):
    id: str
    posted_days_ago: Optional[float] = 1.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Dynamic fields computed during match/recommendations
    match_score: Optional[float] = None
    matched_skills: Optional[List[str]] = None
    missing_skills: Optional[List[str]] = None
    ai_explanation: Optional[str] = None
    why_recommended_reasons: Optional[List[str]] = None
    match_breakdown: Optional[Dict[str, float]] = None

    model_config = {"from_attributes": True}


class OpportunityFilterParams(BaseModel):
    search: Optional[str] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None
    opportunity_type: Optional[str] = None
    verification_status: Optional[str] = None
    minimum_match: Optional[float] = None
    skills: Optional[str] = None  # Comma separated
    limit: int = 50
    offset: int = 0
