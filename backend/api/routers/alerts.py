from fastapi import APIRouter, HTTPException, Depends, Request, Query
from auth import get_current_user, TokenData
from typing import List, Optional
from ml.detection_engine import DetectionEngine
from pydantic import BaseModel
from datetime import datetime, timedelta
import random

router = APIRouter()

def get_engine(request: Request) -> DetectionEngine:
    return request.app.state.engine

class AlertOut(BaseModel):
    id: int
    timestamp: datetime
    src_ip: str
    dst_ip: str
    protocol: Optional[str] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    attack_type: str
    confidence: float
    is_false_positive: bool
    
    class Config:
        from_attributes = True

class AlertDetailOut(BaseModel):
    id: int
    timestamp: datetime
    src_ip: str
    dst_ip: str
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    protocol: Optional[str] = None
    attack_type: str
    confidence: float
    is_false_positive: bool
    raw_features: Optional[dict] = None
    shap_analysis: Optional[dict] = None
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[AlertOut])
async def get_alerts(
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Get recent alerts"""
    return engine.alert_engine.get_alerts(limit=limit, skip=skip)

@router.get("/{alert_id}", response_model=AlertDetailOut)
async def get_alert_detail(
    alert_id: int,
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Get alert detail"""
    from db.db_manager import SessionLocal
    from db.models import AlertModel
    db = SessionLocal()
    try:
        rec = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
        if not rec:
            raise HTTPException(status_code=404, detail="Alert not found")
        # Extract shap if present in raw_features
        shap_analysis = None
        if rec.raw_features and isinstance(rec.raw_features, dict):
            shap_analysis = rec.raw_features.get("shap_analysis")
        return AlertDetailOut(
            id=rec.id,
            timestamp=rec.timestamp,
            src_ip=rec.src_ip,
            dst_ip=rec.dst_ip,
            src_port=rec.src_port,
            dst_port=rec.dst_port,
            protocol=rec.protocol,
            attack_type=rec.attack_type,
            confidence=rec.confidence,
            is_false_positive=rec.is_false_positive,
            raw_features=rec.raw_features,
            shap_analysis=shap_analysis
        )
    finally:
        db.close()

@router.post("/{alert_id}/false_positive")
async def mark_false_positive(
    alert_id: int,
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Mark alert as false positive"""
    success = engine.alert_engine.mark_false_positive(alert_id, current_user.user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert marked as false positive"}


@router.post("/test/generate")
async def generate_test_alerts(
    count: int = Query(10, ge=1, le=100),
    current_user: TokenData = Depends(get_current_user)
):
    """Generate test alerts for testing purposes"""
    from db.db_manager import SessionLocal
    from db.models import AlertModel
    
    attack_types = [
        "DDoS", "Port Scan", "Brute Force", "SQL Injection", 
        "XSS", "FTP-Patator", "SSH-Patator", "Bot", "Infiltration", "Heartbleed"
    ]
    protocols = ["TCP", "UDP", "ICMP", "HTTP", "HTTPS", "SSH", "FTP"]
    
    db = SessionLocal()
    created_alerts = []
    
    try:
        for i in range(count):
            # Generate random alert data
            alert = AlertModel(
                timestamp=datetime.utcnow() - timedelta(minutes=random.randint(0, 60)),
                src_ip=f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
                dst_ip=f"10.0.{random.randint(1, 255)}.{random.randint(1, 255)}",
                src_port=random.randint(1024, 65535),
                dst_port=random.choice([22, 80, 443, 3306, 8080, 21, 23, 25]),
                protocol=random.choice(protocols),
                attack_type=random.choice(attack_types),
                confidence=round(random.uniform(0.6, 0.99), 4),
                model_id=1,
                raw_features={
                    "flow_duration": random.randint(1000, 100000),
                    "total_fwd_packets": random.randint(1, 1000),
                    "total_bwd_packets": random.randint(1, 500),
                    "flow_bytes_per_s": random.uniform(100, 10000)
                }
            )
            db.add(alert)
            created_alerts.append({
                "attack_type": alert.attack_type,
                "src_ip": alert.src_ip,
                "confidence": alert.confidence
            })
        
        db.commit()
        
        return {
            "message": f"Generated {count} test alerts",
            "alerts": created_alerts
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.delete("/test/clear")
async def clear_test_alerts(
    current_user: TokenData = Depends(get_current_user)
):
    """Clear all alerts (for testing purposes)"""
    from db.db_manager import SessionLocal
    from db.models import AlertModel
    
    db = SessionLocal()
    try:
        count = db.query(AlertModel).delete()
        db.commit()
        return {"message": f"Deleted {count} alerts"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
