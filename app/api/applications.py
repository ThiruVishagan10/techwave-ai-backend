import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.common import APIResponse
from app.models.application import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationResponse,
)
from app.services.application_service import application_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/applications", tags=["Applications"])


@router.get("/{profile_id}", response_model=APIResponse[List[Dict[str, Any]]])
async def get_applications_by_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all tracked applications for a student profile."""
    apps = await application_service.get_by_profile_id(db, profile_id)
    return APIResponse.success_response(apps)


@router.post("", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED)
async def create_application(
    app_in: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create or update an application status (SAVED, APPLIED, INTERVIEW, REJECTED, OFFER)."""
    try:
        app_rec = await application_service.create_or_update_application(db, app_in)
        return APIResponse.success_response(app_rec)
    except Exception as e:
        logger.error(f"Error creating application: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record application: {str(e)}",
        )


@router.patch("/{application_id}", response_model=APIResponse[Dict[str, Any]])
async def update_application(
    application_id: str,
    app_update: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update application stage or notes."""
    updated = await application_service.update_by_id(db, application_id, app_update)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' not found.",
        )
    return APIResponse.success_response(updated)


@router.delete("/{application_id}", response_model=APIResponse[dict])
async def delete_application(
    application_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove an application or saved item."""
    success = await application_service.delete_by_id(db, application_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' not found.",
        )
    return APIResponse.success_response({"message": "Application removed successfully."})
