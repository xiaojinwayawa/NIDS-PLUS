from fastapi import APIRouter, HTTPException, Depends, Request
from auth import get_current_user, TokenData
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from ml.detection_engine import DetectionEngine, SystemState
from capture.traffic_capture import get_network_interfaces, get_default_interface

from config import settings

router = APIRouter()

class SystemConfig(BaseModel):
    model_name: Optional[str] = None
    dataset_type: Optional[str] = None
    capture_mode: Optional[str] = "pcap" # pcap or live
    source: Optional[str] = None

class GlobalConfigUpdate(BaseModel):
    alert_threshold: Optional[float] = None
    batch_size: Optional[int] = None
    enable_shap: Optional[bool] = None
    log_level: Optional[str] = None

class StartRequest(BaseModel):
    mode: str = "pcap"
    source: Optional[str] = None

def get_engine(request: Request) -> DetectionEngine:
    """Dependency to get DetectionEngine from app state"""
    return request.app.state.engine

@router.get("/config")
async def get_config(current_user: TokenData = Depends(get_current_user)):
    """Get global configuration"""
    return {
        "alert_threshold": settings.ALERT_THRESHOLD,
        "batch_size": settings.BATCH_SIZE,
        "enable_shap": settings.ENABLE_SHAP,
        "log_level": settings.LOG_LEVEL
    }

@router.put("/config")
async def update_config(
    config: GlobalConfigUpdate,
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Update global configuration"""
    # Prevent update if running? Maybe not strict for all params, but for safety yes.
    if engine.state == SystemState.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot update config while running")
        
    if config.alert_threshold is not None:
        settings.ALERT_THRESHOLD = config.alert_threshold
    if config.batch_size is not None:
        settings.BATCH_SIZE = config.batch_size
    if config.enable_shap is not None:
        settings.ENABLE_SHAP = config.enable_shap
    if config.log_level is not None:
        settings.LOG_LEVEL = config.log_level
        
    return {"message": "Configuration updated", "config": config.model_dump(exclude_unset=True)}

@router.get("/status")
async def get_system_status(
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Get system status"""
    status = engine.get_status()
    
    # Add capture status
    if engine.capture:
        status["capture_running"] = engine.capture.is_running
    else:
        status["capture_running"] = False
    
    # Add Redis queue length
    if engine.redis_client:
        try:
            queue_len = engine.redis_client.llen("traffic_queue")
            status["queue_length"] = queue_len
        except:
            status["queue_length"] = -1
    
    return status

@router.post("/start")
async def start_system(
    request: StartRequest,
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Start detection engine"""
    if engine.state == SystemState.RUNNING:
        raise HTTPException(status_code=400, detail="System already running")
    
    # Reset state if in ERROR or STOPPED
    if engine.state in [SystemState.ERROR, SystemState.STOPPED]:
        engine.state = SystemState.IDLE
    
    engine.start(mode=request.mode, source=request.source)
    return {"message": "System started", "mode": request.mode, "state": engine.state.value}

@router.post("/stop")
async def stop_system(
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Stop detection engine"""
    if engine.state == SystemState.STOPPED:
        return {"message": "System already stopped"}
        
    engine.stop()
    return {"message": "System stopped"}

@router.post("/configure")
async def configure_system(
    config: SystemConfig,
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Configure system parameters"""
    if engine.state == SystemState.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot configure while running")
        
    engine.configure(config.model_dump(exclude_unset=True))
    return {"message": "System configured", "config": config.model_dump(exclude_unset=True)}

@router.get("/interfaces")
async def get_interfaces(
    current_user: TokenData = Depends(get_current_user)
):
    """Get available network interfaces for live capture"""
    interfaces = get_network_interfaces()
    default_iface = get_default_interface()
    
    return {
        "interfaces": interfaces,
        "default": default_iface
    }
