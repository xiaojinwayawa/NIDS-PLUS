
import pytest
import time
from ml.detection_engine import DetectionEngine, SystemState
from unittest.mock import MagicMock, patch

def test_system_state_transitions():
    """
    Property 1: System State Transition Consistency
    Req 1.3: Verify transitions IDLE -> RUNNING -> STOPPING -> STOPPED
    """
    engine = DetectionEngine()
    
    assert engine.state == SystemState.IDLE
    
    # Mock components to avoid actual IO/Thread starting in unit test
    engine.capture = MagicMock()
    engine.inference_engine.load_model = MagicMock(return_value=True)
    engine.feature_extractor = MagicMock()
    
    # We mock start to avoid real thread creation but we want to test state change
    # However, state change logic is inside start/stop.
    # Let's mock inner calls but run start() logic.
    
    with patch('ml.detection_engine.get_extractor'), \
         patch('ml.detection_engine.PcapReplayCapture'), \
         patch('threading.Thread'):
         
        engine.start(mode="pcap", source="test.pcap")
        assert engine.state == SystemState.RUNNING
        
        # Test idempotency of start
        engine.start()
        assert engine.state == SystemState.RUNNING
        
        engine.stop()
        # In real code stop waits for thread, here mock returns immediately
        assert engine.state == SystemState.STOPPED
        
        # Test idempotency of stop
        engine.stop()
        assert engine.state == SystemState.STOPPED

def test_configuration_while_running():
    """
    Property 1: System State Transition Consistency
    Req 1.4: Verify configuration is blocked while running
    """
    engine = DetectionEngine()
    engine.state = SystemState.RUNNING
    
    engine.configure({"model_name": "new_model"})
    assert engine.current_model_name != "new_model" # Should not change
    
    engine.state = SystemState.IDLE
    engine.configure({"model_name": "new_model"})
    assert engine.current_model_name == "new_model" # Should change

def test_pipeline_integration_mock():
    """
    Verify pipeline integration logic (mocked)
    """
    engine = DetectionEngine()
    engine.redis_client = MagicMock()
    engine.feature_extractor = MagicMock()
    engine.inference_engine = MagicMock()
    engine.alert_engine = MagicMock()
    
    # Simulate one packet in queue
    engine.redis_client.rpop.side_effect = ['{"src_ip": "1.1.1.1"}', None]
    
    # Simulate feature extraction
    import numpy as np
    engine.feature_extractor.extract_features.return_value = np.zeros(41)
    engine.feature_extractor.preprocess.return_value = np.zeros(41)
    
    # Simulate inference (Attack)
    engine.inference_engine.predict_batch.return_value = {
        "predictions": [1],
        "confidences": [0.9]
    }
    
    # Run pipeline loop logic manually (extract body of loop)
    # ... Or we can run it in a thread for a short time
    
    engine.stop_event.clear()
    
    # Run loop in a separate thread but stop it quickly
    import threading
    t = threading.Thread(target=engine._pipeline_loop)
    t.start()
    
    time.sleep(0.5)
    engine.stop_event.set()
    t.join()
    
    # Verify calls
    assert engine.redis_client.rpop.called
    assert engine.feature_extractor.extract_features.called
    assert engine.inference_engine.predict_batch.called
    assert engine.alert_engine.generate_alert.called
