import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.profile import ProfileDB, ProfileCreate
from app.ai.profile_analyzer import profile_analyzer

logger = logging.getLogger(__name__)


class ProfileService:
    @staticmethod
    async def get_by_id(db: AsyncSession, profile_id: str) -> Optional[ProfileDB]:
        stmt = select(ProfileDB).where(
            (ProfileDB.id == profile_id) | (ProfileDB.user_id == profile_id)
        ).order_by(ProfileDB.created_at.desc())
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: str = "user_default") -> Optional[ProfileDB]:
        stmt = select(ProfileDB).where(
            (ProfileDB.user_id == user_id) | (ProfileDB.id == user_id)
        ).order_by(ProfileDB.created_at.desc())
        result = await db.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def analyze_and_create(
        cls,
        db: AsyncSession,
        resume_text: Optional[str] = None,
        pdf_bytes: Optional[bytes] = None,
        user_id: str = "user_default",
        additional_notes: str = "",
        target_name: Optional[str] = None,
    ) -> ProfileDB:
        """Extract resume text from PDF or raw string, invoke Gemini structured analysis, and persist to DB."""
        if pdf_bytes:
            extracted_text = profile_analyzer.extract_text_from_pdf(pdf_bytes)
        elif resume_text:
            extracted_text = resume_text.strip()
        else:
            raise ValueError("Either resume_text or PDF file must be provided.")

        analysis = await profile_analyzer.analyze_resume(
            resume_text=extracted_text,
            additional_notes=additional_notes,
            fallback_name=target_name,
        )

        # Check if user profile already exists
        existing = await cls.get_by_user_id(db, user_id)
        if existing:
            existing.name = analysis.get("name", existing.name)
            existing.education = analysis.get("education", existing.education)
            existing.skills = analysis.get("skills", existing.skills)
            existing.experience = analysis.get("experience", existing.experience)
            existing.projects = analysis.get("projects", existing.projects)
            existing.career_interests = analysis.get("career_interests", existing.career_interests)
            existing.preferred_locations = analysis.get("preferred_locations", existing.preferred_locations)
            existing.preferred_work_modes = analysis.get("preferred_work_modes", existing.preferred_work_modes)
            existing.preferred_opportunity_types = analysis.get("preferred_opportunity_types", existing.preferred_opportunity_types)
            existing.resume_text = extracted_text
            existing.profile_strength = analysis.get("profile_strength", existing.profile_strength)
            profile = existing
        else:
            profile = ProfileDB(
                user_id=user_id,
                name=analysis.get("name", target_name or "Alex Morgan"),
                education=analysis.get("education", []),
                skills=analysis.get("skills", []),
                experience=analysis.get("experience", []),
                projects=analysis.get("projects", []),
                career_interests=analysis.get("career_interests", []),
                preferred_locations=analysis.get("preferred_locations", []),
                preferred_work_modes=analysis.get("preferred_work_modes", []),
                preferred_opportunity_types=analysis.get("preferred_opportunity_types", []),
                resume_text=extracted_text,
                profile_strength=analysis.get("profile_strength", 75.0),
            )
            db.add(profile)

        await db.commit()
        await db.refresh(profile)
        return profile

    @staticmethod
    async def create_profile(db: AsyncSession, data: ProfileCreate) -> ProfileDB:
        profile_dict = data.model_dump()
        profile = ProfileDB(**profile_dict)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        return profile

    @staticmethod
    async def seed_default_profile(db: AsyncSession, file_path: str = "seed/default_profile.json") -> Optional[ProfileDB]:
        """Seed initial user profile if specific default profile does not exist."""
        path = Path(file_path)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            target_id = data.get("id", "profile-alex-morgan")
            stmt = select(ProfileDB).where(ProfileDB.id == target_id)
            res = await db.execute(stmt)
            if res.scalar_one_or_none():
                return None

            profile = ProfileDB(**data)
            db.add(profile)
            await db.commit()
            await db.refresh(profile)
            logger.info(f"Seeded default career profile for {profile.name} (id: {profile.id})")
            return profile
        except Exception as e:
            logger.error(f"Error seeding default profile: {e}")
            await db.rollback()
            return None


profile_service = ProfileService()
