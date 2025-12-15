from fastapi import APIRouter, HTTPException, Depends, Request, Query
from auth import get_current_user, TokenData
from typing import List, Optional
from ml.detection_engine import DetectionEngine
from pydantic import BaseModel
from datetime import datetime

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
