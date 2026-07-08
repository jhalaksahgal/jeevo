import redis.asyncio as redis
import json
from typing import Optional, Any
from datetime import timedelta
import logging
from app.config.settings import settings
logger = logging.getLogger(__name__)
class CacheService:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
    async def connect(self):
        try:
            self.redis_client = await redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("✅ Redis connected successfully")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            raise
    async def disconnect(self):
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis disconnected")
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        if not self.redis_client:
            logger.warning(f"Redis not connected, skipping cache set for key: {key}")
            return False
        try:
            if expire is None:
                expire = settings.REDIS_TTL
            serialized_value = json.dumps(value)
            await self.redis_client.setex(
                key,
                expire,
                serialized_value
            )
            return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    async def get(self, key: str) -> Optional[Any]:
        if not self.redis_client:
            logger.warning(f"Redis not connected, skipping cache get for key: {key}")
            return None
        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None
    async def delete(self, key: str) -> bool:
        if not self.redis_client:
            logger.warning(f"Redis not connected, skipping cache delete for key: {key}")
            return False
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    async def exists(self, key: str) -> bool:
        if not self.redis_client:
            logger.warning(f"Redis not connected, skipping cache exists check for key: {key}")
            return False
        try:
            return await self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking cache key {key}: {e}")
            return False
    async def set_session(
        self,
        phone_number: str,
        session_data: dict,
        expire_minutes: Optional[int] = None
    ) -> bool:
        key = f"session:{phone_number}"
        expire_seconds = (expire_minutes or settings.SESSION_EXPIRE_MINUTES) * 60
        return await self.set(key, session_data, expire_seconds)
    async def get_session(self, phone_number: str) -> Optional[dict]:
        key = f"session:{phone_number}"
        return await self.get(key)
    async def delete_session(self, phone_number: str) -> bool:
        key = f"session:{phone_number}"
        return await self.delete(key)
    async def set_user_context(
        self,
        phone_number: str,
        context: dict
    ) -> bool:
        key = f"context:{phone_number}"
        return await self.set(key, context, expire=1800)
    async def get_user_context(self, phone_number: str) -> Optional[dict]:
        key = f"context:{phone_number}"
        return await self.get(key)
    async def cache_risk_level(
        self,
        pincode: str,
        risk_data: dict
    ) -> bool:
        key = f"risk:{pincode}"
        return await self.set(key, risk_data, expire=3600)
    async def get_cached_risk_level(self, pincode: str) -> Optional[dict]:
        key = f"risk:{pincode}"
        return await self.get(key)
    async def increment_counter(self, key: str) -> int:
        if not self.redis_client:
            logger.warning(f"Redis not connected, skipping counter increment for key: {key}")
            return 0
        try:
            return await self.redis_client.incr(key)
        except Exception as e:
            logger.error(f"Error incrementing counter {key}: {e}")
            return 0
    async def get_stats(self) -> dict:
        if not self.redis_client:
            return {"connected": False, "error": "Redis client not initialized"}
        try:
            info = await self.redis_client.info()
            return {
                "connected": True,
                "used_memory": info.get("used_memory_human", "Unknown"),
                "total_keys": await self.redis_client.dbsize(),
                "uptime_seconds": info.get("uptime_in_seconds", 0)
            }
        except Exception as e:
            logger.error(f"Error getting Redis stats: {e}")
            return {"connected": False, "error": str(e)}
cache_service = CacheService()
