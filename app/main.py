import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException

from app.core.config import settings
from app.db.database import init_db, AsyncSessionLocal
from app.services.opportunity_service import opportunity_service
from app.services.profile_service import profile_service

# Routers
from app.api.profiles import router as profiles_router
from app.api.opportunities import router as opportunities_router
from app.api.recommendations import router as recommendations_router
from app.api.verification import router as verification_router
from app.api.applications import router as applications_router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & shutdown events."""
    logger.info("Initializing PathBridge 2.0 AI Backend...")
    # 1. Initialize DB schema
    await init_db()

    # 2. Seed initial dataset if needed
    async with AsyncSessionLocal() as session:
        try:
            await opportunity_service.seed_from_file(session, "seed/opportunities.json")
            await profile_service.seed_default_profile(session, "seed/default_profile.json")
        except Exception as e:
            logger.warning(f"Initial seeding note: {e}")

    logger.info("PathBridge 2.0 AI Backend ready to serve requests.")
    yield
    logger.info("Shutting down PathBridge 2.0 AI Backend.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "AI-powered internship and job discovery, verification, and explainable recommendation backend "
        "powered by Google Gemini API and FastAPI."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handlers for standard { success, data, error } envelope
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        422: "UNPROCESSABLE_ENTITY",
        500: "INTERNAL_SERVER_ERROR",
    }
    code = code_map.get(exc.status_code, "ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": code,
                "message": exc.detail,
            },
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters.",
                "details": exc.errors(),
            },
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled server error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(exc),
            },
        },
    )


# Health check endpoint (Section 20)
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for service monitoring and uptime validation."""
    return {
        "status": "ok",
        "service": "pathbridge-ai",
        "version": settings.VERSION,
    }


# Include Routers under /api
api_prefix = settings.API_V1_STR
app.include_router(profiles_router, prefix=api_prefix)
app.include_router(opportunities_router, prefix=api_prefix)
app.include_router(recommendations_router, prefix=api_prefix)
app.include_router(verification_router, prefix=api_prefix)
app.include_router(applications_router, prefix=api_prefix)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
