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
from queue import Queue

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

# Global message queue for thread-safe WebSocket broadcasting
_ws_message_queue: Queue = Queue()

class DetectionEngine:
    """
    Main engine controlling the detection pipeline
    """
    
    def __init__(self):
        self.state = SystemState.IDLE
        self.stop_event = threading.Event()
        self.pipeline_thread = None
        self.ws_broadcast_thread = None
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        
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
        self.current_model_name = "lightgbm_cicids" # Default
        self.current_model_type = "lightgbm"
        self.dataset_type = "cic-ids2017" # Default features
        
        # Stats tracking
        self._packets_processed = 0
        self._last_stats_time = time.time()
        self._processing_times: List[float] = []
        
        # Traffic statistics for analysis
        self._traffic_stats = {
            "protocols": {},      # protocol -> count
            "src_ips": {},        # src_ip -> count
            "dst_ips": {},        # dst_ip -> count
            "src_ports": {},      # src_port -> count
            "dst_ports": {},      # dst_port -> count
            "port_activity": {},  # (timestamp_slot, port) -> count
        }
        self._stats_lock = threading.Lock()

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

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the main event loop for async operations from threads"""
        self._main_loop = loop

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
        
        # Reset stats
        self._packets_processed = 0
        self._last_stats_time = time.time()
        self._processing_times = []
        
        # Reset traffic statistics
        with self._stats_lock:
            self._traffic_stats = {
                "protocols": {},
                "src_ips": {},
                "dst_ips": {},
                "src_ports": {},
                "dst_ports": {},
                "port_activity": {},
            }
        
        # Broadcast status change
        self._queue_broadcast({"type": "status", "data": {"state": "running", "mode": mode}})
        
        try:
            # Get project root directory for models
            import os
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.dirname(backend_dir)
            models_dir = os.path.join(project_root, "models")
            
            # 1. Initialize Feature Extractor
            self.feature_extractor = get_extractor(self.dataset_type)
            # Load scalers from project root models directory
            self.feature_extractor.load_preprocessors(models_dir) 
            
            # 2. Unload all existing models first, then load the selected model
            # This ensures only the selected model is used for inference
            for model_key in list(self.inference_engine.loaded_models.keys()):
                model_name = self.inference_engine.model_metadata[model_key]["name"]
                version = self.inference_engine.model_metadata[model_key]["version"]
                self.inference_engine.unload_model(model_name, version)
            
            # Determine model type from name
            if "xgb" in self.current_model_name.lower():
                self.current_model_type = "xgboost"
            else:
                self.current_model_type = "lightgbm"
                
            success = self.inference_engine.load_model(self.current_model_name, self.current_model_type)
            if not success:
                logger.error("Failed to load model, aborting start")
                self.state = SystemState.ERROR
                self._queue_broadcast({"type": "status", "data": {"state": "error", "message": "Model load failed"}})
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
                # Use faster replay interval for large files (0.001s = 1000 pkts/s max)
                self.capture = PcapReplayCapture(source, loop=True, interval=0.001)
            else:
                if not source:
                    source = settings.NETWORK_INTERFACE
                self.capture = LiveCapture(source)
                
            self.capture.start()
            
            # 5. Start Pipeline Thread (Consumer)
            self.pipeline_thread = threading.Thread(target=self._pipeline_loop, daemon=True)
            self.pipeline_thread.start()
            
            # 6. Start WebSocket broadcast thread
            self.ws_broadcast_thread = threading.Thread(target=self._ws_broadcast_loop, daemon=True)
            self.ws_broadcast_thread.start()
            
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
        
        if self.ws_broadcast_thread:
            self.ws_broadcast_thread.join(timeout=2.0)
            
        self.state = SystemState.STOPPED
        logger.info("Engine stopped")
        
        # Broadcast status change
        self._queue_broadcast({"type": "status", "data": {"state": "stopped"}})

    def _pipeline_loop(self):
        """
        Main processing loop:
        Redis Queue -> Feature Extraction -> Inference -> Alert -> SHAP -> DB
        """
        logger.info("Pipeline processing loop started")
        
        batch_size = settings.BATCH_SIZE
        stats_interval = 1.0  # Send stats every 1 second
        
        while not self.stop_event.is_set():
            try:
                loop_start = time.time()
                
                # 1. Fetch batch from Redis
                packets_data = []
                for _ in range(batch_size):
                    item = self.redis_client.rpop("traffic_queue")
                    if item:
                        packets_data.append(json.loads(item))
                    else:
                        break
                
                if not packets_data:
                    # Still send stats periodically even with no data
                    self._maybe_send_stats()
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
                        
                        # Collect traffic statistics
                        self._collect_packet_stats(pkt)
                    except Exception as e:
                        logger.error(f"Feature extraction failed: {e}")
                        
                if not features_batch:
                    self._maybe_send_stats()
                    continue
                    
                import numpy as np
                X_batch = np.array(features_batch)
                
                # Reshape if needed (remove extra dim from preprocess)
                if X_batch.ndim == 3:
                    X_batch = X_batch.squeeze(1)

                # 3. Inference
                inference_start = time.time()
                results = self.inference_engine.predict_batch(X_batch)
                predictions = results["predictions"]
                confidences = results["confidences"]
                inference_time = (time.time() - inference_start) * 1000  # ms
                
                # Log prediction summary for debugging
                attack_count = sum(1 for p in predictions if p == 1)
                if attack_count > 0:
                    logger.info(f"Detected {attack_count} attacks in batch of {len(predictions)}")
                
                # Track stats
                self._packets_processed += len(valid_packets)
                self._processing_times.append(inference_time / len(valid_packets))
                
                # 4. Alerting & SHAP
                for i, pred in enumerate(predictions):
                    pkt_info = valid_packets[i]
                    is_attack = pred == 1
                    
                    prediction_result = {
                        "is_attack": is_attack,
                        "confidence": confidences[i],
                        "predictions": [pred],
                        "attack_type": "Malicious" if is_attack else "Benign"
                    }
                    
                    # Generate Alert
                    if is_attack:
                        # Compute SHAP for this attack
                        shap_analysis = None
                        if settings.ENABLE_SHAP:
                             model_key = f"{self.current_model_name}_latest"
                             shap_res = self.shap_analyzer.compute_shap_values(
                                 model_key, 
                                 X_batch[i:i+1],
                                 self.feature_extractor.get_feature_names()
                             )
                             if shap_res:
                                 shap_analysis = shap_res
                        
                        alert = self.alert_engine.generate_alert(
                            pkt_info, 
                            prediction_result, 
                            model_id=1
                        )
                        
                        if alert:
                            self._broadcast_alert(alert, shap_analysis)
                
                # Send stats periodically
                self._maybe_send_stats()
                        
            except Exception as e:
                logger.error(f"Error in pipeline loop: {e}")
                time.sleep(1)
                
        logger.info("Pipeline processing loop exited")

    def _broadcast_alert(self, alert, shap_data=None):
        """Helper to broadcast alert via WS safely using message queue"""
        # alert is an AlertModel object, access attributes directly
        from datetime import datetime
        
        # Get severity based on confidence
        confidence = getattr(alert, 'confidence', 0.5)
        if confidence >= 0.9:
            severity = "critical"
        elif confidence >= 0.8:
            severity = "high"
        elif confidence >= 0.6:
            severity = "medium"
        else:
            severity = "low"
        
        # Format timestamp
        timestamp = getattr(alert, 'timestamp', datetime.now())
        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat()
        
        alert_msg = {
            "type": "alert",
            "data": {
                "id": getattr(alert, 'id', None),
                "timestamp": timestamp,
                "src_ip": getattr(alert, 'src_ip', ''),
                "dst_ip": getattr(alert, 'dst_ip', ''),
                "protocol": getattr(alert, 'protocol', 'TCP'),
                "attack_type": getattr(alert, 'attack_type', 'Unknown'),
                "confidence": confidence,
                "severity": severity,
                "shap_analysis": shap_data
            }
        }
        self._queue_broadcast(alert_msg)
    
    def _maybe_send_stats(self):
        """Send stats if interval has passed"""
        now = time.time()
        elapsed = now - self._last_stats_time
        
        if elapsed >= 1.0:  # Send stats every second
            # Calculate throughput (packets per second)
            throughput = self._packets_processed / elapsed if elapsed > 0 else 0
            
            # Calculate average latency
            avg_latency = 0.0
            if self._processing_times:
                avg_latency = sum(self._processing_times) / len(self._processing_times)
            
            stats_msg = {
                "type": "stats",
                "data": {
                    "timestamp": int(now * 1000),
                    "throughput": round(throughput, 2),
                    "latency": round(avg_latency, 2),
                    "packets_processed": self._packets_processed
                }
            }
            self._queue_broadcast(stats_msg)
            
            # Reset counters
            self._packets_processed = 0
            self._last_stats_time = now
            self._processing_times = []
    
    def _queue_broadcast(self, message: Dict[str, Any]):
        """Queue a message for WebSocket broadcast (thread-safe)"""
        _ws_message_queue.put(message)
    
    def _ws_broadcast_loop(self):
        """Background thread that processes the WS message queue"""
        logger.info("WebSocket broadcast loop started")
        
        while not self.stop_event.is_set():
            try:
                # Get message with timeout to allow checking stop_event
                try:
                    message = _ws_message_queue.get(timeout=0.1)
                except:
                    continue
                
                # Broadcast using the main event loop
                if self._main_loop and not self._main_loop.is_closed():
                    asyncio.run_coroutine_threadsafe(
                        ws_manager.broadcast(message),
                        self._main_loop
                    )
                else:
                    # Fallback: try to create a new loop (less ideal)
                    try:
                        asyncio.run(ws_manager.broadcast(message))
                    except Exception as e:
                        logger.debug(f"Could not broadcast: {e}")
                        
            except Exception as e:
                logger.error(f"Error in WS broadcast loop: {e}")
                
        logger.info("WebSocket broadcast loop exited")

    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        return {
            "state": self.state.value,
            "model": self.current_model_name,
            "dataset": self.dataset_type,
            "models_loaded": list(self.inference_engine.loaded_models.keys())
        }
    
    def _collect_packet_stats(self, pkt: Dict[str, Any]):
        """Collect statistics from a packet for traffic analysis"""
        from datetime import datetime
        
        with self._stats_lock:
            # Protocol
            protocol = pkt.get("protocol", "UNKNOWN")
            if protocol:
                self._traffic_stats["protocols"][protocol] = \
                    self._traffic_stats["protocols"].get(protocol, 0) + 1
            
            # Source IP
            src_ip = pkt.get("src_ip", "")
            if src_ip:
                self._traffic_stats["src_ips"][src_ip] = \
                    self._traffic_stats["src_ips"].get(src_ip, 0) + 1
            
            # Destination IP
            dst_ip = pkt.get("dst_ip", "")
            if dst_ip:
                self._traffic_stats["dst_ips"][dst_ip] = \
                    self._traffic_stats["dst_ips"].get(dst_ip, 0) + 1
            
            # Source Port
            src_port = pkt.get("src_port")
            if src_port:
                port_key = str(src_port)
                self._traffic_stats["src_ports"][port_key] = \
                    self._traffic_stats["src_ports"].get(port_key, 0) + 1
            
            # Destination Port
            dst_port = pkt.get("dst_port")
            if dst_port:
                port_key = str(dst_port)
                self._traffic_stats["dst_ports"][port_key] = \
                    self._traffic_stats["dst_ports"].get(port_key, 0) + 1
                
                # Port activity by time slot (for heatmap)
                time_slot = datetime.now().strftime("%H:%M")
                activity_key = f"{time_slot}:{port_key}"
                self._traffic_stats["port_activity"][activity_key] = \
                    self._traffic_stats["port_activity"].get(activity_key, 0) + 1
    
    def _get_ip_location(self, ip: str) -> str:
        """Get location description for an IP address"""
        import ipaddress
        
        try:
            ip_obj = ipaddress.ip_address(ip)
            
            # Check if private IP
            if ip_obj.is_private:
                return "Local Network"
            
            # Check if loopback
            if ip_obj.is_loopback:
                return "Localhost"
            
            # Check if multicast
            if ip_obj.is_multicast:
                return "Multicast"
            
            # Check if reserved
            if ip_obj.is_reserved:
                return "Reserved"
            
            # Check common public IP ranges (simplified)
            first_octet = int(str(ip).split('.')[0]) if '.' in ip else 0
            
            # Some well-known ranges (simplified)
            if first_octet == 8:
                return "US (Level 3)"
            elif first_octet == 17:
                return "US (Apple)"
            elif first_octet == 20:
                return "US (Microsoft)"
            elif first_octet == 23:
                return "US (AT&T)"
            elif first_octet == 34 or first_octet == 35:
                return "US (Google Cloud)"
            elif first_octet == 52 or first_octet == 54:
                return "US (Amazon AWS)"
            elif first_octet == 104:
                return "US (Cloudflare)"
            elif first_octet == 142:
                return "US (Google)"
            elif first_octet == 172:
                # Check if it's private 172.16-31.x.x
                second_octet = int(str(ip).split('.')[1])
                if 16 <= second_octet <= 31:
                    return "Local Network"
                return "Public"
            else:
                return "Public"
                
        except Exception:
            return "Unknown"
    
    def get_traffic_stats(self) -> Dict[str, Any]:
        """Get collected traffic statistics for analysis page"""
        with self._stats_lock:
            # Protocol distribution
            protocols = [
                {"name": k, "value": v} 
                for k, v in sorted(
                    self._traffic_stats["protocols"].items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )
            ]
            
            # Top source IPs with location
            top_src_ips = [
                {"ip": k, "count": v, "country": self._get_ip_location(k)}
                for k, v in sorted(
                    self._traffic_stats["src_ips"].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:20]  # Top 20
            ]
            
            # Top destination ports for heatmap
            top_ports = sorted(
                self._traffic_stats["dst_ports"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]  # Top 10 ports
            port_list = [p[0] for p in top_ports]
            
            # Build heatmap data
            # Get unique time slots from port_activity
            time_slots = set()
            for key in self._traffic_stats["port_activity"].keys():
                time_slot = key.split(":")[0] + ":" + key.split(":")[1]
                time_slots.add(time_slot)
            time_slots = sorted(list(time_slots))[-10:]  # Last 10 time slots
            
            heatmap_data = []
            for t_idx, time_slot in enumerate(time_slots):
                for p_idx, port in enumerate(port_list):
                    activity_key = f"{time_slot}:{port}"
                    count = self._traffic_stats["port_activity"].get(activity_key, 0)
                    heatmap_data.append([t_idx, p_idx, count])
            
            return {
                "protocols": protocols if protocols else [{"name": "No Data", "value": 0}],
                "top_ips": top_src_ips if top_src_ips else [],
                "heatmap": heatmap_data,
                "ports": port_list if port_list else ["80", "443", "22"],
                "time_slots": time_slots if time_slots else [],
                "total_packets": sum(self._traffic_stats["protocols"].values())
            }
