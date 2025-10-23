from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine, async_sessionmaker
from sqlalchemy.orm import declarative_base
import logging

from misc.settings import settings


logger = logging.getLogger(__name__)

class Database:

    BASE = declarative_base()

    def __init__(self, 
                 db_url: str) -> None:
        logger.debug(f"Initializing database with URL: {db_url}")
        
        self._async_engine = create_async_engine(settings.database_url, echo=False)
        
        self._AsyncSessionLocal = async_sessionmaker(self._async_engine, 
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False)
    
    async def create_tables(self) -> None:
        logger.debug("Creating tables by models")
        
        async with self._async_engine.begin() as conn:
            await conn.run_sync(self.BASE.metadata.create_all) 
        
        logger.debug("Creation completed")

    @property
    def engine(self) -> AsyncEngine:
        return self._async_engine

    @property
    def session(self) -> AsyncSession:
        logger.debug("Creating new database session")
        return self._AsyncSessionLocal()