import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.common import APIResponse
from app.models.verification import VerificationAnalyzeRequest, VerificationResponse, VerificationDB
from app.models.opportunity import OpportunityDB
from app.ai.verifier import verifier
from app.core.security import extract_domain

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/verification", tags=["Verification"])


@router.post("/analyze", response_model=APIResponse[VerificationResponse])
async def analyze_opportunity_verification(
    req: VerificationAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Analyze an opportunity or external URL for trust, scam signals, and domain authenticity."""
    try:
        opp_data = {}
        target_opp_id = req.opportunity_id

        # If opportunity_id was provided, look it up in DB
        if target_opp_id:
            res = await db.execute(select(OpportunityDB).where(OpportunityDB.id == target_opp_id))
            opp = res.scalar_one_or_none()
            if not opp:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Opportunity '{target_opp_id}' not found.",
                )
            
            # Check cached verification in DB if not force_refresh
            if not req.force_refresh:
                v_res = await db.execute(
                    select(VerificationDB)
                    .where(VerificationDB.opportunity_id == target_opp_id)
                    .order_by(VerificationDB.created_at.desc())
                )
                cached = v_res.scalars().first()
                if cached:
                    return APIResponse.success_response(
                        VerificationResponse(
                            id=cached.id,
                            opportunity_id=cached.opportunity_id,
                            status=cached.status,
                            confidence=cached.confidence,
                            signals=cached.signals or {},
                            risk_factors=cached.risk_factors or [],
                            explanation=cached.explanation,
                            created_at=cached.created_at,
                        )
                    )

            opp_data = {
                "id": opp.id,
                "company": opp.company,
                "title": opp.title,
                "description": opp.description,
                "company_domain": opp.company_domain,
                "source_url": opp.source_url,
                "application_url": opp.application_url,
                "salary": opp.salary,
                "deadline": opp.deadline,
                "eligibility": opp.eligibility,
            }
        else:
            # External or ad-hoc URL analysis
            domain = req.company_domain or extract_domain(req.url or req.application_url or req.source_url)
            opp_data = {
                "company": req.company or (domain.split(".")[0].capitalize() if domain else "Unknown Company"),
                "title": req.title or "Job / Internship Posting",
                "description": req.description or f"Job opportunity verification check for {domain}",
                "company_domain": domain,
                "source_url": req.source_url or req.url,
                "application_url": req.application_url or req.url,
                "salary": None,
                "deadline": None,
                "eligibility": None,
            }

        # Run AI verification
        analysis = await verifier.analyze_opportunity(opp_data)

        # If opportunity_id exists, save or update to DB
        verif_id = None
        if target_opp_id:
            verif_rec = VerificationDB(
                opportunity_id=target_opp_id,
                status=analysis["status"],
                confidence=analysis["confidence"],
                signals=analysis["signals"],
                risk_factors=analysis["risk_factors"],
                explanation=analysis["explanation"],
            )
            db.add(verif_rec)

            # Also update opportunity table
            opp.verification_status = analysis["status"]
            opp.verification_score = analysis["confidence"]
            await db.commit()
            await db.refresh(verif_rec)
            verif_id = verif_rec.id

        return APIResponse.success_response(
            VerificationResponse(
                id=verif_id,
                opportunity_id=target_opp_id,
                status=analysis["status"],
                confidence=analysis["confidence"],
                signals=analysis["signals"],
                risk_factors=analysis["risk_factors"],
                explanation=analysis["explanation"],
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification analysis failed: {str(e)}",
        )
