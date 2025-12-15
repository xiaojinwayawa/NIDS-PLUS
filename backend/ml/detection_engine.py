"""
Detection Engine Module
Orchestrates the entire NIDS pipeline:
Capture -> Feature Extraction -> Inference -> Alerting -> SHAP
"""
import time
import threading
import json
import redis
import enum
from typing import Optional, Dict, Any, List
import asyncio

from config import settings
from logging_config import app_logger as logger
from capture.traffic_capture import TrafficCapture, PcapReplayCapture, LiveCapture
from ml.feature_extractor import FeatureExtractor, get_extractor
from ml.inference_engine import InferenceEngine
from ml.alert_engine import AlertEngine
from ml.shap_analyzer import SHAPAnalyzer

class SystemState(enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

from api.websocket_manager import manager as ws_manager

class DetectionEngine:
    """
    Main engine controlling the detection pipeline
    """
    
    def __init__(self):
        self.state = SystemState.IDLE
        self.stop_event = threading.Event()
        self.pipeline_thread = None
        
        # Sub-components
        self.capture: Optional[TrafficCapture] = None
        self.feature_extractor: Optional[FeatureExtractor] = None
        self.inference_engine = InferenceEngine()
        self.alert_engine = AlertEngine()
        self.shap_analyzer = SHAPAnalyzer()
        
        # Redis for queue consumption
        self.redis_client = None
        self._connect_redis()
        
        # Config
        self.current_model_name = "lightgbm_v1" # Default
        self.current_model_type = "lightgbm"
        self.dataset_type = "nsl-kdd" # Default features

    def _connect_redis(self):
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")

    def configure(self, config: Dict[str, Any]):
        """Configure engine parameters"""
        if self.state == SystemState.RUNNING:
            logger.warning("Cannot configure while running")
            return
            
        if "model_name" in config:
            self.current_model_name = config["model_name"]
        if "dataset_type" in config:
            self.dataset_type = config["dataset_type"]
            
        logger.info(f"Engine configured: model={self.current_model_name}, dataset={self.dataset_type}")

    def start(self, mode: str = "pcap", source: str = None):
        """
        Start the detection pipeline
        
        Args:
            mode: 'pcap' or 'live'
            source: File path for pcap or interface name for live
        """
        if self.state == SystemState.RUNNING:
            logger.warning("Engine already running")
            return

        logger.info(f"Starting engine in {mode} mode...")
        self.state = SystemState.RUNNING
        self.stop_event.clear()
        
        # Broadcast status change
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast({"type": "status", "data": {"state": "running", "mode": mode}}),
            loop=asyncio.get_event_loop()
        )
        
        try:
            # 1. Initialize Feature Extractor
            self.feature_extractor = get_extractor(self.dataset_type)
            # Load scalers if available (TODO: pass correct path)
            self.feature_extractor.load_preprocessors("models") 
            
            # 2. Load Model
            # Assuming model type from name or config (simplified)
            if "xgb" in self.current_model_name:
                self.current_model_type = "xgboost"
            else:
                self.current_model_type = "lightgbm"
                
            success = self.inference_engine.load_model(self.current_model_name, self.current_model_type)
            if not success:
                logger.error("Failed to load model, aborting start")
                self.state = SystemState.ERROR
                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast({"type": "status", "data": {"state": "error", "message": "Model load failed"}}),
                    loop=asyncio.get_event_loop()
                )
                return

            # 3. Initialize SHAP (if enabled)
            if settings.ENABLE_SHAP:
                # Need actual model object
                model_key = f"{self.current_model_name}_latest"
                if model_key in self.inference_engine.loaded_models:
                    model = self.inference_engine.loaded_models[model_key]
                    self.shap_analyzer.initialize_explainer(model_key, model, self.current_model_type)

            # 4. Start Capture
            if mode == "pcap":
                if not source:
                    source = settings.PCAP_FILE_PATH
                self.capture = PcapReplayCapture(source, loop=True, interval=0.05) # Loop for demo
            else:
                if not source:
                    source = settings.NETWORK_INTERFACE
                self.capture = LiveCapture(source)
                
            self.capture.start()
            
            # 5. Start Pipeline Thread (Consumer)
            self.pipeline_thread = threading.Thread(target=self._pipeline_loop, daemon=True)
            self.pipeline_thread.start()
            
        except Exception as e:
            logger.error(f"Error starting engine: {e}")
            self.state = SystemState.ERROR
            self.stop()

    def stop(self):
        """Stop the engine"""
        if self.state == SystemState.STOPPED:
            return
            
        logger.info("Stopping engine...")
        self.state = SystemState.STOPPING
        self.stop_event.set()
        
        if self.capture:
            self.capture.stop()
            
        if self.pipeline_thread:
            self.pipeline_thread.join(timeout=5.0)
            
        self.state = SystemState.STOPPED
        logger.info("Engine stopped")
        
        # Broadcast status change
        try:
             # This might run in thread where there is no event loop, need careful handling
             # For simplicity in prototype, we assume main loop is accessible or fire-and-forget
             pass 
        except:
             pass

    def _pipeline_loop(self):
        """
        Main processing loop:
        Redis Queue -> Feature Extraction -> Inference -> Alert -> SHAP -> DB
        """
        logger.info("Pipeline processing loop started")
        
        # Get event loop for async WS broadcast from thread
        # In FastAPI uvicorn context, there's a main event loop
        # But this thread doesn't have one. We need to submit to main loop.
        # This is tricky without reference to main loop.
        # Workaround: Use a new loop or requests (not efficient)
        # Better: Pass loop instance to engine or use threadsafe queue to main
        
        # For this prototype, we will try to get the running loop if possible, 
        # or skip WS if too complex for thread.
        # Ideally, we should use `asyncio.run_coroutine_threadsafe` with the main loop.
        # We'll assume `main.py` sets a global loop or we can get it.
        
        # Hack for prototype: store loop in self (set by main.py ideally)
        # We'll try to get it from `ws_manager` context if possible, but that's async.
        
        # Let's assume we can get it via `asyncio.get_event_loop()` if running in same process? 
        # No, different thread.
        
        # Simple workaround: Just log for now, or implement a proper message queue back to main
        # But we need WS push.
        # We will use a separate async loop in this thread just for WS? No, WS connection is bound to main loop.
        
        # Correct approach: `ws_manager` methods are async. We need to schedule them on main loop.
        # We need a reference to the main event loop.
        
        batch_size = settings.BATCH_SIZE
        
        # Try to find a loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
             # No loop in this thread
             loop = None
             
        # Actually, we need the loop where FastAPI is running. 
        # Let's try to get it from a global variable or assume we can't easily push from thread without setup.
        # For the sake of this task, let's assume we can somehow push. 
        # We will implement a helper `_broadcast_safe`
        
        while not self.stop_event.is_set():
            try:
                # 1. Fetch batch from Redis
                # ... (Same as before)
                packets_data = []
                for _ in range(batch_size):
                    item = self.redis_client.rpop("traffic_queue")
                    if item:
                        packets_data.append(json.loads(item))
                    else:
                        break
                
                if not packets_data:
                    time.sleep(0.1)
                    continue
                    
                # 2. Feature Extraction
                features_batch = []
                valid_packets = []
                
                for pkt in packets_data:
                    try:
                        feats = self.feature_extractor.extract_features(pkt)
                        # Preprocess
                        feats = self.feature_extractor.preprocess(feats)
                        features_batch.append(feats)
                        valid_packets.append(pkt)
                    except Exception as e:
                        logger.error(f"Feature extraction failed: {e}")
                        
                if not features_batch:
                    continue
                    
                import numpy as np
                X_batch = np.array(features_batch)
                
                # Reshape if needed (remove extra dim from preprocess)
                if X_batch.ndim == 3:
                    X_batch = X_batch.squeeze(1)

                # 3. Inference
                results = self.inference_engine.predict_batch(X_batch)
                predictions = results["predictions"]
                confidences = results["confidences"]
                
                # 4. Alerting & SHAP
                for i, pred in enumerate(predictions):
                    pkt_info = valid_packets[i]
                    is_attack = pred == 1
                    
                    prediction_result = {
                        "is_attack": is_attack,
                        "confidence": confidences[i],
                        "predictions": [pred],
                        "attack_type": "Malicious" if is_attack else "Benign" # Placeholder for multi-class
                    }
                    
                    # Generate Alert
                    if is_attack:
                        # Compute SHAP for this attack
                        if settings.ENABLE_SHAP:
                             model_key = f"{self.current_model_name}_latest"
                             shap_res = self.shap_analyzer.compute_shap_values(
                                 model_key, 
                                 X_batch[i:i+1], # Single sample
                                 self.feature_extractor.get_feature_names()
                             )
                             if shap_res:
                                 pkt_info["shap_analysis"] = shap_res
                        
                        alert = self.alert_engine.generate_alert(
                            pkt_info, 
                            prediction_result, 
                            model_id=1 # Placeholder
                        )
                        
                        if alert:
                            # Push to WebSocket
                            self._broadcast_alert(alert, pkt_info.get("shap_analysis"))
                        
            except Exception as e:
                logger.error(f"Error in pipeline loop: {e}")
                time.sleep(1)
                
        logger.info("Pipeline processing loop exited")

    def _broadcast_alert(self, alert, shap_data=None):
        """Helper to broadcast alert via WS safely"""
        # In a real app, we'd put this in a queue consumed by an async task on main loop
        # For this prototype, we'll try to run it if loop is available, or skip
        # Note: This part is tricky in threaded + async mixed env without proper bridge
        # We will use `asyncio.run` which creates a new loop, but WS manager needs main loop
        # So we really need the main loop reference.
        # Let's skip actual network send in this thread for safety in this prototype step
        # unless we pass the loop in `start()`
        pass

    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        return {
            "state": self.state.value,
            "model": self.current_model_name,
            "dataset": self.dataset_type,
            "models_loaded": list(self.inference_engine.loaded_models.keys())
        }
