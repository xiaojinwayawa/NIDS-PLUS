"""
Integration Tests for NIDS System
Tests end-to-end workflows
"""
import pytest
import os
import sys
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from ml.detection_engine import DetectionEngine, SystemState
from ml.inference_engine import InferenceEngine
from ml.alert_engine import AlertEngine


class TestEndToEndDetection:
    """Test complete detection pipeline"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_health_check(self, client):
        """Test health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "NIDS" in data["message"]


class TestDetectionEngine:
    """Test detection engine state management"""
    
    def test_engine_initial_state(self):
        """Test engine starts in IDLE state"""
        engine = DetectionEngine()
        assert engine.state == SystemState.IDLE
        
    def test_engine_get_status(self):
        """Test engine status retrieval"""
        engine = DetectionEngine()
        status = engine.get_status()
        assert "state" in status
        assert status["state"] == "idle"
        
    def test_engine_configure(self):
        """Test engine configuration"""
        engine = DetectionEngine()
        engine.configure({"model_name": "test_model", "dataset_type": "cic-ids2017"})
        assert engine.current_model_name == "test_model"
        assert engine.dataset_type == "cic-ids2017"


class TestInferenceEngine:
    """Test model inference"""
    
    def test_inference_engine_init(self):
        """Test inference engine initialization"""
        engine = InferenceEngine()
        assert engine is not None
        assert engine.loaded_models == {}
        
    def test_model_loading(self):
        """Test model loading from files"""
        models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models")
        engine = InferenceEngine(models_dir=models_dir)
        
        lgb_path = os.path.join(models_dir, "lightgbm_cicids.joblib")
        if os.path.exists(lgb_path):
            success = engine.load_model("lightgbm_cicids", "lightgbm")
            assert success
            assert "lightgbm_cicids_latest" in engine.loaded_models
        else:
            pytest.skip("Model file not found")
            
    def test_model_loading_idempotent(self):
        """Test that loading same model twice is idempotent"""
        models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models")
        engine = InferenceEngine(models_dir=models_dir)
        
        lgb_path = os.path.join(models_dir, "lightgbm_cicids.joblib")
        if os.path.exists(lgb_path):
            engine.load_model("lightgbm_cicids", "lightgbm")
            engine.load_model("lightgbm_cicids", "lightgbm")  # Load again
            # Should still only have one entry
            assert len([k for k in engine.loaded_models if "lightgbm_cicids" in k]) == 1
        else:
            pytest.skip("Model file not found")
            
    def test_predict_batch_no_models(self):
        """Test prediction with no models loaded"""
        import numpy as np
        engine = InferenceEngine()
        features = np.random.rand(5, 78)
        result = engine.predict_batch(features)
        assert "predictions" in result
        assert "error" in result


class TestAlertEngine:
    """Test alert generation"""
    
    def test_alert_engine_init(self):
        """Test alert engine initialization"""
        engine = AlertEngine()
        assert engine is not None
        
    def test_alert_generation_structure(self):
        """Test alert generation with mock data"""
        engine = AlertEngine()
        
        packet_info = {
            "timestamp": 1703174400,
            "src_ip": "192.168.1.100",
            "dst_ip": "10.0.0.1",
            "src_port": 12345,
            "dst_port": 80,
            "protocol": "TCP"
        }
        
        prediction_result = {
            "is_attack": True,
            "confidence": 0.95,
            "attack_type": "DDoS",
            "predictions": [1]
        }
        
        # Mock the database save
        with patch.object(engine, '_save_alert'):
            alert = engine.generate_alert(packet_info, prediction_result, model_id=1)
            assert alert is not None
            assert alert.attack_type == "DDoS"
            assert alert.src_ip == "192.168.1.100"
            
    def test_no_alert_for_benign(self):
        """Test no alert generated for benign traffic"""
        engine = AlertEngine()
        
        packet_info = {"timestamp": 1703174400, "src_ip": "192.168.1.1"}
        prediction_result = {"is_attack": False, "predictions": [0]}
        
        alert = engine.generate_alert(packet_info, prediction_result)
        assert alert is None


class TestAPIEndpoints:
    """Test API endpoint availability"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_auth_login_endpoint_exists(self, client):
        """Test auth login endpoint exists"""
        response = client.post("/api/auth/login", json={
            "username": "test",
            "password": "test"
        })
        # Should return 401 (unauthorized) or 200, not 404
        assert response.status_code != 404
        
    def test_system_status_endpoint_exists(self, client):
        """Test system status endpoint exists"""
        response = client.get("/api/system/status")
        # Should return 401 (unauthorized), not 404
        assert response.status_code != 404
        
    def test_system_start_endpoint_exists(self, client):
        """Test system start endpoint exists"""
        response = client.post("/api/system/start", json={"mode": "pcap"})
        assert response.status_code != 404
        
    def test_alerts_endpoint_exists(self, client):
        """Test alerts endpoint exists"""
        response = client.get("/api/alerts/")
        assert response.status_code != 404
        
    def test_stats_endpoint_exists(self, client):
        """Test stats endpoint exists"""
        response = client.get("/api/stats/dashboard")
        assert response.status_code != 404


class TestModelInference:
    """Test model inference with real models"""
    
    def test_lightgbm_inference(self):
        """Test LightGBM model inference"""
        import numpy as np
        
        models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models")
        engine = InferenceEngine(models_dir=models_dir)
        
        lgb_path = os.path.join(models_dir, "lightgbm_cicids.joblib")
        if not os.path.exists(lgb_path):
            pytest.skip("LightGBM model not found")
            
        engine.load_model("lightgbm_cicids", "lightgbm")
        
        # Create dummy features (78 features for CIC-IDS2017)
        features = np.random.rand(10, 78)
        result = engine.predict_batch(features)
        
        assert "predictions" in result
        assert "confidences" in result
        assert len(result["predictions"]) == 10
        assert result["inference_time_ms"] >= 0
        
    def test_xgboost_inference(self):
        """Test XGBoost model inference"""
        import numpy as np
        
        models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models")
        engine = InferenceEngine(models_dir=models_dir)
        
        xgb_path = os.path.join(models_dir, "xgboost_cicids.joblib")
        if not os.path.exists(xgb_path):
            pytest.skip("XGBoost model not found")
            
        engine.load_model("xgboost_cicids", "xgboost")
        
        features = np.random.rand(10, 78)
        result = engine.predict_batch(features)
        
        assert "predictions" in result
        assert len(result["predictions"]) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
