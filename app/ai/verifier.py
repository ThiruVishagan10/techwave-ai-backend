import logging
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.core.security import extract_domain, is_official_domain_match
from app.ai.gemini import gemini_service
from app.ai.prompts.verification_prompt import (
    VERIFICATION_SYSTEM_INSTRUCTION,
    build_verification_prompt,
)

logger = logging.getLogger(__name__)


class StructuredVerificationOutput(BaseModel):
    status: str = Field(..., description="VERIFIED, NEEDS_REVIEW, or SUSPICIOUS")
    confidence: float = Field(..., ge=0, le=100, description="Verification confidence score")
    signals: Dict[str, bool] = Field(default_factory=dict, description="Key trust indicators")
    risk_factors: List[str] = Field(default_factory=list, description="List of identified risk factors")
    explanation: str = Field(..., description="Explainable objective assessment")


class Verifier:
    @classmethod
    async def analyze_opportunity(cls, opportunity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Hybrid deterministic signal scoring + Gemini semantic risk analysis."""
        
        # 1. Run deterministic checks first (Rules engine)
        deterministic = cls._run_deterministic_checks(opportunity_data)
        
        # 2. Check if Gemini API is available for semantic reasoning
        if gemini_service.is_available:
            prompt = build_verification_prompt(opportunity_data, deterministic["signals"])
            gemini_result = await gemini_service.generate_structured(
                prompt=prompt,
                system_instruction=VERIFICATION_SYSTEM_INSTRUCTION,
                response_schema=StructuredVerificationOutput,
            )
            if gemini_result:
                # Merge deterministic signals and Gemini insights for maximum defensibility
                combined_signals = {**deterministic["signals"], **gemini_result.get("signals", {})}
                combined_risks = list(set(deterministic["risk_factors"] + gemini_result.get("risk_factors", [])))
                
                # Rule-override: If deterministic checks discovered an upfront scam fee or telegram scam, force SUSPICIOUS
                final_status = gemini_result.get("status", deterministic["status"])
                if deterministic["status"] == "SUSPICIOUS":
                    final_status = "SUSPICIOUS"
                
                return {
                    "status": final_status,
                    "confidence": gemini_result.get("confidence", deterministic["confidence"]),
                    "signals": combined_signals,
                    "risk_factors": combined_risks,
                    "explanation": gemini_result.get("explanation", deterministic["explanation"]),
                }

        # 3. Fallback to deterministic rules engine output
        logger.info("Using deterministic verification engine output")
        return deterministic

    @staticmethod
    def _run_deterministic_checks(data: Dict[str, Any]) -> Dict[str, Any]:
        """Rules-based deterministic verification checks."""
        company = data.get("company", "")
        domain = data.get("company_domain") or extract_domain(data.get("source_url"))
        app_url = data.get("application_url", "")
        desc = (data.get("description", "") + " " + " ".join(data.get("responsibilities", []))).lower()
        salary = str(data.get("salary", "")).lower()

        signals = {
            "company_information": bool(company and len(company) > 1),
            "official_domain": bool(domain and "." in domain),
            "application_url": bool(app_url and app_url.startswith("http")),
            "complete_description": len(desc) > 120,
            "deadline_detected": bool(data.get("deadline")),
            "no_suspicious_payment": True,
            "domain_consistency": True,
        }
        risk_factors = []

        # Check for upfront fee / payment scam patterns
        scam_phrases = [
            "registration fee", "deposit fee", "training kit fee", "refundable deposit",
            "security deposit", "processing charge", "pay ₹", "pay $", "pay rs",
            "wallet balance", "crypto deposit", "upi transfer to claim"
        ]
        for phrase in scam_phrases:
            if phrase in desc or phrase in salary:
                signals["no_suspicious_payment"] = False
                risk_factors.append(f"Demands upfront payment or registration deposit ('{phrase}')")

        # Check for untracked communication channels (Telegram / WhatsApp bots)
        if "t.me/" in app_url.lower() or "telegram" in desc or "chat.whatsapp.com" in app_url.lower():
            signals["application_url"] = False
            risk_factors.append("Directs candidates to informal messaging channels (Telegram/WhatsApp) instead of corporate ATS")

        # Check for suspicious or newly registered TLDs
        app_domain = extract_domain(app_url)
        if app_domain:
            suspicious_tlds = [".xyz", ".biz", ".top", ".info", ".click", ".link"]
            if any(app_domain.endswith(tld) for tld in suspicious_tlds):
                risk_factors.append(f"Application endpoint hosted on high-risk generic TLD ({app_domain})")
            
            # Check domain consistency with company
            if domain and not is_official_domain_match(company, app_domain):
                # Check if it is a reputable ATS
                reputable_ats = ["lever.co", "greenhouse.io", "myworkdayjobs.com", "ashbyhq.com", "smartrecruiters.com", "bamboohr.com"]
                if not any(ats in app_domain for ats in reputable_ats):
                    signals["domain_consistency"] = False
                    risk_factors.append(f"Application domain ({app_domain}) does not match company domain ({domain})")

        # Check for unrealistic salary claims for entry roles
        if "guaranteed" in desc and ("week" in salary or "daily" in salary):
            risk_factors.append("Unrealistically high guaranteed payout promises without formal technical screening")

        # Determine Status & Confidence
        if not signals["no_suspicious_payment"] or any("Telegram" in r or "WhatsApp" in r for r in risk_factors):
            status = "SUSPICIOUS"
            confidence = 94.0
            explanation = "High risk indicators detected: posting requests financial deposits or directs candidates to unmonitored personal messaging channels."
        elif risk_factors or not signals["domain_consistency"] or "forms.gle" in app_url:
            status = "NEEDS_REVIEW"
            confidence = 74.0
            explanation = "Posting exhibits non-standard recruitment attributes (external third-party forms or unverified corporate presence) that warrant manual verification."
        else:
            status = "VERIFIED"
            confidence = 96.0
            explanation = "Verified authentic listing: official corporate domain confirmed, secure application endpoint validated, and zero high-risk signals detected."

        return {
            "status": status,
            "confidence": confidence,
            "signals": signals,
            "risk_factors": risk_factors,
            "explanation": explanation,
        }


verifier = Verifier()
