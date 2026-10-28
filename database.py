from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine,AsyncEngine,async_sessionmaker,AsyncSession
from sqlalchemy.orm import declarative_base



engine:AsyncEngine = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost:5432/e-commerce")


async_session_local = async_sessionmaker(
    bind = engine,
    expire_on_commit=False,       
    autocommit=False,              
    autoflush=False, 
)


base = declarative_base()

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_local() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    async with engine.begin() as conn:
        # needed by the trigram index on products.name
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(base.metadata.create_all)
        # create_all skips tables that already exist, so add any new indexes on them too
        await conn.run_sync(_create_missing_indexes)


def _create_missing_indexes(sync_conn) -> None:
    for table in base.metadata.sorted_tables:
        for index in table.indexes:
            index.create(sync_conn, checkfirst=True)
