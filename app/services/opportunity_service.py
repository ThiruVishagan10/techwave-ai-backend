import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, desc

from app.models.opportunity import (
    OpportunityDB,
    OpportunityCreate,
    OpportunityFilterParams,
)
from app.ai.verifier import verifier
from app.models.verification import VerificationDB

logger = logging.getLogger(__name__)


class OpportunityService:
    @staticmethod
    async def get_opportunities(
        db: AsyncSession,
        filters: OpportunityFilterParams,
    ) -> List[OpportunityDB]:
        """Query opportunities with comprehensive filtering."""
        stmt = select(OpportunityDB)
        conditions = []

        if filters.search:
            search_pattern = f"%{filters.search.strip()}%"
            conditions.append(
                or_(
                    OpportunityDB.title.ilike(search_pattern),
                    OpportunityDB.company.ilike(search_pattern),
                    OpportunityDB.description.ilike(search_pattern),
                )
            )

        if filters.location:
            conditions.append(OpportunityDB.location.ilike(f"%{filters.location.strip()}%"))

        if filters.work_mode:
            conditions.append(OpportunityDB.work_mode.ilike(f"%{filters.work_mode.strip()}%"))

        if filters.opportunity_type:
            conditions.append(OpportunityDB.opportunity_type.ilike(f"%{filters.opportunity_type.strip()}%"))

        if filters.verification_status:
            conditions.append(OpportunityDB.verification_status.ilike(f"%{filters.verification_status.strip()}%"))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(desc(OpportunityDB.created_at)).offset(filters.offset).limit(filters.limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, opp_id: str) -> Optional[OpportunityDB]:
        """Fetch single opportunity by ID."""
        stmt = select(OpportunityDB).where(OpportunityDB.id == opp_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, data: OpportunityCreate) -> OpportunityDB:
        """Create new opportunity record."""
        opp_dict = data.model_dump()
        opp = OpportunityDB(**opp_dict)
        db.add(opp)
        await db.commit()
        await db.refresh(opp)
        return opp

    @classmethod
    async def verify_opportunity_by_id(cls, db: AsyncSession, opp_id: str) -> Dict[str, Any]:
        """Run verification analysis on opportunity and record verification in DB."""
        opp = await cls.get_by_id(db, opp_id)
        if not opp:
            raise ValueError(f"Opportunity with ID '{opp_id}' not found.")

        opp_data = {
            "id": opp.id,
            "company": opp.company,
            "title": opp.title,
            "description": opp.description,
            "source_url": opp.source_url,
            "application_url": opp.application_url,
            "company_domain": opp.company_domain,
            "salary": opp.salary,
            "deadline": opp.deadline,
            "eligibility": opp.eligibility,
        }

        # Run verification AI
        analysis = await verifier.analyze_opportunity(opp_data)

        # Update opportunity table status & score
        opp.verification_status = analysis["status"]
        opp.verification_score = analysis["confidence"]

        # Store verification record
        verif_rec = VerificationDB(
            opportunity_id=opp.id,
            status=analysis["status"],
            confidence=analysis["confidence"],
            signals=analysis["signals"],
            risk_factors=analysis["risk_factors"],
            explanation=analysis["explanation"],
        )
        db.add(verif_rec)
        await db.commit()
        await db.refresh(opp)

        return {
            "opportunity_id": opp.id,
            **analysis,
        }

    @staticmethod
    async def seed_from_file(db: AsyncSession, file_path: str = "seed/opportunities.json") -> int:
        """Seed opportunities from JSON file if not already present."""
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"Seed file not found at {file_path}")
            return 0

        try:
            with open(path, "r", encoding="utf-8") as f:
                items = json.load(f)

            inserted_count = 0
            for item in items:
                opp_id = item.get("id")
                # Check if exists
                stmt = select(OpportunityDB).where(OpportunityDB.id == opp_id)
                res = await db.execute(stmt)
                existing = res.scalar_one_or_none()
                if not existing:
                    opp = OpportunityDB(**item)
                    db.add(opp)
                    inserted_count += 1

            if inserted_count > 0:
                await db.commit()
                logger.info(f"Seeded {inserted_count} opportunities from {file_path}")
            return inserted_count
        except Exception as e:
            logger.error(f"Error seeding opportunities: {e}")
            await db.rollback()
            return 0


opportunity_service = OpportunityService()
