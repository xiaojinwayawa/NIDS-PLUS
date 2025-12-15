
import pytest
import numpy as np
import os
import joblib
import time
from hypothesis import given, strategies as st
from ml.inference_engine import InferenceEngine
from sklearn.linear_model import LogisticRegression

# Mock Model Fixture
@pytest.fixture
def mock_model_dir(tmp_path):
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    
    # Create a dummy LightGBM-compatible model (using sklearn for simplicity as interface is similar)
    # In real test we would use actual LGBM/XGB models
    model = LogisticRegression()
    X = np.random.rand(10, 5)
    y = np.random.randint(0, 2, 10)
    model.fit(X, y)
    
    # Save as .joblib (supported by our engine for "lightgbm" type path)
    joblib.dump(model, model_dir / "test_model.joblib")
    
    return str(model_dir)

def test_inference_latency(mock_model_dir):
    """
    Property 5: Inference Latency Guarantee
    Req 5.5: Verify inference returns within 100ms
    """
    engine = InferenceEngine(models_dir=mock_model_dir)
    # Mock the loading part to use our sklearn model but treat as lightgbm
    # We need to ensure the engine calls predict/predict_proba correctly
    # Sklearn models have predict_proba, so it fits the interface
    
    success = engine.load_model("test_model", "lightgbm")
    assert success
    
    # Generate batch of features (5 dimensions as trained)
    features = np.random.rand(100, 5) # Batch of 100
    
    start = time.time()
    result = engine.predict_batch(features)
    duration = (time.time() - start) * 1000
    
    assert duration < 100 # ms
    assert "inference_time_ms" in result
    assert result["inference_time_ms"] < 100

def test_model_loading_idempotency(mock_model_dir):
    """
    Property 10: Model Loading Idempotency
    Req 5.1: Verify loading same model multiple times has no side effects
    """
    engine = InferenceEngine(models_dir=mock_model_dir)
    
    # First load
    assert engine.load_model("test_model", "lightgbm")
    assert "test_model_latest" in engine.loaded_models
    
    # Second load
    assert engine.load_model("test_model", "lightgbm")
    assert len(engine.loaded_models) == 1 # Should still be 1

def test_batch_inference_throughput(mock_model_dir):
    """
    Property 11: Batch Inference Throughput
    Req 19.2: Verify throughput (1000 records) is handled efficiently
    """
    engine = InferenceEngine(models_dir=mock_model_dir)
    engine.load_model("test_model", "lightgbm")
    
    # Large batch
    batch_size = 1000
    features = np.random.rand(batch_size, 5)
    
    start = time.time()
    result = engine.predict_batch(features)
    duration = time.time() - start
    
    # Check output size
    assert len(result["predictions"]) == batch_size
    assert len(result["confidences"]) == batch_size
    
    # Throughput check: 1000 items should be processed reasonably fast (e.g., < 0.5s for this simple model)
    assert duration < 0.5 
    print(f"\nThroughput: {batch_size / duration:.2f} samples/sec")
