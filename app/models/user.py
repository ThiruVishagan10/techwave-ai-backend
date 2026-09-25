import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Column, String, Boolean, DateTime

from app.db.base import Base


class UserDB(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    avatar_url = Column(String(512), nullable=True)
    role = Column(String(32), default="student", nullable=False)  # student, recruiter, admin
    auth_provider = Column(String(32), default="local", nullable=False)  # local, google
    google_id = Column(String(128), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# --- Pydantic Schemas ---

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    full_name: str = Field(..., min_length=2, description="Candidate or Recruiter full name")
    role: Optional[str] = "student"
    avatar_url: Optional[str] = None


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    credential: Optional[str] = Field(None, description="Google ID Token from Google One Tap / Sign-in button")
    id_token: Optional[str] = Field(None, description="Alternative field for Google ID Token")
    role: Optional[str] = Field("student", description="Role if auto-registering new account (default: student)")


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    profile_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
