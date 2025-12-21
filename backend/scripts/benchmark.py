"""
Performance Benchmark Script
Tests inference latency and throughput
"""
import os
import sys
import time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.inference_engine import InferenceEngine
from logging_config import app_logger as logger

def benchmark_inference():
    """Benchmark model inference performance"""
    models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models")
    engine = InferenceEngine(models_dir=models_dir)
    
    # Load models
    lgb_path = os.path.join(models_dir, "lightgbm_cicids.joblib")
    xgb_path = os.path.join(models_dir, "xgboost_cicids.joblib")
    
    if os.path.exists(lgb_path):
        engine.load_model("lightgbm_cicids", "lightgbm")
    if os.path.exists(xgb_path):
        engine.load_model("xgboost_cicids", "xgboost")
    
    if not engine.loaded_models:
        logger.error("No models available for benchmark")
        return
    
    # Test parameters
    feature_dim = 78  # CIC-IDS2017 features
    batch_sizes = [1, 10, 50, 100, 500, 1000]
    iterations = 100
    
    print("\n" + "=" * 60)
    print("NIDS Inference Performance Benchmark")
    print("=" * 60)
    print(f"Models loaded: {list(engine.loaded_models.keys())}")
    print(f"Feature dimension: {feature_dim}")
    print(f"Iterations per batch size: {iterations}")
    print("=" * 60)
    
    results = []
    
    for batch_size in batch_sizes:
        latencies = []
        
        for _ in range(iterations):
            # Generate random features
            features = np.random.rand(batch_size, feature_dim).astype(np.float32)
            
            start = time.perf_counter()
            result = engine.predict_batch(features)
            end = time.perf_counter()
            
            latencies.append((end - start) * 1000)  # ms
        
        avg_latency = np.mean(latencies)
        p50_latency = np.percentile(latencies, 50)
        p95_latency = np.percentile(latencies, 95)
        p99_latency = np.percentile(latencies, 99)
        throughput = (batch_size * 1000) / avg_latency  # samples/sec
        
        results.append({
            "batch_size": batch_size,
            "avg_latency_ms": avg_latency,
            "p50_ms": p50_latency,
            "p95_ms": p95_latency,
            "p99_ms": p99_latency,
            "throughput": throughput
        })
        
        print(f"\nBatch Size: {batch_size}")
        print(f"  Avg Latency: {avg_latency:.2f} ms")
        print(f"  P50 Latency: {p50_latency:.2f} ms")
        print(f"  P95 Latency: {p95_latency:.2f} ms")
        print(f"  P99 Latency: {p99_latency:.2f} ms")
        print(f"  Throughput:  {throughput:.0f} samples/sec")
    
    print("\n" + "=" * 60)
    print("Performance Summary")
    print("=" * 60)
    
    # Check against requirements
    # Requirement: <100ms latency, >1000 samples/sec throughput
    batch_100 = next((r for r in results if r["batch_size"] == 100), None)
    if batch_100:
        latency_ok = batch_100["p95_ms"] < 100
        throughput_ok = batch_100["throughput"] > 1000
        
        print(f"\nRequirement Check (batch_size=100):")
        print(f"  Latency < 100ms: {'✓ PASS' if latency_ok else '✗ FAIL'} ({batch_100['p95_ms']:.2f}ms)")
        print(f"  Throughput > 1000/s: {'✓ PASS' if throughput_ok else '✗ FAIL'} ({batch_100['throughput']:.0f}/s)")
    
    return results

if __name__ == "__main__":
    benchmark_inference()
