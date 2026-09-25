import re
from typing import Optional
from urllib.parse import urlparse


def sanitize_text(text: Optional[str]) -> str:
    """Sanitize and strip whitespace/control characters."""
    if not text:
        return ""
    # Strip null bytes and normalize whitespace
    cleaned = text.replace("\x00", "").strip()
    return cleaned


def extract_domain(url: Optional[str]) -> Optional[str]:
    """Extract domain from a URL safely."""
    if not url:
        return None
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        # Remove port and www
        netloc = netloc.split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc or None
    except Exception:
        return None


def is_official_domain_match(company: str, domain: Optional[str]) -> bool:
    """Check if the domain broadly matches the company name or subdomains."""
    if not company or not domain:
        return False
    domain_lower = domain.lower()
    company_lower = company.lower()
    comp_clean = re.sub(r"[^a-zA-Z0-9]", "", company_lower)
    
    # Direct match or subdomain match (e.g. careers.microsoft.com matching microsoft.com or Microsoft)
    if comp_clean in domain_lower:
        return True
    
    # Check parts of domain
    parts = domain_lower.split(".")
    for part in parts:
        if comp_clean in part or part in comp_clean:
            return True
    return False
