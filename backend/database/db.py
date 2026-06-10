"""
database/db.py — Async database engine and session factory for RoadSense AI

Uses SQLAlchemy 2.0 async API with aiosqlite for zero-config SQLite storage.
Can be swapped to PostgreSQL by changing DATABASE_URL in .env.
"""

import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from database.models import Base

# ── Database URL ──────────────────────────────────────────────────────────────
# Default: SQLite file in backend/ directory (works out of the box, no server needed)
# Override with env var for PostgreSQL in production:
#   DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname
_raw_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./roadsense.db")

# SQLite needs check_same_thread=False; PostgreSQL doesn't need it
connect_args = {"check_same_thread": False} if _raw_url.startswith("sqlite") else {}

engine = create_async_engine(
    _raw_url,
    connect_args=connect_args,
    echo=False,           # Set True to log all SQL for debugging
    pool_pre_ping=True,
)

# ── SQLite WAL mode (massive write-throughput boost) ─────────────────────────
# WAL (Write-Ahead Logging) allows readers and the streaming writer to work
# concurrently without blocking each other. This is the #1 performance fix
# for SQLite-backed real-time streaming workloads.
if _raw_url.startswith("sqlite"):
    from sqlalchemy import event, text

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")   # concurrent writes without locking
        cursor.execute("PRAGMA synchronous=NORMAL") # safe + fast (vs FULL which is slow)
        cursor.execute("PRAGMA cache_size=-32000")  # 32 MB page cache in RAM
        cursor.execute("PRAGMA temp_store=MEMORY")  # temp tables in RAM
        cursor.close()

# Session factory — use as async context manager
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db():
    """Create all tables if they don't exist. Called once at startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"[DB] Database ready: {_raw_url}")


async def get_db():
    """FastAPI dependency — yields an async session, commits or rolls back."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
