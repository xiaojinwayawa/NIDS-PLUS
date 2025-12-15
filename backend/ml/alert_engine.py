"""
Alert Engine Module
Handles alert generation, persistence, and querying
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from db.db_manager import SessionLocal
from db.models import AlertModel
from logging_config import app_logger as logger

class AlertEngine:
    """
    Engine for managing alerts
    """
    
    def __init__(self):
        pass

    def generate_alert(self, 
                       packet_info: Dict[str, Any], 
                       prediction_result: Dict[str, Any],
                       model_id: int = None) -> Optional[AlertModel]:
        """
        Generate and persist an alert if threat detected
        
        Args:
            packet_info: Packet metadata (src_ip, dst_ip, etc.)
            prediction_result: Result from inference engine (confidences, etc.)
            model_id: ID of the model used
            
        Returns:
            Created AlertModel or None
        """
        # Determine if alert needed
        # Assuming binary classification: 0=Normal, 1=Attack
        # Or multi-class where prediction is the attack class index
        
        # Simplified logic: if "predictions" is 1 or confidence > threshold
        is_attack = prediction_result.get("is_attack", False)
        if not is_attack:
            # Check if prediction list indicates attack
            preds = prediction_result.get("predictions", [])
            if preds and preds[0] == 1:
                is_attack = True
                
        if not is_attack:
            return None
            
        try:
            # Create alert record
            alert = AlertModel(
                timestamp=datetime.fromtimestamp(packet_info.get("timestamp", 0)),
                src_ip=packet_info.get("src_ip", "0.0.0.0"),
                dst_ip=packet_info.get("dst_ip", "0.0.0.0"),
                src_port=packet_info.get("src_port", 0),
                dst_port=packet_info.get("dst_port", 0),
                protocol=packet_info.get("protocol", "UNKNOWN"),
                attack_type=prediction_result.get("attack_type", "Generic Attack"),
                confidence=prediction_result.get("confidence", 1.0),
                model_id=model_id,
                raw_features=packet_info # Store raw info for forensics
            )
            
            # Persist to DB
            self._save_alert(alert)
            
            logger.info(f"Alert generated: {alert.attack_type} from {alert.src_ip}")
            return alert
            
        except Exception as e:
            logger.error(f"Error generating alert: {e}")
            return None

    def _save_alert(self, alert: AlertModel):
        """Save alert to database"""
        db = SessionLocal()
        try:
            db.add(alert)
            db.commit()
            db.refresh(alert)
        except Exception as e:
            logger.error(f"Database error saving alert: {e}")
            db.rollback()
        finally:
            db.close()

    def get_alerts(self, limit: int = 100, skip: int = 0) -> List[AlertModel]:
        """Get recent alerts"""
        db = SessionLocal()
        try:
            return db.query(AlertModel).order_by(AlertModel.id.desc()).offset(skip).limit(limit).all()
        finally:
            db.close()

    def mark_false_positive(self, alert_id: int, user_id: int) -> bool:
        """Mark an alert as false positive"""
        db = SessionLocal()
        try:
            alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
            if alert:
                alert.is_false_positive = True
                alert.marked_by = user_id
                alert.marked_at = datetime.utcnow()
                db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error marking alert {alert_id}: {e}")
            db.rollback()
            return False
        finally:
            db.close()
