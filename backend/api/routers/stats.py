from fastapi import APIRouter, Depends, Request
from auth import get_current_user, TokenData
from ml.detection_engine import DetectionEngine
import redis
from config import settings

router = APIRouter()

def get_engine(request: Request) -> DetectionEngine:
    return request.app.state.engine

@router.get("/attacks")
async def attack_statistics(
    hours: int = 24,
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """
    Attack type distribution and time series from alerts
    """
    from datetime import datetime, timedelta
    from db.db_manager import SessionLocal
    from db.models import AlertModel
    import collections
    
    since = datetime.utcnow() - timedelta(hours=hours)
    db = SessionLocal()
    try:
        alerts = db.query(AlertModel).filter(AlertModel.timestamp >= since).all()
        dist = collections.Counter([a.attack_type for a in alerts])
        
        # Time series by hour
        ts_map = collections.defaultdict(int)
        for a in alerts:
            key = a.timestamp.strftime("%Y-%m-%d %H:00")
            ts_map[key] += 1
        time_labels = sorted(ts_map.keys())
        time_counts = [ts_map[k] for k in time_labels]
        
        return {
            "distribution": [{"name": k, "value": v} for k, v in dist.items()],
            "time_labels": time_labels,
            "time_counts": time_counts
        }
    finally:
        db.close()
@router.get("/dashboard")
async def get_dashboard_stats(
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """
    Get real-time dashboard statistics
    """
    stats = {
        "system_status": engine.state.value,
        "traffic_queue_size": 0,
        "recent_alerts_count": 0,
        "processed_packets": 0 # TODO: Track this in engine
    }
    
    # Get Queue Size
    try:
        if engine.redis_client:
             stats["traffic_queue_size"] = engine.redis_client.llen("traffic_queue")
    except:
        pass
        
    # Get recent alerts count (simplified, could be optimized)
    # Just getting length of recent alerts
    alerts = engine.alert_engine.get_alerts(limit=100)
    stats["recent_alerts_count"] = len(alerts)
    
    return stats

@router.get("/traffic")
async def get_traffic_stats(
    time_range: str = "1h",
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """
    Get detailed traffic statistics from real captured data
    """
    from datetime import datetime, timedelta
    
    # Get real statistics from the detection engine
    stats = engine.get_traffic_stats()
    
    # If no real data, return empty structure
    if stats["total_packets"] == 0:
        now = datetime.now()
        return {
            "protocols": [{"name": "No Data", "value": 0}],
            "top_ips": [],
            "heatmap": [],
            "ports": ["80", "443", "22", "53", "8080"],
            "time_slots": [(now - timedelta(minutes=i)).strftime("%H:%M") for i in range(10)][::-1],
            "message": "No traffic data collected yet. Start the detection system to capture traffic."
        }
    
    # Fill in time slots if empty
    if not stats["time_slots"]:
        now = datetime.now()
        stats["time_slots"] = [(now - timedelta(minutes=i)).strftime("%H:%M") for i in range(10)][::-1]
    
    return stats
