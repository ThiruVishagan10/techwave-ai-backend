import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, Float, DateTime, JSON
from sqlalchemy.orm import declarative_base

from app.db.base import Base


class ProfileDB(Base):
    __tablename__ = "profiles"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), index=True, default="user_default")
    name = Column(String(255), nullable=False)
    education = Column(JSON, default=list)
    skills = Column(JSON, default=dict)
    experience = Column(JSON, default=list)
    projects = Column(JSON, default=list)
    career_interests = Column(JSON, default=list)
    preferred_locations = Column(JSON, default=list)
    preferred_work_modes = Column(JSON, default=list)
    preferred_opportunity_types = Column(JSON, default=list)
    resume_text = Column(Text, nullable=True)
    profile_strength = Column(Float, default=70.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# --- Pydantic Schemas ---

class EducationItem(BaseModel):
    degree: Optional[str] = None
    field: Optional[str] = None
    university: Optional[str] = None
    batch: Optional[str] = None
    gpa: Optional[str] = None


class ExperienceItem(BaseModel):
    role: Optional[str] = None
    organization: Optional[str] = None
    period: Optional[str] = None
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    impact: Optional[str] = None


class ProfileAnalyzeRequest(BaseModel):
    resume_text: Optional[str] = None
    user_id: Optional[str] = "user_default"
    name: Optional[str] = None
    additional_notes: Optional[str] = None


class ProfileCreate(BaseModel):
    user_id: Optional[str] = "user_default"
    name: str
    education: List[Union[EducationItem, Dict[str, Any]]] = Field(default_factory=list)
    skills: Union[List[str], Dict[str, List[str]]] = Field(default_factory=dict)
    experience: List[Union[ExperienceItem, Dict[str, Any]]] = Field(default_factory=list)
    projects: List[Union[ProjectItem, Dict[str, Any]]] = Field(default_factory=list)
    career_interests: List[str] = Field(default_factory=list)
    preferred_locations: List[str] = Field(default_factory=list)
    preferred_work_modes: List[str] = Field(default_factory=list)
    preferred_opportunity_types: List[str] = Field(default_factory=list)
    resume_text: Optional[str] = None
    profile_strength: Optional[float] = 75.0


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    name: str
    education: List[Any] = Field(default_factory=list)
    skills: Any = Field(default_factory=dict)
    experience: List[Any] = Field(default_factory=list)
    projects: List[Any] = Field(default_factory=list)
    career_interests: List[str] = Field(default_factory=list)
    preferred_locations: List[str] = Field(default_factory=list)
    preferred_work_modes: List[str] = Field(default_factory=list)
    preferred_opportunity_types: List[str] = Field(default_factory=list)
    resume_text: Optional[str] = None
    profile_strength: float
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
