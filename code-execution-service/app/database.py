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
    
    async def list_all_executions(self, limit: int = 100) -> list[Dict[str, Any]]:
        """List all executions stored in Redis"""
        try:
            redis_client = await self.get_redis()
            
            # Get all execution keys
            keys = await redis_client.keys("execution:*")
            
            # Limit the results
            if len(keys) > limit:
                keys = keys[:limit]
            
            executions = []
            for key in keys:
                data = await redis_client.get(key)
                if data:
                    try:
                        execution_data = json.loads(data)
                        executions.append(execution_data)
                    except json.JSONDecodeError:
                        print(f"Failed to decode execution data for key: {key}")
                        continue
            
            # Sort by created_at (newest first)
            executions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            return executions
        except Exception as e:
            print(f"List executions error: {e}")
            return []
    
    async def list_executions_by_user(self, user_id: str, limit: int = 50) -> list[Dict[str, Any]]:
        """List executions for a specific user"""
        try:
            all_executions = await self.list_all_executions(limit * 2)  # Get more to filter
            
            # Filter by user_id
            user_executions = [
                execution for execution in all_executions 
                if execution.get("user_id") == user_id
            ]
            
            # Limit results
            return user_executions[:limit]
        except Exception as e:
            print(f"List user executions error: {e}")
            return []

# Global Redis manager instance
redis_manager = RedisManager()
