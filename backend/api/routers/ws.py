from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from api.websocket_manager import manager
from logging_config import app_logger as logger

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates
    Clients receive:
    - New alerts
    - System status changes
    - Real-time statistics
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, maybe receive commands in future
            data = await websocket.receive_text()
            # Echo or process if needed (for now just heartbeat or ignore)
            if data == "ping":
                await websocket.send_text("pong")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
