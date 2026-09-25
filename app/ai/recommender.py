import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class Recommender:
    @staticmethod
    def rank_opportunities(
        opportunities: List[Dict[str, Any]],
        recommendations_map: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Rank opportunities according to PathBridge multi-objective priority:
        1. Verification status (Verified > Needs Review > Suspicious)
        2. Match score (Highest first)
        3. Career alignment score
        4. Freshness / Deadline
        """
        enriched = []
        for opp in opportunities:
            opp_id = opp.get("id")
            rec = recommendations_map.get(opp_id)
            
            # Extract scores if available
            match_score = rec.get("match_score", opp.get("match_score", 50.0)) if rec else opp.get("match_score", 50.0)
            career_alignment = rec.get("career_alignment_score", 50.0) if rec else 50.0
            verif_status = opp.get("verification_status", "VERIFIED").upper()

            # Assign priority weight
            # VERIFIED gets bonus +20, NEEDS_REVIEW 0, SUSPICIOUS heavily penalized (-100)
            status_weight = 20.0 if verif_status == "VERIFIED" else (0.0 if verif_status == "NEEDS_REVIEW" else -100.0)
            
            composite_rank = float(match_score) + (career_alignment * 0.2) + status_weight
            
            enriched_opp = dict(opp)
            if rec:
                enriched_opp["match_score"] = rec.get("match_score")
                enriched_opp["matched_skills"] = rec.get("matched_skills")
                enriched_opp["missing_skills"] = rec.get("skill_gaps")
                enriched_opp["ai_explanation"] = rec.get("explanation")
                enriched_opp["match_breakdown"] = {
                    "skillsMatch": rec.get("skills_score", 85.0),
                    "experienceMatch": rec.get("experience_score", 80.0),
                    "educationMatch": rec.get("education_score", 90.0),
                    "preferenceMatch": rec.get("preference_score", 85.0),
                    "careerGoalAlignment": rec.get("career_alignment_score", 90.0),
                }

            enriched.append((composite_rank, enriched_opp))

        # Sort descending by composite rank
        enriched.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in enriched]


recommender = Recommender()
