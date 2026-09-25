import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from app.core.config import settings
from app.db.base import Base

# Import all models so Base knows about all tables
from app.models.user import UserDB
from app.models.profile import ProfileDB
from app.models.opportunity import OpportunityDB
from app.models.recommendation import RecommendationDB
from app.models.verification import VerificationDB
from app.models.application import ApplicationDB

logger = logging.getLogger(__name__)

def get_database_url() -> str:
    url = settings.DATABASE_URL.strip()
    if "<DB-PASSWORD>" in url or ("<" in url and ">" in url):
        logger.warning(
            "DATABASE_URL contains an unpopulated placeholder ('<DB-PASSWORD>'). "
            "Please replace <DB-PASSWORD> in .env with your Supabase database password. "
            "Using local SQLite database in the interim."
        )
        return "sqlite+aiosqlite:///./pathbridge.db"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # asyncpg requires ssl parameter instead of sslmode
    if "sslmode=" in url:
        url = url.replace("sslmode=require", "ssl=require").replace("sslmode=prefer", "ssl=prefer").replace("sslmode=disable", "ssl=disable")
    return url

db_url = get_database_url()

# Configure engine kwargs
engine_kwargs = {"echo": False}
if "sqlite" in db_url:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    # If in-memory or single file
    if ":memory:" in db_url:
        engine_kwargs["poolclass"] = StaticPool

engine = create_async_engine(db_url, **engine_kwargs)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def init_db() -> None:
    """Initialize database tables and handle fallback gracefully if Postgres connection fails."""
    global engine, AsyncSessionLocal
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Ensure newly added columns exist in existing SQLite databases
            from sqlalchemy import text
            for col_sql in [
                "ALTER TABLE users ADD COLUMN auth_provider VARCHAR(32) DEFAULT 'local'",
                "ALTER TABLE users ADD COLUMN google_id VARCHAR(128)",
            ]:
                try:
                    await conn.execute(text(col_sql))
                except Exception:
                    pass
        logger.info(f"Database initialized successfully with URL pattern: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    except Exception as e:
        logger.warning(f"Failed to connect to primary DB ({db_url}): {e}. Falling back to SQLite for MVP demo stability.")
        sqlite_url = "sqlite+aiosqlite:///./pathbridge.db"
        engine = create_async_engine(sqlite_url, connect_args={"check_same_thread": False})
        AsyncSessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            from sqlalchemy import text
            for col_sql in [
                "ALTER TABLE users ADD COLUMN auth_provider VARCHAR(32) DEFAULT 'local'",
                "ALTER TABLE users ADD COLUMN google_id VARCHAR(128)",
            ]:
                try:
                    await conn.execute(text(col_sql))
                except Exception:
                    pass
        logger.info("Fallback SQLite database initialized successfully at ./pathbridge.db")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
