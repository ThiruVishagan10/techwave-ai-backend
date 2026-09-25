import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc

from app.models.application import (
    ApplicationDB,
    ApplicationCreate,
    ApplicationUpdate,
)
from app.models.opportunity import OpportunityDB
from app.models.profile import ProfileDB

logger = logging.getLogger(__name__)


class ApplicationService:
    @staticmethod
    async def get_by_profile_id(db: AsyncSession, profile_id: str) -> List[Dict[str, Any]]:
        """Fetch all application records for a student profile, joined with opportunity info."""
        matching_ids = [profile_id]
        p_res = await db.execute(
            select(ProfileDB).where(
                (ProfileDB.id == profile_id) | (ProfileDB.user_id == profile_id)
            ).order_by(ProfileDB.created_at.desc())
        )
        profile = p_res.scalars().first()
        if profile:
            matching_ids.extend([profile.id, profile.user_id])
        matching_ids = list(set(matching_ids))

        stmt = (
            select(ApplicationDB, OpportunityDB)
            .outerjoin(OpportunityDB, ApplicationDB.opportunity_id == OpportunityDB.id)
            .where(ApplicationDB.profile_id.in_(matching_ids))
            .order_by(desc(ApplicationDB.updated_at))
        )
        res = await db.execute(stmt)
        rows = res.all()

        results = []
        for app_row, opp_row in rows:
            app_dict = {
                "id": app_row.id,
                "profile_id": app_row.profile_id,
                "opportunity_id": app_row.opportunity_id,
                "status": app_row.status.upper(),
                "applied_at": app_row.applied_at,
                "notes": app_row.notes,
                "created_at": app_row.created_at,
                "updated_at": app_row.updated_at,
                "opportunity": None,
            }
            if opp_row:
                app_dict["opportunity"] = {
                    "id": opp_row.id,
                    "title": opp_row.title,
                    "company": opp_row.company,
                    "company_logo_color": opp_row.company_logo_color,
                    "company_initial": opp_row.company_initial,
                    "location": opp_row.location,
                    "work_mode": opp_row.work_mode,
                    "opportunity_type": opp_row.opportunity_type,
                    "salary": opp_row.salary,
                    "deadline": opp_row.deadline,
                    "verification_status": opp_row.verification_status,
                }
            results.append(app_dict)

        return results

    @staticmethod
    async def create_or_update_application(
        db: AsyncSession,
        data: ApplicationCreate,
    ) -> Dict[str, Any]:
        """Create new application or update status if already exists."""
        stmt = select(ApplicationDB).where(
            and_(
                ApplicationDB.profile_id == data.profile_id,
                ApplicationDB.opportunity_id == data.opportunity_id,
            )
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()

        clean_status = data.status.upper()

        if existing:
            existing.status = clean_status
            if data.notes is not None:
                existing.notes = data.notes
            if clean_status == "APPLIED" and not existing.applied_at:
                existing.applied_at = datetime.now(timezone.utc)
            existing.updated_at = datetime.now(timezone.utc)
            app_record = existing
        else:
            app_record = ApplicationDB(
                profile_id=data.profile_id,
                opportunity_id=data.opportunity_id,
                status=clean_status,
                notes=data.notes,
                applied_at=data.applied_at or (datetime.now(timezone.utc) if clean_status == "APPLIED" else None),
            )
            db.add(app_record)

        await db.commit()
        await db.refresh(app_record)

        # Get opp details
        opp_res = await db.execute(select(OpportunityDB).where(OpportunityDB.id == app_record.opportunity_id))
        opp = opp_res.scalar_one_or_none()

        return {
            "id": app_record.id,
            "profile_id": app_record.profile_id,
            "opportunity_id": app_record.opportunity_id,
            "status": app_record.status,
            "applied_at": app_record.applied_at,
            "notes": app_record.notes,
            "created_at": app_record.created_at,
            "updated_at": app_record.updated_at,
            "opportunity": {
                "id": opp.id,
                "title": opp.title,
                "company": opp.company,
                "location": opp.location,
            } if opp else None,
        }

    @staticmethod
    async def update_by_id(
        db: AsyncSession,
        app_id: str,
        data: ApplicationUpdate,
    ) -> Optional[Dict[str, Any]]:
        stmt = select(ApplicationDB).where(ApplicationDB.id == app_id)
        res = await db.execute(stmt)
        app_record = res.scalar_one_or_none()
        if not app_record:
            return None

        if data.status:
            clean_status = data.status.upper()
            app_record.status = clean_status
            if clean_status == "APPLIED" and not app_record.applied_at:
                app_record.applied_at = datetime.now(timezone.utc)
        if data.notes is not None:
            app_record.notes = data.notes
        
        app_record.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(app_record)

        return {
            "id": app_record.id,
            "profile_id": app_record.profile_id,
            "opportunity_id": app_record.opportunity_id,
            "status": app_record.status,
            "applied_at": app_record.applied_at,
            "notes": app_record.notes,
            "created_at": app_record.created_at,
            "updated_at": app_record.updated_at,
        }

    @staticmethod
    async def delete_by_id(db: AsyncSession, app_id: str) -> bool:
        stmt = select(ApplicationDB).where(ApplicationDB.id == app_id)
        res = await db.execute(stmt)
        app_record = res.scalar_one_or_none()
        if not app_record:
            return False
        await db.delete(app_record)
        await db.commit()
        return True

    @staticmethod
    async def seed_default_applications(db: AsyncSession) -> int:
        """Seed initial demo applications for default user Alex Morgan if none exist."""
        profile_ids = ["profile-alex-morgan", "user_default"]
        stmt = select(ApplicationDB).where(ApplicationDB.profile_id.in_(profile_ids))
        res = await db.execute(stmt)
        if res.scalars().first():
            return 0

        demo_apps = [
            {
                "id": "app-seed-deepmind",
                "profile_id": "profile-alex-morgan",
                "opportunity_id": "opp-deepmind-genai",
                "status": "INTERVIEW",
                "notes": "Passed Round 1 coding interview. Technical architecture round scheduled.",
                "applied_at": datetime.now(timezone.utc),
            },
            {
                "id": "app-seed-msft",
                "profile_id": "profile-alex-morgan",
                "opportunity_id": "opp-msft-aiml",
                "status": "APPLIED",
                "notes": "Application submitted via Microsoft Careers university portal.",
                "applied_at": datetime.now(timezone.utc),
            },
            {
                "id": "app-seed-stripe",
                "profile_id": "profile-alex-morgan",
                "opportunity_id": "opp-stripe-be",
                "status": "OFFER",
                "notes": "Received Summer 2026 internship offer! Stipend ₹185,000/month.",
                "applied_at": datetime.now(timezone.utc),
            },
            {
                "id": "app-seed-atlassian",
                "profile_id": "profile-alex-morgan",
                "opportunity_id": "opp-atlassian-de",
                "status": "SAVED",
                "notes": "Bookmarked for upcoming application cycle.",
                "applied_at": datetime.now(timezone.utc),
            },
        ]

        seeded_count = 0
        for app_data in demo_apps:
            opp_res = await db.execute(select(OpportunityDB).where(OpportunityDB.id == app_data["opportunity_id"]))
            if opp_res.scalar_one_or_none():
                app_obj = ApplicationDB(**app_data)
                db.add(app_obj)
                seeded_count += 1

        try:
            if seeded_count > 0:
                await db.commit()
                logger.info(f"Seeded {seeded_count} demo applications for Alex Morgan.")
            return seeded_count
        except Exception as e:
            logger.error(f"Error seeding default applications: {e}")
            await db.rollback()
            return 0


application_service = ApplicationService()
