import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import UserDB
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)


class UserService:
    @staticmethod
    async def seed_default_user(db: AsyncSession) -> Optional[UserDB]:
        """Seed the default demo user (Alex Morgan) if not present."""
        email = "alex.morgan@pathbridge.ai"
        stmt = select(UserDB).where(UserDB.email == email)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if user:
            return user

        user = UserDB(
            id="user_default",
            email=email,
            hashed_password=get_password_hash("Password123!"),
            full_name="Alex Morgan",
            avatar_url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=256",
            role="student",
            is_active=True,
        )
        db.add(user)
        try:
            await db.commit()
            await db.refresh(user)
            logger.info(f"Seeded default demo user: {email} (id: {user.id})")
            return user
        except Exception as e:
            logger.error(f"Error seeding default user: {e}")
            await db.rollback()
            return None


user_service = UserService()
