import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.common import APIResponse
from app.models.opportunity import (
    OpportunityCreate,
    OpportunityResponse,
    OpportunityFilterParams,
)
from app.services.opportunity_service import opportunity_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])


@router.get("", response_model=APIResponse[List[OpportunityResponse]])
async def list_opportunities(
    search: Optional[str] = Query(None, description="Search term for title, company, or description"),
    location: Optional[str] = Query(None, description="Filter by location"),
    work_mode: Optional[str] = Query(None, description="Filter by work mode (Remote, Hybrid, On-site)"),
    opportunity_type: Optional[str] = Query(None, description="Filter by type (Internship, Full-time)"),
    verification_status: Optional[str] = Query(None, description="Filter by status (VERIFIED, NEEDS_REVIEW, SUSPICIOUS)"),
    minimum_match: Optional[float] = Query(None, description="Minimum match percentage"),
    skills: Optional[str] = Query(None, description="Comma-separated skill keywords"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve and filter opportunities with rich faceted parameters."""
    filters = OpportunityFilterParams(
        search=search,
        location=location,
        work_mode=work_mode,
        opportunity_type=opportunity_type,
        verification_status=verification_status,
        minimum_match=minimum_match,
        skills=skills,
        limit=limit,
        offset=offset,
    )
    items = await opportunity_service.get_opportunities(db, filters)
    return APIResponse.success_response([OpportunityResponse.model_validate(item) for item in items])


@router.get("/{opportunity_id}", response_model=APIResponse[OpportunityResponse])
async def get_opportunity(
    opportunity_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details for a single opportunity by ID."""
    opp = await opportunity_service.get_by_id(db, opportunity_id)
    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Opportunity '{opportunity_id}' not found.",
        )
    return APIResponse.success_response(OpportunityResponse.model_validate(opp))


@router.post("", response_model=APIResponse[OpportunityResponse], status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    opp_in: OpportunityCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new job or internship opportunity."""
    opp = await opportunity_service.create(db, opp_in)
    return APIResponse.success_response(OpportunityResponse.model_validate(opp))


@router.post("/{opportunity_id}/verify", response_model=APIResponse[dict])
async def verify_opportunity(
    opportunity_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI verification and trust signal analysis for an existing opportunity."""
    try:
        result = await opportunity_service.verify_opportunity_by_id(db, opportunity_id)
        return APIResponse.success_response(result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Verification error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/actions/seed", response_model=APIResponse[dict])
async def seed_opportunities_endpoint(
    db: AsyncSession = Depends(get_db),
):
    """Utility endpoint to seed default hackathon opportunities into the database."""
    count = await opportunity_service.seed_from_file(db)
    return APIResponse.success_response({"message": f"Successfully seeded {count} opportunities."})
