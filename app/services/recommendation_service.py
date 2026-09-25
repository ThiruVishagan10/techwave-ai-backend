import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.recommendation import RecommendationDB, MatchResponse
from app.models.profile import ProfileDB
from app.models.opportunity import OpportunityDB
from app.ai.matcher import matcher
from app.ai.recommender import recommender

logger = logging.getLogger(__name__)


class RecommendationService:
    @classmethod
    async def match_single(
        cls,
        db: AsyncSession,
        profile_id: str,
        opportunity_id: str,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Generate or retrieve cached explainable match for a profile and opportunity."""
        # 1. Fetch profile & opportunity records
        p_res = await db.execute(
            select(ProfileDB).where(
                (ProfileDB.id == profile_id) | (ProfileDB.user_id == profile_id)
            ).order_by(ProfileDB.created_at.desc())
        )
        profile = p_res.scalars().first()
        if not profile:
            raise ValueError(f"Profile '{profile_id}' not found.")

        canonical_profile_id = profile.id
        matching_profile_ids = list(set([profile_id, profile.id, profile.user_id]))

        # Check database cache if refresh not requested
        if not force_refresh:
            stmt = select(RecommendationDB).where(
                and_(
                    RecommendationDB.profile_id.in_(matching_profile_ids),
                    RecommendationDB.opportunity_id == opportunity_id,
                )
            )
            res = await db.execute(stmt)
            cached = res.scalar_one_or_none()
            if cached:
                logger.info(f"Returning cached recommendation for profile={profile_id}, opp={opportunity_id}")
                return {
                    "id": cached.id,
                    "profile_id": cached.profile_id,
                    "opportunity_id": cached.opportunity_id,
                    "match_score": cached.match_score,
                    "skills_score": cached.skills_score,
                    "experience_score": cached.experience_score,
                    "education_score": cached.education_score,
                    "preference_score": cached.preference_score,
                    "career_alignment_score": cached.career_alignment_score,
                    "matched_skills": cached.matched_skills or [],
                    "skill_gaps": cached.skill_gaps or [],
                    "explanation": cached.explanation,
                    "created_at": cached.created_at,
                }

        o_res = await db.execute(select(OpportunityDB).where(OpportunityDB.id == opportunity_id))
        opportunity = o_res.scalar_one_or_none()
        if not opportunity:
            raise ValueError(f"Opportunity '{opportunity_id}' not found.")

        # 3. Format inputs for AI Matcher
        profile_data = {
            "name": profile.name,
            "education": profile.education,
            "skills": profile.skills,
            "experience": profile.experience,
            "projects": profile.projects,
            "career_interests": profile.career_interests,
            "preferred_locations": profile.preferred_locations,
            "preferred_work_modes": profile.preferred_work_modes,
            "preferred_opportunity_types": profile.preferred_opportunity_types,
        }
        opp_data = {
            "company": opportunity.company,
            "title": opportunity.title,
            "description": opportunity.description,
            "skills": opportunity.skills,
            "location": opportunity.location,
            "work_mode": opportunity.work_mode,
            "opportunity_type": opportunity.opportunity_type,
            "eligibility": opportunity.eligibility,
            "responsibilities": opportunity.responsibilities,
            "requirements": opportunity.requirements,
        }

        # 4. Invoke Matcher AI
        match_result = await matcher.match_profile_opportunity(profile_data, opp_data)

        # 5. Persist or update in database
        stmt_check = select(RecommendationDB).where(
            and_(
                RecommendationDB.profile_id.in_(matching_profile_ids),
                RecommendationDB.opportunity_id == opportunity_id,
            )
        )
        res_check = await db.execute(stmt_check)
        rec = res_check.scalar_one_or_none()

        if rec:
            rec.match_score = match_result["match_score"]
            rec.skills_score = match_result["skills_score"]
            rec.experience_score = match_result["experience_score"]
            rec.education_score = match_result["education_score"]
            rec.preference_score = match_result["preference_score"]
            rec.career_alignment_score = match_result["career_alignment_score"]
            rec.matched_skills = match_result["matched_skills"]
            rec.skill_gaps = match_result["skill_gaps"]
            rec.explanation = match_result["explanation"]
        else:
            rec = RecommendationDB(
                profile_id=canonical_profile_id,
                opportunity_id=opportunity_id,
                match_score=match_result["match_score"],
                skills_score=match_result["skills_score"],
                experience_score=match_result["experience_score"],
                education_score=match_result["education_score"],
                preference_score=match_result["preference_score"],
                career_alignment_score=match_result["career_alignment_score"],
                matched_skills=match_result["matched_skills"],
                skill_gaps=match_result["skill_gaps"],
                explanation=match_result["explanation"],
            )
            db.add(rec)

        await db.commit()
        await db.refresh(rec)

        return {
            "id": rec.id,
            "profile_id": rec.profile_id,
            "opportunity_id": rec.opportunity_id,
            "match_score": rec.match_score,
            "skills_score": rec.skills_score,
            "experience_score": rec.experience_score,
            "education_score": rec.education_score,
            "preference_score": rec.preference_score,
            "career_alignment_score": rec.career_alignment_score,
            "matched_skills": rec.matched_skills or [],
            "skill_gaps": rec.skill_gaps or [],
            "explanation": rec.explanation,
            "created_at": rec.created_at,
        }

    @classmethod
    async def get_ranked_recommendations(
        cls,
        db: AsyncSession,
        profile_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve and rank recommendations for a candidate profile."""
        # 1. Fetch profile
        p_res = await db.execute(
            select(ProfileDB).where(
                (ProfileDB.id == profile_id) | (ProfileDB.user_id == profile_id)
            ).order_by(ProfileDB.created_at.desc())
        )
        profile = p_res.scalars().first()
        if not profile:
            raise ValueError(f"Profile '{profile_id}' not found.")

        canonical_profile_id = profile.id
        matching_profile_ids = list(set([profile_id, profile.id, profile.user_id]))

        # 2. Fetch all opportunities
        o_res = await db.execute(select(OpportunityDB))
        opportunities = list(o_res.scalars().all())
        if not opportunities:
            return []

        # 3. Fetch existing recommendations from DB
        r_res = await db.execute(
            select(RecommendationDB).where(RecommendationDB.profile_id.in_(matching_profile_ids))
        )
        existing_recs = {r.opportunity_id: r for r in r_res.scalars().all()}

        # 4. For any opportunities without recommendations, generate baseline scores so candidate gets instant rankings
        profile_data = {
            "name": profile.name,
            "skills": profile.skills,
            "experience": profile.experience,
            "projects": profile.projects,
            "career_interests": profile.career_interests,
            "preferred_locations": profile.preferred_locations,
            "preferred_work_modes": profile.preferred_work_modes,
        }

        recs_map = {}
        for opp in opportunities:
            if opp.id in existing_recs:
                cached = existing_recs[opp.id]
                recs_map[opp.id] = {
                    "match_score": cached.match_score,
                    "skills_score": cached.skills_score,
                    "experience_score": cached.experience_score,
                    "education_score": cached.education_score,
                    "preference_score": cached.preference_score,
                    "career_alignment_score": cached.career_alignment_score,
                    "matched_skills": cached.matched_skills,
                    "skill_gaps": cached.skill_gaps,
                    "explanation": cached.explanation,
                }
            else:
                # Fast rule-based score for display, saved to DB
                opp_dict = {
                    "company": opp.company,
                    "title": opp.title,
                    "description": opp.description,
                    "skills": opp.skills or [],
                    "location": opp.location,
                    "work_mode": opp.work_mode,
                }
                calc = matcher._deterministic_matching(profile_data, opp_dict)
                recs_map[opp.id] = calc

                # Store into DB for subsequent lookups
                new_rec = RecommendationDB(
                    profile_id=profile_id,
                    opportunity_id=opp.id,
                    match_score=calc["match_score"],
                    skills_score=calc["skills_score"],
                    experience_score=calc["experience_score"],
                    education_score=calc["education_score"],
                    preference_score=calc["preference_score"],
                    career_alignment_score=calc["career_alignment_score"],
                    matched_skills=calc["matched_skills"],
                    skill_gaps=calc["skill_gaps"],
                    explanation=calc["explanation"],
                )
                db.add(new_rec)

        await db.commit()

        # 5. Convert opportunities to dict and rank
        opp_dicts = []
        for o in opportunities:
            opp_dicts.append({
                "id": o.id,
                "title": o.title,
                "company": o.company,
                "company_logo_color": o.company_logo_color or "from-blue-600 to-indigo-600",
                "company_initial": o.company_initial or o.company[:2].upper(),
                "location": o.location,
                "work_mode": o.work_mode,
                "opportunity_type": o.opportunity_type,
                "duration": o.duration or "6 months",
                "salary": o.salary,
                "deadline": o.deadline,
                "source_url": o.source_url,
                "application_url": o.application_url,
                "company_domain": o.company_domain,
                "verification_status": o.verification_status,
                "verification_score": o.verification_score,
                "skills": o.skills or [],
                "eligibility": o.eligibility,
                "description": o.description,
                "responsibilities": o.responsibilities or [],
                "requirements": o.requirements or [],
                "benefits": o.benefits or [],
                "verification_checks": o.verification_checks or [],
                "posted_days_ago": o.posted_days_ago,
            })

        ranked = recommender.rank_opportunities(opp_dicts, recs_map)
        return ranked[:limit]


recommendation_service = RecommendationService()
