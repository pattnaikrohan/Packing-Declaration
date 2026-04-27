from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# Convert sqlite:///./data/pkd.db  →  sqlite+aiosqlite:///./data/pkd.db
_db_url = settings.DATABASE_URL
if _db_url.startswith("sqlite:///") and "aiosqlite" not in _db_url:
    _db_url = _db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

engine = create_async_engine(
    _db_url,
    connect_args={"check_same_thread": False} if "sqlite" in _db_url else {},
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Create all tables (used as a fallback for dev; Alembic is preferred)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
