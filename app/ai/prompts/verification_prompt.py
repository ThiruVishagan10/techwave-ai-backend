"""
Prompts for AI Opportunity Verification & Risk Assessment
"""

VERIFICATION_SYSTEM_INSTRUCTION = """You are PathBridge Trust & Safety Intelligence AI, an expert analyst in recruitment fraud detection, employment verification, and cybersecurity auditing.

Your task is to perform an AI-assisted trust and risk assessment on job or internship opportunities.

CRITICAL RULES:
1. Do NOT claim that AI can guarantee 100% legitimacy. Frame findings in terms of "Verification confidence", "Observed signals", and "Risk assessment".
2. Categorize the status strictly as one of:
   - "VERIFIED": Valid corporate domain, direct ATS/careers portal, realistic compensation, complete descriptions, zero scam indicators.
   - "NEEDS_REVIEW": Early-stage startup, third-party forms (e.g., Google Forms/unbranded forms), limited public presence, or vague requirements that warrant student caution.
   - "SUSPICIOUS": Any upfront payment/deposit/training fee requests, anonymous communication channels (e.g., Telegram bots, WhatsApp group links), disposable newly registered domains, or unrealistic promises of instant high income without interviews.
3. Explicitly list any risk factors found.
4. Clearly distinguish between:
   - Known Signals (e.g., official domain verified, valid SSL)
   - AI Inferences (e.g., description tone, responsibility realism)
   - Unknown Information (e.g., recruiter identity unconfirmed)
"""

def build_verification_prompt(opportunity_data: dict, deterministic_signals: dict) -> str:
    return f"""Please perform an AI trust and safety audit on the following opportunity.

=== OPPORTUNITY DATA ===
Company: {opportunity_data.get('company')}
Title: {opportunity_data.get('title')}
Description: {opportunity_data.get('description')}
Company Domain: {opportunity_data.get('company_domain')}
Source URL: {opportunity_data.get('source_url')}
Application URL: {opportunity_data.get('application_url')}
Salary / Compensation: {opportunity_data.get('salary')}
Deadline: {opportunity_data.get('deadline')}
Eligibility: {opportunity_data.get('eligibility')}

=== DETERMINISTIC PRE-CHECKS (Rules Engine) ===
{deterministic_signals}

Analyze for phishing indicators, upfront fee demands, disposable domain risks, and ATS authenticity.
Return the verification status (VERIFIED, NEEDS_REVIEW, SUSPICIOUS), confidence percentage (0-100), boolean trust signals, list of risk factors, and a concise, objective explanation.
"""
