import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dhwani.db")

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass


async def init_db():
    async with engine.begin() as conn:
        # Import models here to register them with Base.metadata before creation
        from app.models import Agent, Call, APIKey
        await conn.run_sync(Base.metadata.create_all)
        
        # Schema migration helper for existing calls table
        import logging
        logger = logging.getLogger("voice-agent")
        
        def migrate_schema(sync_conn):
            cursor = sync_conn.connection.cursor()
            cursor.execute("PRAGMA table_info(calls)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if "summary" not in columns:
                cursor.execute("ALTER TABLE calls ADD COLUMN summary TEXT")
                logger.info("Migrated DB: Added 'summary' column to 'calls' table")
            if "disposition" not in columns:
                cursor.execute("ALTER TABLE calls ADD COLUMN disposition VARCHAR(100)")
                logger.info("Migrated DB: Added 'disposition' column to 'calls' table")
            if "structured_outcome" not in columns:
                cursor.execute("ALTER TABLE calls ADD COLUMN structured_outcome TEXT")
                logger.info("Migrated DB: Added 'structured_outcome' column to 'calls' table")
                
        await conn.run_sync(migrate_schema)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

