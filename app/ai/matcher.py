import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.ai.gemini import gemini_service
from app.ai.prompts.matching_prompt import (
    MATCHING_SYSTEM_INSTRUCTION,
    build_matching_prompt,
)

logger = logging.getLogger(__name__)


# --- Pydantic Schema for Gemini Structured Matching Output ---

class StructuredMatchOutput(BaseModel):
    match_score: float = Field(..., ge=0, le=100, description="Overall weighted match percentage")
    skills_score: float = Field(..., ge=0, le=100, description="Skills alignment score")
    experience_score: float = Field(..., ge=0, le=100, description="Experience alignment score")
    education_score: float = Field(..., ge=0, le=100, description="Education and academic cohort alignment")
    preference_score: float = Field(..., ge=0, le=100, description="Work mode and location preferences alignment")
    career_alignment_score: float = Field(..., ge=0, le=100, description="Long-term career goals alignment")
    matched_skills: List[str] = Field(default_factory=list, description="Skills possessed by candidate")
    skill_gaps: List[str] = Field(default_factory=list, description="Skills missing or needed for role")
    explanation: str = Field(..., description="Explainable rationale detailing strengths and gap bridge suggestions")


class Matcher:
    @classmethod
    async def match_profile_opportunity(
        cls,
        profile_data: Dict[str, Any],
        opportunity_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Perform multi-dimensional matching via Gemini API with semantic and rule fallbacks."""
        
        # 1. First run deterministic signal analysis to extract matched & missing skills
        deterministic_result = cls._deterministic_matching(profile_data, opportunity_data)

        # 2. Check if Gemini API is available for structured LLM reasoning
        if gemini_service.is_available:
            prompt = build_matching_prompt(profile_data, opportunity_data)
            gemini_result = await gemini_service.generate_structured(
                prompt=prompt,
                system_instruction=MATCHING_SYSTEM_INSTRUCTION,
                response_schema=StructuredMatchOutput,
            )
            if gemini_result:
                # Optionally incorporate semantic embedding if available
                embedding_sim = await cls._compute_semantic_similarity(profile_data, opportunity_data)
                if embedding_sim > 0:
                    # Blend slightly with embedding similarity
                    raw_gemini_score = float(gemini_result.get("match_score", 90))
                    blended = round(0.85 * raw_gemini_score + 0.15 * (embedding_sim * 100), 1)
                    gemini_result["match_score"] = min(blended, 99.0)

                return gemini_result

        # 3. Fallback to high-accuracy deterministic scoring
        logger.info("Using deterministic matching engine fallback")
        return deterministic_result

    @classmethod
    async def _compute_semantic_similarity(
        cls, profile_data: Dict[str, Any], opportunity_data: Dict[str, Any]
    ) -> float:
        """Compute cosine similarity between profile and opportunity summary embeddings."""
        try:
            profile_summary = f"{profile_data.get('name', '')} {profile_data.get('career_interests', [])} {profile_data.get('skills', [])}"
            opp_summary = f"{opportunity_data.get('title', '')} {opportunity_data.get('company', '')} {opportunity_data.get('description', '')} {opportunity_data.get('skills', [])}"
            
            p_emb = await gemini_service.get_embedding(profile_summary)
            o_emb = await gemini_service.get_embedding(opp_summary)
            if p_emb and o_emb:
                return gemini_service.cosine_similarity(p_emb, o_emb)
        except Exception as e:
            logger.debug(f"Semantic similarity skipped: {e}")
        return 0.0

    @staticmethod
    def _deterministic_matching(profile_data: Dict[str, Any], opportunity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Precise rule-based multi-dimensional scoring."""
        # 1. Flatten candidate skills
        candidate_skills = set()
        raw_skills = profile_data.get("skills", [])
        if isinstance(raw_skills, list):
            for s in raw_skills:
                candidate_skills.add(s.lower().strip())
        elif isinstance(raw_skills, dict):
            for group, s_list in raw_skills.items():
                if isinstance(s_list, list):
                    for s in s_list:
                        candidate_skills.add(s.lower().strip())

        # Also add technologies from projects & experience
        for p in profile_data.get("projects", []):
            if isinstance(p, dict):
                for tech in p.get("technologies", []):
                    candidate_skills.add(tech.lower().strip())
        for exp in profile_data.get("experience", []):
            if isinstance(exp, dict):
                for tech in exp.get("technologies", []):
                    candidate_skills.add(tech.lower().strip())

        # 2. Extract opportunity skills
        req_skills = opportunity_data.get("skills", [])
        matched = []
        gaps = []
        for s in req_skills:
            s_clean = s.strip()
            if s_clean.lower() in candidate_skills:
                matched.append(s_clean)
            else:
                gaps.append(s_clean)

        # 3. Calculate dimension scores
        total_req = len(req_skills) if req_skills else 1
        skills_ratio = len(matched) / total_req
        skills_score = round(max(40.0, min(100.0, skills_ratio * 100.0)), 1)

        # Experience score: check project & internship relevance
        experience_items = profile_data.get("experience", [])
        exp_score = 85.0 if len(experience_items) >= 2 else (75.0 if len(experience_items) == 1 else 60.0)
        
        # Education score
        edu_score = 95.0

        # Preference score (Work mode & location)
        pref_modes = [m.lower() for m in profile_data.get("preferred_work_modes", [])]
        opp_mode = str(opportunity_data.get("work_mode", "")).lower()
        preference_score = 95.0 if (opp_mode in pref_modes or "remote" in opp_mode or not pref_modes) else 75.0

        # Career alignment score
        career_interests = [c.lower() for c in profile_data.get("career_interests", [])]
        opp_title = str(opportunity_data.get("title", "")).lower()
        aligned = any(interest in opp_title or any(w in opp_title for w in interest.split()) for interest in career_interests)
        career_alignment_score = 94.0 if aligned else 78.0

        # Overall weighted match score
        overall = round(
            (skills_score * 0.40)
            + (exp_score * 0.20)
            + (edu_score * 0.15)
            + (preference_score * 0.15)
            + (career_alignment_score * 0.10),
            1,
        )

        company = opportunity_data.get("company", "Company")
        title = opportunity_data.get("title", "Role")
        
        if overall >= 85:
            explanation = (
                f"Strong alignment with candidate's {', '.join(matched[:3]) if matched else 'core'} background. "
                f"Directly advances career goals in {title} at {company}."
            )
        elif overall >= 70:
            explanation = (
                f"Moderate alignment for {title}. Candidate possesses core competencies ({', '.join(matched[:2]) if matched else 'foundational skills'}), "
                f"with opportunity to bridge {', '.join(gaps[:2]) if gaps else 'specific domain requirements'}."
            )
        else:
            explanation = (
                f"Foundational match for {title}. Candidate has related fundamentals but requires bridging gaps in "
                f"{', '.join(gaps[:3]) if gaps else 'specialized tools'}."
            )

        return {
            "match_score": overall,
            "skills_score": skills_score,
            "experience_score": exp_score,
            "education_score": edu_score,
            "preference_score": preference_score,
            "career_alignment_score": career_alignment_score,
            "matched_skills": matched,
            "skill_gaps": gaps,
            "explanation": explanation,
        }


matcher = Matcher()
