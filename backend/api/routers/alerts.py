from fastapi import APIRouter, HTTPException, Depends, Request, Query
from auth import get_current_user, TokenData
from typing import List, Optional, Dict, Any
from ml.detection_engine import DetectionEngine
from ml.false_positive_manager import FalsePositiveManager, GovernanceRule
from pydantic import BaseModel
from datetime import datetime, timedelta
import random

router = APIRouter()

# FP Manager instance
_fp_manager: Optional[FalsePositiveManager] = None

def get_fp_manager() -> FalsePositiveManager:
    global _fp_manager
    if _fp_manager is None:
        _fp_manager = FalsePositiveManager()
    return _fp_manager

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
    from db.models import AlertModel, ModelModel
    from api.websocket_manager import manager as ws_manager
    
    attack_types = [
        "DDoS", "Port Scan", "Brute Force", "SQL Injection", 
        "XSS", "FTP-Patator", "SSH-Patator", "Bot", "Infiltration", "Heartbleed"
    ]
    protocols = ["TCP", "UDP", "ICMP", "HTTP", "HTTPS", "SSH", "FTP"]
    
    db = SessionLocal()
    created_alerts = []
    ws_alerts = []
    
    try:
        # Get an existing model_id or use None
        model = db.query(ModelModel).first()
        model_id = model.id if model else None
        
        for i in range(count):
            # Generate random alert data (use current time for better testing)
            alert = AlertModel(
                timestamp=datetime.utcnow(),
                src_ip=f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
                dst_ip=f"10.0.{random.randint(1, 255)}.{random.randint(1, 255)}",
                src_port=random.randint(1024, 65535),
                dst_port=random.choice([22, 80, 443, 3306, 8080, 21, 23, 25]),
                protocol=random.choice(protocols),
                attack_type=random.choice(attack_types),
                confidence=round(random.uniform(0.6, 0.99), 4),
                model_id=model_id,
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
            ws_alerts.append(alert)
        
        db.commit()
        
        # Broadcast alerts via WebSocket for Dashboard display
        for alert in ws_alerts:
            # Get severity based on confidence
            confidence = alert.confidence
            if confidence >= 0.9:
                severity = "critical"
            elif confidence >= 0.8:
                severity = "high"
            elif confidence >= 0.6:
                severity = "medium"
            else:
                severity = "low"
            
            alert_msg = {
                "type": "alert",
                "data": {
                    "id": alert.id,
                    "timestamp": alert.timestamp.isoformat(),
                    "src_ip": alert.src_ip,
                    "dst_ip": alert.dst_ip,
                    "protocol": alert.protocol or "TCP",
                    "attack_type": alert.attack_type,
                    "confidence": confidence,
                    "severity": severity,
                    "shap_analysis": None
                }
            }
            await ws_manager.broadcast(alert_msg)
        
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


# ============== FP Governance Endpoints ==============

@router.get("/governance/rules")
async def get_governance_rules(
    current_user: TokenData = Depends(get_current_user),
    fp_manager: FalsePositiveManager = Depends(get_fp_manager)
):
    """Get all governance rules"""
    return fp_manager.get_all_rules()

@router.get("/governance/suggestions")
async def get_governance_suggestions(
    current_user: TokenData = Depends(get_current_user),
    fp_manager: FalsePositiveManager = Depends(get_fp_manager)
):
    """Get governance suggestions based on FP patterns"""
    return fp_manager.generate_governance_suggestions()

@router.get("/governance/metrics")
async def get_governance_metrics(
    current_user: TokenData = Depends(get_current_user),
    fp_manager: FalsePositiveManager = Depends(get_fp_manager)
):
    """Get FP/FN metrics comparison"""
    return fp_manager.get_metrics_comparison()

@router.put("/governance/rules/{rule_id}/toggle")
async def toggle_governance_rule(
    rule_id: str,
    is_active: bool = Query(...),
    current_user: TokenData = Depends(get_current_user),
    fp_manager: FalsePositiveManager = Depends(get_fp_manager)
):
    """Toggle a governance rule on/off"""
    success = fp_manager.toggle_rule(rule_id, is_active)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"message": "Rule updated", "is_active": is_active}

@router.delete("/governance/rules/{rule_id}")
async def delete_governance_rule(
    rule_id: str,
    current_user: TokenData = Depends(get_current_user),
    fp_manager: FalsePositiveManager = Depends(get_fp_manager)
):
    """Delete a governance rule"""
    success = fp_manager.remove_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"message": "Rule deleted"}

class SuggestionApply(BaseModel):
    type: str
    ip: Optional[str] = None
    port: Optional[int] = None
    feature: Optional[str] = None
    current_threshold: Optional[float] = None
    suggested_threshold: Optional[float] = None
    avg_value: Optional[float] = None
    confidence: Optional[float] = None

@router.post("/governance/apply-suggestion")
async def apply_governance_suggestion(
    suggestion: SuggestionApply,
    current_user: TokenData = Depends(get_current_user),
    fp_manager: FalsePositiveManager = Depends(get_fp_manager)
):
    """Apply a governance suggestion as a rule"""
    import time
    
    rule_id = f"manual_{suggestion.type}_{int(time.time())}"
    
    if suggestion.type == "whitelist_ip" and suggestion.ip:
        rule = GovernanceRule(
            rule_id=rule_id,
            rule_type="whitelist",
            created_at=datetime.now(),
            whitelist_ips=[suggestion.ip]
        )
    elif suggestion.type == "whitelist_port" and suggestion.port:
        rule = GovernanceRule(
            rule_id=rule_id,
            rule_type="whitelist",
            created_at=datetime.now(),
            whitelist_ports=[suggestion.port]
        )
    elif suggestion.type == "threshold" and suggestion.suggested_threshold:
        rule = GovernanceRule(
            rule_id=rule_id,
            rule_type="threshold",
            created_at=datetime.now(),
            threshold_adjustment=(suggestion.suggested_threshold - (suggestion.current_threshold or 0.5))
        )
    elif suggestion.type == "feature_rule" and suggestion.feature:
        rule = GovernanceRule(
            rule_id=rule_id,
            rule_type="feature_rule",
            created_at=datetime.now(),
            feature_name=suggestion.feature,
            feature_condition="lt",
            feature_value=suggestion.avg_value or 0
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid suggestion type or missing parameters")
    
    fp_manager.add_rule(rule)
    return {"message": "Suggestion applied", "rule_id": rule_id}

@router.get("/governance/feedback-summary")
async def get_feedback_summary(
    current_user: TokenData = Depends(get_current_user),
    fp_manager: FalsePositiveManager = Depends(get_fp_manager)
):
    """Get summary of false positive feedbacks"""
    return fp_manager.get_feedback_summary()
