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
    enable_rule_correction: Optional[bool] = None

class GlobalConfigUpdate(BaseModel):
    alert_threshold: Optional[float] = None
    batch_size: Optional[int] = None
    enable_shap: Optional[bool] = None
    log_level: Optional[str] = None
    flow_min_packets: Optional[int] = None
    alert_event_cooldown_seconds: Optional[int] = None
    alert_event_resolve_timeout_seconds: Optional[int] = None
    flow_aggregation_timeout: Optional[float] = None
    flow_idle_timeout: Optional[float] = None
    flow_tcp_timeout: Optional[float] = None
    flow_udp_timeout: Optional[float] = None
    flow_icmp_timeout: Optional[float] = None
    flow_max_packets: Optional[int] = None
    flow_enable_bidirectional: Optional[bool] = None
    pcap_replay_interval: Optional[float] = None
    flow_check_interval: Optional[float] = None
    pipeline_idle_sleep: Optional[float] = None
    flow_cleanup_interval: Optional[float] = None

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
        "log_level": settings.LOG_LEVEL,
        "flow_min_packets": settings.FLOW_MIN_PACKETS,
        "alert_event_cooldown_seconds": settings.ALERT_EVENT_COOLDOWN_SECONDS,
        "alert_event_resolve_timeout_seconds": settings.ALERT_EVENT_RESOLVE_TIMEOUT_SECONDS,
        "flow_aggregation_timeout": settings.FLOW_AGGREGATION_TIMEOUT,
        "flow_idle_timeout": settings.FLOW_IDLE_TIMEOUT,
        "flow_tcp_timeout": settings.FLOW_TCP_TIMEOUT,
        "flow_udp_timeout": settings.FLOW_UDP_TIMEOUT,
        "flow_icmp_timeout": settings.FLOW_ICMP_TIMEOUT,
        "flow_max_packets": settings.FLOW_MAX_PACKETS,
        "flow_enable_bidirectional": settings.FLOW_ENABLE_BIDIRECTIONAL,
        "pcap_replay_interval": settings.PCAP_REPLAY_INTERVAL,
        "flow_check_interval": settings.FLOW_CHECK_INTERVAL,
        "pipeline_idle_sleep": settings.PIPELINE_IDLE_SLEEP,
        "flow_cleanup_interval": settings.FLOW_CLEANUP_INTERVAL,
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
    if config.flow_min_packets is not None:
        settings.FLOW_MIN_PACKETS = config.flow_min_packets
    if config.alert_event_cooldown_seconds is not None:
        settings.ALERT_EVENT_COOLDOWN_SECONDS = config.alert_event_cooldown_seconds
    if config.alert_event_resolve_timeout_seconds is not None:
        settings.ALERT_EVENT_RESOLVE_TIMEOUT_SECONDS = config.alert_event_resolve_timeout_seconds
    if config.flow_aggregation_timeout is not None:
        settings.FLOW_AGGREGATION_TIMEOUT = config.flow_aggregation_timeout
    if config.flow_idle_timeout is not None:
        settings.FLOW_IDLE_TIMEOUT = config.flow_idle_timeout
    if config.flow_tcp_timeout is not None:
        settings.FLOW_TCP_TIMEOUT = config.flow_tcp_timeout
    if config.flow_udp_timeout is not None:
        settings.FLOW_UDP_TIMEOUT = config.flow_udp_timeout
    if config.flow_icmp_timeout is not None:
        settings.FLOW_ICMP_TIMEOUT = config.flow_icmp_timeout
    if config.flow_max_packets is not None:
        settings.FLOW_MAX_PACKETS = config.flow_max_packets
    if config.flow_enable_bidirectional is not None:
        settings.FLOW_ENABLE_BIDIRECTIONAL = config.flow_enable_bidirectional
    if config.pcap_replay_interval is not None:
        settings.PCAP_REPLAY_INTERVAL = config.pcap_replay_interval
    if config.flow_check_interval is not None:
        settings.FLOW_CHECK_INTERVAL = config.flow_check_interval
    if config.pipeline_idle_sleep is not None:
        settings.PIPELINE_IDLE_SLEEP = config.pipeline_idle_sleep
    if config.flow_cleanup_interval is not None:
        settings.FLOW_CLEANUP_INTERVAL = config.flow_cleanup_interval
        
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
    """Start the detection engine"""
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
    """Stop the detection engine"""
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


# ============== Rule Correction Endpoints ==============

@router.get("/rule-correction")
async def get_rule_correction_status(
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Get rule correction status and loaded rules"""
    return engine.rule_engine.get_rules_info()

@router.put("/rule-correction")
async def update_rule_correction(
    enabled: bool,
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Enable or disable rule correction"""
    engine.rule_engine.set_enabled(enabled)
    return {"message": f"Rule correction {'enabled' if enabled else 'disabled'}", "enabled": enabled}


# ============== Fusion Config Endpoints ==============

class FusionConfigUpdate(BaseModel):
    strategy: str = "weighted"
    cascade_threshold: float = 0.7
    weights: Dict[str, float] = {}

@router.get("/fusion-config")
async def get_fusion_config(
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Get model fusion configuration"""
    if engine.inference_engine:
        info = engine.inference_engine.get_model_info()
        return {
            "fusion_strategy": info.get("fusion_strategy", "weighted"),
            "cascade_threshold": getattr(engine.inference_engine, "cascade_threshold", 0.7),
            "model_weights": info.get("model_weights", {})
        }
    return {
        "fusion_strategy": "weighted",
        "cascade_threshold": 0.7,
        "model_weights": {}
    }

@router.put("/fusion-config")
async def update_fusion_config(
    config: FusionConfigUpdate,
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Update model fusion configuration"""
    if engine.inference_engine:
        engine.inference_engine.set_fusion_strategy(
            strategy=config.strategy,
            weights=config.weights,
            cascade_threshold=config.cascade_threshold
        )
        return {"message": "Fusion configuration updated", "config": config.model_dump()}
    raise HTTPException(status_code=400, detail="Inference engine not initialized")
