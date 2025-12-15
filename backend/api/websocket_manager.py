"""
WebSocket Connection Manager
Handles real-time client connections and broadcasting
"""
from typing import List, Dict, Any
from fastapi import WebSocket
import json
import asyncio
from logging_config import app_logger as logger

class ConnectionManager:
    """
    Manages WebSocket connections
    """
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        
    async def connect(self, websocket: WebSocket):
        """Accept connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """
        Broadcast message to all connected clients
        """
        if not self.active_connections:
            return
            
        json_msg = json.dumps(message)
        
        # Iterate over copy to handle disconnections safely
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(json_msg)
            except Exception as e:
                logger.error(f"Error sending to WS client: {e}")
                self.disconnect(connection)

# Global instance
manager = ConnectionManager()
