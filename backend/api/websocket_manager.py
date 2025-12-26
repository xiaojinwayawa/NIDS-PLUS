"""
WebSocket Connection Manager
Handles real-time client connections and broadcasting with JWT authentication.

补充需求 F：生产安全强化（WebSocket/跨域/密钥）
"""
from typing import List, Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import json
import asyncio
from logging_config import app_logger as logger


class AuthenticatedConnection:
    """Represents an authenticated WebSocket connection"""
    def __init__(self, websocket: WebSocket, user_id: int = None, username: str = None):
        self.websocket = websocket
        self.user_id = user_id
        self.username = username
        self.connected_at = datetime.now()
        self.is_authenticated = user_id is not None


class ConnectionManager:
    """
    Manages WebSocket connections with JWT authentication support.
    """
    
    def __init__(self):
        self.active_connections: List[AuthenticatedConnection] = []
        self.require_auth = True  # Can be disabled for development
        
    def set_require_auth(self, require: bool):
        """Enable or disable authentication requirement"""
        self.require_auth = require
        logger.info(f"WebSocket authentication requirement: {require}")
    
    async def connect(self, websocket: WebSocket, user_id: int = None, username: str = None):
        """Accept connection with optional authentication"""
        await websocket.accept()
        
        conn = AuthenticatedConnection(
            websocket=websocket,
            user_id=user_id,
            username=username
        )
        self.active_connections.append(conn)
        
        auth_status = "authenticated" if conn.is_authenticated else "anonymous"
        logger.info(f"WebSocket client connected ({auth_status}). Total: {len(self.active_connections)}")
        
        return conn
    
    async def connect_with_token(self, websocket: WebSocket, token: str = None) -> Optional[AuthenticatedConnection]:
        """
        Connect with JWT token authentication.
        
        Args:
            websocket: WebSocket connection
            token: JWT token for authentication
            
        Returns:
            AuthenticatedConnection if successful, None if auth failed
        """
        user_id = None
        username = None
        
        if token:
            # Verify token
            user_info = self._verify_token(token)
            if user_info:
                user_id = user_info.get("user_id")
                username = user_info.get("username")
        
        # Check if auth is required
        if self.require_auth and user_id is None:
            logger.warning("WebSocket connection rejected: authentication required")
            await websocket.close(code=4001, reason="Authentication required")
            self._log_security_event("ws_auth_failed", {"reason": "no_valid_token"})
            return None
        
        return await self.connect(websocket, user_id, username)
    
    def _verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token and extract user info"""
        try:
            from auth import verify_token
            payload = verify_token(token)
            if payload:
                return {
                    "user_id": payload.get("sub") or payload.get("user_id"),
                    "username": payload.get("username")
                }
        except Exception as e:
            logger.error(f"Token verification error: {e}")
        return None

    def disconnect(self, websocket: WebSocket):
        """Remove connection"""
        for conn in self.active_connections[:]:
            if conn.websocket == websocket:
                self.active_connections.remove(conn)
                logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")
                break

    async def broadcast(self, message: Dict[str, Any], authenticated_only: bool = False):
        """
        Broadcast message to all connected clients.
        
        Args:
            message: Message to broadcast
            authenticated_only: If True, only send to authenticated connections
        """
        if not self.active_connections:
            return
            
        json_msg = json.dumps(message)
        
        for conn in self.active_connections[:]:
            try:
                # Skip unauthenticated if required
                if authenticated_only and not conn.is_authenticated:
                    continue
                    
                await conn.websocket.send_text(json_msg)
            except Exception as e:
                logger.error(f"Error sending to WS client: {e}")
                self.disconnect(conn.websocket)
    
    async def send_to_user(self, user_id: int, message: Dict[str, Any]):
        """Send message to a specific user"""
        json_msg = json.dumps(message)
        
        for conn in self.active_connections[:]:
            if conn.user_id == user_id:
                try:
                    await conn.websocket.send_text(json_msg)
                except Exception as e:
                    logger.error(f"Error sending to user {user_id}: {e}")
                    self.disconnect(conn.websocket)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        authenticated = sum(1 for c in self.active_connections if c.is_authenticated)
        return {
            "total_connections": len(self.active_connections),
            "authenticated": authenticated,
            "anonymous": len(self.active_connections) - authenticated
        }
    
    def _log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security-related events for audit"""
        logger.warning(f"Security event [{event_type}]: {details}")


# Global instance
manager = ConnectionManager()

