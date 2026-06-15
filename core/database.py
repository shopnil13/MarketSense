from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from core.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables (dev shortcut — use Alembic in production)."""
    async with engine.begin() as conn:
        from core import models  # noqa: F401 — ensure models are registered
        await conn.run_sync(Base.metadata.create_all)
