import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import secrets
import httpx
from app.core.config import settings
from app.db.database import get_db
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.common import APIResponse
from app.models.user import (
    UserDB,
    UserRegisterRequest,
    UserLoginRequest,
    GoogleAuthRequest,
    UserResponse,
    AuthResponse,
)
from app.models.profile import ProfileDB
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=APIResponse[AuthResponse], status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new student or recruiter account and return access token."""
    email_clean = user_in.email.strip().lower()

    # Check for existing email
    stmt = select(UserDB).where(UserDB.email == email_clean)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An account with email '{email_clean}' already exists.",
        )

    # Hash password and create user
    hashed_pwd = get_password_hash(user_in.password)
    user = UserDB(
        email=email_clean,
        hashed_password=hashed_pwd,
        full_name=user_in.full_name.strip(),
        role=user_in.role or "student",
        avatar_url=user_in.avatar_url,
    )
    db.add(user)
    await db.flush()  # assign user.id

    # Create an initial linked profile for students if not exists
    profile = ProfileDB(
        user_id=user.id,
        name=user.full_name,
        skills=["Python", "FastAPI", "Machine Learning"],
        career_interests=["Software Engineering", "AI/ML"],
        preferred_work_modes=["Remote", "Hybrid"],
        preferred_opportunity_types=["Internship"],
    )
    db.add(profile)
    await db.commit()
    await db.refresh(user)
    await db.refresh(profile)

    # Issue JWT token
    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        role=user.role,
        is_active=user.is_active,
        profile_id=profile.id,
        created_at=user.created_at,
    )

    return APIResponse.success_response(
        AuthResponse(access_token=token, token_type="bearer", user=user_resp)
    )


@router.post("/login", response_model=APIResponse[AuthResponse])
async def login(
    credentials: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email and password and receive an access token."""
    email_clean = credentials.email.strip().lower()

    stmt = select(UserDB).where(UserDB.email == email_clean)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been suspended or deactivated.",
        )

    # Fetch associated profile if exists
    p_stmt = select(ProfileDB).where(ProfileDB.user_id == user.id)
    p_res = await db.execute(p_stmt)
    profile = p_res.scalars().first()

    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        role=user.role,
        is_active=user.is_active,
        profile_id=profile.id if profile else None,
        created_at=user.created_at,
    )

    return APIResponse.success_response(
        AuthResponse(access_token=token, token_type="bearer", user=user_resp)
    )


@router.post("/google", response_model=APIResponse[AuthResponse])
async def google_auth(
    auth_in: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate or auto-register using a Google ID token (One Tap / Sign-in with Google).
    Accepts credential or id_token returned by Google Identity Services in Next.js.
    """
    token_str = (auth_in.credential or auth_in.id_token or "").strip()
    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google credential or id_token is required.",
        )

    # 1. Verify with Google tokeninfo endpoint
    # In development or testing, support mock token: mock_google_<identifier>
    google_data = None
    if settings.ENVIRONMENT != "production" and token_str.startswith("mock_google_"):
        mock_raw = token_str.replace("mock_google_", "")
        mock_email = mock_raw if "@" in mock_raw else f"{mock_raw}@gmail.com"
        google_data = {
            "email": mock_email,
            "name": mock_email.split("@")[0].replace(".", " ").title(),
            "picture": "https://lh3.googleusercontent.com/a/default-user",
            "sub": f"mock_google_sub_{mock_raw}",
            "email_verified": "true",
        }
    else:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(
                    "https://oauth2.googleapis.com/tokeninfo",
                    params={"id_token": token_str},
                )
                if res.status_code != 200:
                    logger.error(f"Google token verification failed: {res.status_code} {res.text}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid or expired Google credential token.",
                    )
                google_data = res.json()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to communicate with Google authentication API: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to verify Google credentials with Google servers.",
            )

    email = google_data.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account did not return an email address.",
        )

    email_clean = email.strip().lower()
    full_name = google_data.get("name") or email_clean.split("@")[0].replace(".", " ").title()
    avatar_url = google_data.get("picture")
    google_id = google_data.get("sub")

    # 2. Check for existing user
    stmt = select(UserDB).where(UserDB.email == email_clean)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if user:
        # Existing account: update linked google_id or avatar if missing
        if not user.google_id and google_id:
            user.google_id = google_id
        if not user.avatar_url and avatar_url:
            user.avatar_url = avatar_url
        if user.auth_provider == "local" and google_id:
            user.auth_provider = "google"
        await db.commit()
        await db.refresh(user)
    else:
        # Auto-register new user
        random_pwd = secrets.token_urlsafe(32)
        user = UserDB(
            email=email_clean,
            hashed_password=get_password_hash(random_pwd),
            full_name=full_name,
            avatar_url=avatar_url,
            role=auth_in.role or "student",
            auth_provider="google",
            google_id=google_id,
            is_active=True,
        )
        db.add(user)
        await db.flush()

        # Provision profile for new student
        profile = ProfileDB(
            user_id=user.id,
            name=user.full_name,
            skills=["Python", "FastAPI", "React"],
            career_interests=["Software Engineering", "AI/ML"],
            preferred_work_modes=["Remote", "Hybrid"],
            preferred_opportunity_types=["Internship", "Full-time"],
        )
        db.add(profile)
        await db.commit()
        await db.refresh(user)

    # 3. Retrieve profile
    p_stmt = select(ProfileDB).where(ProfileDB.user_id == user.id)
    p_res = await db.execute(p_stmt)
    profile = p_res.scalars().first()

    # 4. Issue application JWT token
    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        role=user.role,
        is_active=user.is_active,
        profile_id=profile.id if profile else None,
        created_at=user.created_at,
    )

    return APIResponse.success_response(
        AuthResponse(access_token=token, token_type="bearer", user=user_resp)
    )



@router.get("/me", response_model=APIResponse[UserResponse])
async def get_me(
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details of the currently authenticated user."""
    p_stmt = select(ProfileDB).where(ProfileDB.user_id == current_user.id)
    p_res = await db.execute(p_stmt)
    profile = p_res.scalars().first()

    user_resp = UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        avatar_url=current_user.avatar_url,
        role=current_user.role,
        is_active=current_user.is_active,
        profile_id=profile.id if profile else None,
        created_at=current_user.created_at,
    )
    return APIResponse.success_response(user_resp)


@router.post("/logout", response_model=APIResponse[dict])
async def logout(
    current_user: UserDB = Depends(get_current_user),
):
    """Log out currently active session."""
    return APIResponse.success_response(
        {"message": "Logged out successfully."}
    )
