import logging
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.common import APIResponse
from app.models.profile import ProfileDB, ProfileCreate, ProfileResponse, ProfileAnalyzeRequest
from app.services.profile_service import profile_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.post("/analyze", response_model=APIResponse[ProfileResponse])
async def analyze_profile(
    resume_file: Optional[UploadFile] = File(None),
    resume_text: Optional[str] = Form(None),
    user_id: Optional[str] = Form("user_default"),
    name: Optional[str] = Form(None),
    additional_notes: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload resume PDF or pass resume text to trigger Gemini structured career profile analysis."""
    try:
        pdf_bytes = None
        if resume_file:
            pdf_bytes = await resume_file.read()

        if not pdf_bytes and not resume_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either resume_file or resume_text must be provided.",
            )

        profile = await profile_service.analyze_and_create(
            db=db,
            resume_text=resume_text,
            pdf_bytes=pdf_bytes,
            user_id=user_id or "user_default",
            additional_notes=additional_notes or "",
            target_name=name,
        )

        return APIResponse.success_response(ProfileResponse.model_validate(profile))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze profile: {str(e)}",
        )


@router.get("/{profile_id}", response_model=APIResponse[ProfileResponse])
async def get_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve candidate career profile by ID or user_id."""
    profile = await profile_service.get_by_id(db, profile_id)
    if not profile:
        # Fallback check if it was user_id
        profile = await profile_service.get_by_user_id(db, profile_id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Career profile '{profile_id}' not found.",
        )

    return APIResponse.success_response(ProfileResponse.model_validate(profile))


@router.get("", response_model=APIResponse[List[ProfileResponse]])
async def list_profiles(
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List profiles, optionally filtered by user_id."""
    stmt = select(ProfileDB)
    if user_id:
        stmt = stmt.where(ProfileDB.user_id == user_id)
    result = await db.execute(stmt)
    profiles = result.scalars().all()
    return APIResponse.success_response([ProfileResponse.model_validate(p) for p in profiles])


@router.post("", response_model=APIResponse[ProfileResponse])
async def create_profile(
    profile_in: ProfileCreate,
    db: AsyncSession = Depends(get_db),
):
    """Manually create or seed a career profile."""
    profile = await profile_service.create_profile(db, profile_in)
    return APIResponse.success_response(ProfileResponse.model_validate(profile))
