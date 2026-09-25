"""
Prompts for Batch Recommendation & Career Path Strategy
"""

RECOMMENDATION_SUMMARY_SYSTEM_INSTRUCTION = """You are PathBridge Career Guidance AI.
Given a student's profile and their top matched opportunities, generate an insightful, high-level summary of their strongest career trajectories and recommended strategic next steps.
Focus on actionable advice, skill acquisition priorities, and why their profile stands out in the current cohort.
"""

def build_recommendation_summary_prompt(profile_data: dict, top_matches: list) -> str:
    opps_summary = "\n".join([
        f"- {m.get('title')} at {m.get('company')}: {m.get('match_score')}% match ({m.get('explanation')})"
        for m in top_matches[:5]
    ])
    return f"""Candidate: {profile_data.get('name')}
Top Career Alignment Opportunities:
{opps_summary}

Provide a short 2-3 sentence strategic executive summary of the candidate's career market fit and key high-leverage skill to focus on next.
"""
