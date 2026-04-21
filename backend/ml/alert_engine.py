"""
Alert Engine Module
Handles alert generation, persistence, and querying
"""
from copy import deepcopy
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from db.db_manager import SessionLocal
from db.models import AlertModel
from config import settings
from logging_config import app_logger as logger

class AlertEngine:
    """
    Engine for managing alerts
    """
    
    def __init__(self):
        pass

    def _build_event_payload(
        self,
        *,
        first_seen: datetime,
        last_seen: datetime,
        repeat_count: int,
        status: str
    ) -> Dict[str, Any]:
        duration_seconds = max(0, int((last_seen - first_seen).total_seconds()))
        return {
            "first_seen": first_seen.isoformat(),
            "last_seen": last_seen.isoformat(),
            "repeat_count": repeat_count,
            "status": status,
            "duration_seconds": duration_seconds,
            "cooldown_seconds": settings.ALERT_EVENT_COOLDOWN_SECONDS,
            "resolve_timeout_seconds": settings.ALERT_EVENT_RESOLVE_TIMEOUT_SECONDS,
        }

    def _parse_event_time(self, value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _get_event_payload(self, alert: AlertModel) -> Dict[str, Any]:
        raw_features = alert.raw_features if isinstance(alert.raw_features, dict) else {}
        event = raw_features.get("event", {})
        first_seen = self._parse_event_time(event.get("first_seen")) or alert.timestamp or datetime.utcnow()
        last_seen = self._parse_event_time(event.get("last_seen")) or alert.timestamp or first_seen
        repeat_count = int(event.get("repeat_count", 1))
        status = event.get("status", "active")
        return self._build_event_payload(
            first_seen=first_seen,
            last_seen=last_seen,
            repeat_count=repeat_count,
            status=status,
        )

    def _resolve_status(self, event: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.utcnow()
        last_seen = self._parse_event_time(event.get("last_seen")) or now
        resolved = (now - last_seen) > timedelta(seconds=settings.ALERT_EVENT_RESOLVE_TIMEOUT_SECONDS)
        event["status"] = "resolved" if resolved else "active"
        event["duration_seconds"] = max(
            0,
            int((last_seen - (self._parse_event_time(event.get("first_seen")) or last_seen)).total_seconds())
        )
        return event

    def _decorate_alert_dict(self, alert: AlertModel, now: Optional[datetime] = None) -> Dict[str, Any]:
        event = self._resolve_status(self._get_event_payload(alert), now=now)
        return {
            "id": alert.id,
            "timestamp": alert.timestamp,
            "src_ip": alert.src_ip,
            "dst_ip": alert.dst_ip,
            "src_port": alert.src_port,
            "dst_port": alert.dst_port,
            "protocol": alert.protocol,
            "attack_type": alert.attack_type,
            "confidence": alert.confidence,
            "is_false_positive": alert.is_false_positive,
            "first_seen": event["first_seen"],
            "last_seen": event["last_seen"],
            "repeat_count": event["repeat_count"],
            "event_status": event["status"],
            "duration_seconds": event["duration_seconds"],
        }

    def generate_alert(self, 
                       packet_info: Dict[str, Any], 
                       prediction_result: Dict[str, Any],
                       model_id: Optional[int] = None) -> Optional[AlertModel]:
        """
        Generate and persist an alert if threat detected
        
        Args:
            packet_info: Packet metadata (src_ip, dst_ip, etc.)
            prediction_result: Result from inference engine (confidences, etc.)
            model_id: ID of the model used (can be None)
            
        Returns:
            Created AlertModel or None
        """
        # Determine if alert needed
        # Assuming binary classification: 0=Normal, 1=Attack
        # Or multi-class where prediction is the attack class index
        
        # Simplified logic: if "predictions" is 1 or confidence > threshold
        is_attack = prediction_result.get("is_attack", False)
        confidence = prediction_result.get("confidence", 0)
        
        if not is_attack:
            # Check if prediction list indicates attack
            preds = prediction_result.get("predictions", [])
            if preds and preds[0] == 1:
                is_attack = True
            # Also alert on high confidence even if model says normal (for detection of Nmap scans)
            elif confidence > 0.5:
                is_attack = True
                
        if not is_attack:
            return None
            
        db = SessionLocal()
        try:
            # Handle timestamp - could be float, int, or missing
            pkt_timestamp = packet_info.get("timestamp", 0)
            if isinstance(pkt_timestamp, (int, float)) and pkt_timestamp > 0:
                alert_timestamp = datetime.fromtimestamp(pkt_timestamp)
            else:
                alert_timestamp = datetime.utcnow()

            src_ip = packet_info.get("src_ip", "0.0.0.0")
            attack_type = prediction_result.get("attack_type", "Generic Attack")
            confidence = float(prediction_result.get("confidence", 1.0))

            existing = db.query(AlertModel)\
                .filter(
                    AlertModel.src_ip == src_ip,
                    AlertModel.attack_type == attack_type
                )\
                .order_by(AlertModel.timestamp.desc())\
                .first()

            if existing:
                current_event = self._get_event_payload(existing)
                last_seen = self._parse_event_time(current_event["last_seen"]) or existing.timestamp or alert_timestamp
                first_seen = self._parse_event_time(current_event["first_seen"]) or existing.timestamp or alert_timestamp
                delta_seconds = max(0.0, (alert_timestamp - last_seen).total_seconds())

                if delta_seconds <= settings.ALERT_EVENT_RESOLVE_TIMEOUT_SECONDS:
                    merged_raw_features = deepcopy(existing.raw_features) if isinstance(existing.raw_features, dict) else {}
                    for key, value in packet_info.items():
                        if key != "event":
                            merged_raw_features[key] = value

                    merged_raw_features["event"] = self._build_event_payload(
                        first_seen=first_seen,
                        last_seen=alert_timestamp,
                        repeat_count=int(current_event["repeat_count"]) + 1,
                        status="active",
                    )

                    existing.timestamp = alert_timestamp
                    existing.dst_ip = packet_info.get("dst_ip", existing.dst_ip)
                    existing.src_port = packet_info.get("src_port", existing.src_port)
                    existing.dst_port = packet_info.get("dst_port", existing.dst_port)
                    existing.protocol = packet_info.get("protocol", existing.protocol)
                    existing.confidence = max(float(existing.confidence or 0.0), confidence)
                    existing.raw_features = merged_raw_features

                    setattr(existing, "_event_action", "merged")
                    setattr(existing, "_suppress_broadcast", delta_seconds < settings.ALERT_EVENT_COOLDOWN_SECONDS)

                    db.commit()
                    db.refresh(existing)
                    logger.info(
                        f"Alert event updated: {existing.attack_type} from {existing.src_ip}, "
                        f"repeat_count={merged_raw_features['event']['repeat_count']}"
                    )
                    return existing

                # Previous event is stale; mark it resolved and create a new event record.
                stale_raw_features = deepcopy(existing.raw_features) if isinstance(existing.raw_features, dict) else {}
                stale_raw_features["event"] = self._build_event_payload(
                    first_seen=first_seen,
                    last_seen=last_seen,
                    repeat_count=int(current_event["repeat_count"]),
                    status="resolved",
                )
                existing.raw_features = stale_raw_features
                db.flush()

            raw_features = deepcopy(packet_info)
            raw_features["event"] = self._build_event_payload(
                first_seen=alert_timestamp,
                last_seen=alert_timestamp,
                repeat_count=1,
                status="active",
            )

            alert = AlertModel(
                timestamp=alert_timestamp,
                src_ip=src_ip,
                dst_ip=packet_info.get("dst_ip", "0.0.0.0"),
                src_port=packet_info.get("src_port", 0),
                dst_port=packet_info.get("dst_port", 0),
                protocol=packet_info.get("protocol", "UNKNOWN"),
                attack_type=attack_type,
                confidence=confidence,
                model_id=model_id,
                raw_features=raw_features
            )

            db.add(alert)
            db.commit()
            db.refresh(alert)

            setattr(alert, "_event_action", "created")
            setattr(alert, "_suppress_broadcast", False)

            logger.info(f"Alert generated: {alert.attack_type} from {alert.src_ip}")
            return alert

        except Exception as e:
            logger.error(f"Error generating alert: {e}")
            db.rollback()
            return None
        finally:
            db.close()

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

    def get_alerts(self, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """Get recent alerts"""
        db = SessionLocal()
        try:
            alerts = db.query(AlertModel).order_by(AlertModel.timestamp.desc()).offset(skip).limit(limit).all()
            now = datetime.utcnow()
            return [self._decorate_alert_dict(alert, now=now) for alert in alerts]
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return []
        finally:
            db.close()

    def mark_false_positive(self, alert_id: int, user_id: int) -> bool:
        """Mark an alert as false positive and save features for continuous learning"""
        db = SessionLocal()
        try:
            alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
            if alert:
                alert.is_false_positive = True
                alert.marked_by = user_id
                alert.marked_at = datetime.utcnow()
                db.commit()
                
                # Extract and save features for Human-in-the-Loop continuous learning
                if alert.raw_features and isinstance(alert.raw_features, dict):
                    self._save_fp_features_to_csv(alert.raw_features)
                    
                return True
            return False
        except Exception as e:
            logger.error(f"Error marking alert {alert_id}: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    def unmark_false_positive(self, alert_id: int) -> bool:
        """Unmark an alert as false positive and remove its features from continuous learning"""
        db = SessionLocal()
        try:
            alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
            if alert and alert.is_false_positive:
                alert.is_false_positive = False
                alert.marked_by = None
                alert.marked_at = None
                db.commit()
                
                # Remove features from Human-in-the-Loop continuous learning
                if alert.raw_features and isinstance(alert.raw_features, dict):
                    self._remove_fp_features_from_csv(alert.raw_features)
                    
                return True
            return False
        except Exception as e:
            logger.error(f"Error unmarking alert {alert_id}: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    def _save_fp_features_to_csv(self, raw_features: dict):
        """Save false positive raw features to a dedicated CSV for model retraining"""
        import os
        import pandas as pd
        import numpy as np
        
        # Get project root and data dir
        current_file = os.path.abspath(__file__)
        ml_dir = os.path.dirname(current_file)
        backend_dir = os.path.dirname(ml_dir)
        project_root = os.path.dirname(backend_dir)
        data_dir = os.path.join(project_root, "data", "fp_governance")
        os.makedirs(data_dir, exist_ok=True)
        
        fp_csv_path = os.path.join(data_dir, "human_feedback_fp.csv")
        
        try:
            # Flatten features and set label to 0 (Normal) since it's a false positive
            flat_features = {}
            for k, v in raw_features.items():
                # Skip non-numeric or nested dicts (like shap_analysis)
                if isinstance(v, (int, float, bool)):
                    flat_features[k] = float(v)
            
            if not flat_features:
                logger.warning("No numeric features found in alert raw_features to save.")
                return
                
            flat_features['Label'] = 'BENIGN'  # Force normal label
            
            df_new = pd.DataFrame([flat_features])
            
            if os.path.exists(fp_csv_path):
                # Append without header
                df_new.to_csv(fp_csv_path, mode='a', header=False, index=False)
            else:
                # Create with header
                df_new.to_csv(fp_csv_path, mode='w', header=True, index=False)
                
            logger.info(f"Saved FP features to {fp_csv_path} for continuous learning.")
        except Exception as e:
            logger.error(f"Failed to save FP features to CSV: {e}")

    def _remove_fp_features_from_csv(self, raw_features: dict):
        """Remove false positive raw features from the dedicated CSV"""
        import os
        import pandas as pd
        import numpy as np
        
        # Get project root and data dir
        current_file = os.path.abspath(__file__)
        ml_dir = os.path.dirname(current_file)
        backend_dir = os.path.dirname(ml_dir)
        project_root = os.path.dirname(backend_dir)
        data_dir = os.path.join(project_root, "data", "fp_governance")
        
        fp_csv_path = os.path.join(data_dir, "human_feedback_fp.csv")
        
        if not os.path.exists(fp_csv_path):
            return
            
        try:
            # Flatten features to match how they were saved
            flat_features = {}
            for k, v in raw_features.items():
                if isinstance(v, (int, float, bool)):
                    flat_features[k] = float(v)
            
            if not flat_features:
                return
                
            flat_features['Label'] = 'BENIGN'
            
            # Read existing CSV
            df = pd.read_csv(fp_csv_path)
            if df.empty:
                return
                
            # Create a matching series for the row to remove
            target_series = pd.Series(flat_features)
            
            # Find rows that match the target features (allowing for slight float variations)
            # A simple approach is to find exact matches for a subset of key features
            # Or use numpy isclose for all common numeric features
            common_cols = list(set(df.columns).intersection(set(target_series.index)))
            
            if not common_cols:
                return
                
            # Create a boolean mask for rows that match
            mask = pd.Series(True, index=df.index)
            for col in common_cols:
                if col == 'Label':
                    mask &= (df[col] == target_series[col])
                else:
                    # Use isclose for float comparison
                    mask &= np.isclose(df[col].astype(float), float(target_series[col]), rtol=1e-05, atol=1e-08)
            
            # If we found a match, drop the FIRST match only (in case of duplicates)
            match_indices = df[mask].index
            if len(match_indices) > 0:
                df = df.drop(match_indices[0])
                # Save back to CSV
                df.to_csv(fp_csv_path, index=False)
                logger.info(f"Removed 1 FP feature row from {fp_csv_path}")
                
        except Exception as e:
            logger.error(f"Failed to remove FP features from CSV: {e}")
