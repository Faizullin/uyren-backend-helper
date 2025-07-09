import redis.asyncio as redis
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from .config import settings


class RedisManager:
    """Redis manager for temporary execution tracking and WebSocket management"""
    
    def __init__(self):
        self.redis_url = settings.redis_url
        self._redis = None
    
    async def get_redis(self) -> redis.Redis:
        """Get Redis connection"""
        if self._redis is None:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf8",
                decode_responses=True
            )
        return self._redis
    
    async def close(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
    
    async def set_execution_data(self, execution_id: str, data: Dict[str, Any]) -> bool:
        """Store execution data temporarily"""
        try:
            redis_client = await self.get_redis()
            key = f"execution:{execution_id}"
            serialized_data = json.dumps(data, default=str)
            await redis_client.setex(key, settings.execution_ttl, serialized_data)
            return True
        except Exception as e:
            print(f"Redis set error: {e}")
            return False
    
    async def get_execution_data(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution data"""
        try:
            redis_client = await self.get_redis()
            key = f"execution:{execution_id}"
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"Redis get error: {e}")
            return None
    
    async def update_execution_status(self, execution_id: str, status: str, **kwargs) -> bool:
        """Update execution status and additional data"""
        try:
            existing_data = await self.get_execution_data(execution_id)
            if existing_data:
                existing_data.update({
                    'status': status,
                    'updated_at': datetime.utcnow().isoformat(),
                    **kwargs
                })
                return await self.set_execution_data(execution_id, existing_data)
            return False
        except Exception as e:
            print(f"Redis update error: {e}")
            return False
    
    async def delete_execution_data(self, execution_id: str) -> bool:
        """Delete execution data"""
        try:
            redis_client = await self.get_redis()
            key = f"execution:{execution_id}"
            await redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Redis delete error: {e}")
            return False
    
    async def set_websocket_connection(self, user_id: str, execution_id: str, connection_id: str) -> bool:
        """Track WebSocket connection for real-time updates"""
        try:
            redis_client = await self.get_redis()
            key = f"websocket:{execution_id}:{user_id}"
            await redis_client.setex(key, settings.execution_ttl, connection_id)
            return True
        except Exception as e:
            print(f"WebSocket tracking error: {e}")
            return False
    
    async def get_websocket_connection(self, user_id: str, execution_id: str) -> Optional[str]:
        """Get WebSocket connection ID"""
        try:
            redis_client = await self.get_redis()
            key = f"websocket:{execution_id}:{user_id}"
            return await redis_client.get(key)
        except Exception as e:
            print(f"WebSocket get error: {e}")
            return None


# Global Redis manager instance
redis_manager = RedisManager()
