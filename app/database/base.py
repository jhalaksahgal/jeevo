from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config.settings import settings
import asyncio, logging
logger = logging.getLogger(__name__)
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite://"):
    if not db_url.startswith("sqlite+aiosqlite"): db_url = db_url.replace("sqlite://", "sqlite+aiosqlite:///")
    engine = create_async_engine(db_url, echo=settings.DATABASE_ECHO, future=True, connect_args={"check_same_thread": False})
else:
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DATABASE_ECHO, future=True, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False)
Base = declarative_base()
async def get_db():
    async with AsyncSessionLocal() as session:
        try: yield session
        finally: await session.close()
get_async_db = get_db
async def init_db(max_retries: int = 10, retry_delay: float = 2.0):
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables initialized")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"DB attempt {attempt + 1}/{max_retries} failed")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"DB init failed: {e}")
                raise
    return False
async def close_db(): await engine.dispose()
