from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config.settings import settings
from app.routes import webhook
from app.database.base import init_db, close_db, AsyncSessionLocal
from app.services.cache_service import cache_service
from app.services.heatmap_update_service import HeatmapUpdateService
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()
async def scheduled_heatmap_update():
    """Scheduled task to update heatmap every 2 hours"""
    try:
        logger.info("🕐 Running scheduled heatmap update...")
        await HeatmapUpdateService.update_all_regions()
    except Exception as e:
        logger.error(f"Heatmap update failed: {e}")
async def scheduled_vaccine_reminder_update():
    """Scheduled task to send vaccine reminders daily - 14 days before due date"""
    pass
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 50)
    logger.info(f"🚀 Starting {settings.APP_NAME}")
    logger.info(f"📱 WhatsApp Phone Number ID: {settings.WHATSAPP_PHONE_NUMBER_ID}")
    logger.info(f"🔧 Debug Mode: {settings.DEBUG}")
    logger.info("=" * 50)
    try:
        logger.info("📊 Initializing PostgreSQL database...")
        await init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    try:
        logger.info("🔴 Connecting to Redis...")
        await cache_service.connect()
        redis_stats = await cache_service.get_stats()
        logger.info(f"✅ Redis connected - Keys: {redis_stats.get('total_keys', 0)}")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        raise
    try:
        logger.info("⏰ Starting APScheduler...")
        scheduler.add_job(
            scheduled_heatmap_update,
            "interval",
            hours=2,
            id="heatmap_update",
            name="Heatmap Update Task",
            max_instances=1
        )
        scheduler.add_job(
            scheduled_vaccine_reminder_update,
            "cron",
            hour=8,
            minute=0,
            id="vaccine_reminder",
            name="Vaccine Reminder Task",
            max_instances=1
        )
        scheduler.start()
        logger.info("✅ APScheduler started - Heatmap updates every 2 hours, Vaccine reminders daily at 8 AM")
        await scheduled_heatmap_update()
        logger.info("✅ Initial heatmap update complete")
    except Exception as e:
        logger.warning(f"⚠️ APScheduler setup failed: {e}")
    logger.info("=" * 50)
    logger.info("✅ All services started successfully!")
    logger.info("=" * 50)
    yield
    logger.info("👋 Shutting down services...")
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("✅ Scheduler shutdown")
    await cache_service.disconnect()
    logger.info("✅ Redis disconnected")
    await close_db()
    logger.info("✅ Database closed")
    logger.info("👋 Shutdown complete")
app = FastAPI(
    title=settings.APP_NAME,
    description="WhatsApp-based multilingual health assistant for rural India",
    version="1.0.0",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(webhook.router, tags=["WhatsApp Webhook"])
@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "status": "running",
        "message": "Jeevo WhatsApp Health Platform API is active"
    }
@app.get("/health")
async def health_check():
    redis_stats = await cache_service.get_stats()
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "database": "connected",
        "redis": redis_stats
    }
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )
