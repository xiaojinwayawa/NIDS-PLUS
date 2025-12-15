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
    Get detailed traffic statistics (Mocked for prototype)
    Real implementation would query a Time Series DB (InfluxDB/Prometheus) or aggregated SQL
    """
    import random
    from datetime import datetime, timedelta
    
    now = datetime.now()
    
    # 1. Protocol Distribution
    protocols = [
        {"name": "TCP", "value": random.randint(500, 1000)},
        {"name": "UDP", "value": random.randint(200, 500)},
        {"name": "ICMP", "value": random.randint(50, 200)},
        {"name": "HTTP", "value": random.randint(300, 800)},
        {"name": "DNS", "value": random.randint(100, 300)}
    ]
    
    # 2. Top IPs
    top_ips = [
        {"ip": f"192.168.1.{i}", "count": random.randint(100, 5000), "country": "Local"}
        for i in range(1, 11)
    ]
    top_ips.sort(key=lambda x: x["count"], reverse=True)
    
    # 3. Port Activity (Heatmap mock)
    # x: time (last 10 mins), y: common ports
    ports = ["80", "443", "22", "53", "8080"]
    heatmap_data = []
    for i in range(10): # 10 time slots
        for j, port in enumerate(ports):
            heatmap_data.append([i, j, random.randint(0, 100)])
            
    return {
        "protocols": protocols,
        "top_ips": top_ips,
        "heatmap": heatmap_data,
        "ports": ports,
        "time_slots": [(now - timedelta(minutes=i)).strftime("%H:%M") for i in range(10)][::-1]
    }
