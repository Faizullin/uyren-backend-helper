import json
import websockets
from typing import Dict, Set
from ..database import redis_manager


class WebSocketManager:
    """WebSocket manager for real-time execution updates"""
    
    def __init__(self):
        # Active WebSocket connections {user_id: {execution_id: websocket}}
        self.connections: Dict[str, Dict[str, websockets.WebSocketServerProtocol]] = {}
    
    async def connect(self, websocket: websockets.WebSocketServerProtocol, user_id: str, execution_id: str):
        """Register a new WebSocket connection"""
        if user_id not in self.connections:
            self.connections[user_id] = {}
        
        self.connections[user_id][execution_id] = websocket
        
        # Store connection in Redis for tracking
        connection_id = f"{user_id}_{execution_id}"
        await redis_manager.set_websocket_connection(user_id, execution_id, connection_id)
        
        print(f"WebSocket connected: user {user_id}, execution {execution_id}")
    
    async def disconnect(self, user_id: str, execution_id: str):
        """Remove WebSocket connection"""
        if user_id in self.connections and execution_id in self.connections[user_id]:
            del self.connections[user_id][execution_id]
            
            if not self.connections[user_id]:
                del self.connections[user_id]
        
        print(f"WebSocket disconnected: user {user_id}, execution {execution_id}")
    
    async def send_execution_update(self, user_id: str, execution_id: str, data: Dict):
        """Send execution update to specific user and execution"""
        if user_id in self.connections and execution_id in self.connections[user_id]:
            websocket = self.connections[user_id][execution_id]
            try:
                message = {
                    "type": "execution_update",
                    "execution_id": execution_id,
                    "data": data
                }
                await websocket.send(json.dumps(message))
                print(f"Sent update to user {user_id}, execution {execution_id}")
            except websockets.exceptions.ConnectionClosed:
                await self.disconnect(user_id, execution_id)
            except Exception as e:
                print(f"Error sending WebSocket message: {e}")
                await self.disconnect(user_id, execution_id)
    
    async def broadcast_to_user(self, user_id: str, data: Dict):
        """Broadcast message to all connections for a user"""
        if user_id in self.connections:
            disconnected_executions = []
            
            for execution_id, websocket in self.connections[user_id].items():
                try:
                    message = {
                        "type": "broadcast",
                        "data": data
                    }
                    await websocket.send(json.dumps(message))
                except websockets.exceptions.ConnectionClosed:
                    disconnected_executions.append(execution_id)
                except Exception as e:
                    print(f"Error broadcasting to user {user_id}: {e}")
                    disconnected_executions.append(execution_id)
            
            # Clean up disconnected connections
            for execution_id in disconnected_executions:
                await self.disconnect(user_id, execution_id)


# Global WebSocket manager instance
websocket_manager = WebSocketManager()
