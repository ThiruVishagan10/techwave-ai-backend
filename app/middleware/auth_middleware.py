import logging
from typing import Optional, Dict, Any, List
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings
from app.core.security import decode_access_token

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Application-wide Authentication Middleware.
    
    Ensures that users are authenticated before accessing protected routes:
    - Automatically allows CORS preflight (OPTIONS) requests.
    - Allows explicitly defined exempt paths (login, register, docs, health).
    - Extracts JWT Bearer tokens from 'Authorization' header, cookies, or query params.
    - Decodes and validates tokens, setting `request.state.user` and `request.state.is_authenticated`.
    - Returns standardized 401 JSON responses for missing or invalid tokens on protected routes.
    """

    def __init__(self, app, exempt_paths: Optional[List[str]] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or settings.AUTH_EXEMPT_PATHS

    def is_exempt(self, path: str) -> bool:
        """Check whether the given URL path is exempt from authentication."""
        clean_path = path.rstrip("/") or "/"

        for exempt in self.exempt_paths:
            exempt_clean = exempt.rstrip("/") or "/"
            # Exact match or prefix match for docs/auth routes
            if clean_path == exempt_clean or clean_path.startswith(f"{exempt_clean}/"):
                return True
            if exempt_clean != "/" and clean_path.startswith(exempt_clean):
                return True

        # Always exempt OpenAPI specs and interactive docs
        if clean_path.startswith(("/docs", "/redoc", "/openapi.json")):
            return True

        return False

    @staticmethod
    def extract_token(request: Request) -> Optional[str]:
        """Extract JWT token from Authorization header, cookies, or query parameters."""
        # 1. Bearer token in Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header:
            parts = auth_header.strip().split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                return parts[1]
            elif len(parts) == 1:
                return parts[0]

        # 2. Token stored in HTTP-only or session cookie
        cookie_token = request.cookies.get("access_token") or request.cookies.get("token")
        if cookie_token:
            return cookie_token

        # 3. Token passed in query string (for downloads, SSE, or direct links)
        query_token = request.query_params.get("token") or request.query_params.get("access_token")
        if query_token:
            return query_token

        return None

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Default unauthenticated state
        request.state.user = None
        request.state.user_id = None
        request.state.is_authenticated = False

        # 1. CORS Preflight requests must always pass through unblocked
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        token = self.extract_token(request)

        # 2. If a token is provided, attempt to decode and validate it
        payload: Optional[Dict[str, Any]] = None
        if token:
            payload = decode_access_token(token)
            if payload:
                request.state.user = payload
                request.state.user_id = payload.get("sub")
                request.state.is_authenticated = True

        # 3. Check if the path is in the exemption list
        if self.is_exempt(path):
            return await call_next(request)

        # 4. Protected route handling
        if not token:
            logger.warning(f"Unauthenticated request to protected route: {request.method} {path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Authentication required. Please log in to access this resource.",
                    },
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not payload:
            logger.warning(f"Invalid or expired token for route: {request.method} {path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "INVALID_TOKEN",
                        "message": "Invalid or expired access token. Please log in again.",
                    },
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 5. Token is valid and user is verified, continue down middleware chain
        return await call_next(request)
