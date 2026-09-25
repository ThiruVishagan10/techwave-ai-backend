import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.common import APIResponse
from app.models.recommendation import MatchRequest, MatchResponse
from app.services.recommendation_service import recommendation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["Recommendations & Matching"])


@router.post("/match", response_model=APIResponse[MatchResponse])
async def match_profile_opportunity(
    match_req: MatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Compare candidate profile with an opportunity and generate an explainable, multi-dimensional score."""
    try:
        result = await recommendation_service.match_single(
            db=db,
            profile_id=match_req.profile_id,
            opportunity_id=match_req.opportunity_id,
            force_refresh=match_req.force_refresh,
        )
        return APIResponse.success_response(MatchResponse.model_validate(result))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Matching error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Match evaluation failed: {str(e)}",
        )


@router.get("/{profile_id}", response_model=APIResponse[List[Dict[str, Any]]])
async def get_personalized_recommendations(
    profile_id: str,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve ranked, personalized recommendations for a candidate based on multi-objective alignment."""
    try:
        ranked_opps = await recommendation_service.get_ranked_recommendations(
            db=db,
            profile_id=profile_id,
            limit=limit,
        )
        return APIResponse.success_response(ranked_opps)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Recommendations error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendations: {str(e)}",
        )
