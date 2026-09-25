import re
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt

from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a raw password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash a password securely using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Encode a JWT access token with expiration timestamp."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except (jwt.PyJWTError, Exception):
        return None


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
