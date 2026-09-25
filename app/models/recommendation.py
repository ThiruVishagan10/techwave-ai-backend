import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, Float, DateTime, JSON

from app.db.base import Base


class RecommendationDB(Base):
    __tablename__ = "recommendations"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String(64), nullable=False, index=True)
    opportunity_id = Column(String(64), nullable=False, index=True)
    match_score = Column(Float, nullable=False)
    skills_score = Column(Float, nullable=False)
    experience_score = Column(Float, nullable=False)
    education_score = Column(Float, nullable=False)
    preference_score = Column(Float, nullable=False)
    career_alignment_score = Column(Float, nullable=False)
    matched_skills = Column(JSON, default=list)
    skill_gaps = Column(JSON, default=list)
    explanation = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# --- Pydantic Schemas ---

class MatchRequest(BaseModel):
    profile_id: str
    opportunity_id: str
    force_refresh: bool = False


class MatchResponse(BaseModel):
    id: Optional[str] = None
    profile_id: str
    opportunity_id: str
    match_score: float
    skills_score: float
    experience_score: float
    education_score: float
    preference_score: float
    career_alignment_score: float
    matched_skills: List[str] = Field(default_factory=list)
    skill_gaps: List[str] = Field(default_factory=list)
    explanation: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
