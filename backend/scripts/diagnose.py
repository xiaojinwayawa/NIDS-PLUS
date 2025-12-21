"""
Diagnostic script to check NIDS system components
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis
import numpy as np
from config import settings

def check_redis():
    """Check Redis connection and queue status"""
    print("\n" + "="*50)
    print("1. CHECKING REDIS CONNECTION")
    print("="*50)
    
    try:
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        
        # Test connection
        pong = r.ping()
        print(f"✓ Redis connection: OK (ping={pong})")
        print(f"  Host: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        
        # Check queue length
        queue_len = r.llen("traffic_queue")
        print(f"✓ Traffic queue length: {queue_len}")
        
        if queue_len == 0:
            print("  ⚠ Queue is empty - no packets waiting for processing")
            print("  → Make sure detection is started and PCAP is being replayed")
        else:
            # Peek at first item
            first_item = r.lindex("traffic_queue", 0)
            print(f"  Sample item: {first_item[:100]}..." if first_item else "  No items")
            
        return True
        
    except Exception as e:
        print(f"✗ Redis connection FAILED: {e}")
        print("  → Check if Redis is running: docker ps | grep redis")
        return False

def check_feature_extraction():
    """Check feature extraction"""
    print("\n" + "="*50)
    print("2. CHECKING FEATURE EXTRACTION")
    print("="*50)
    
    try:
        from ml.feature_extractor import get_extractor
        
        extractor = get_extractor("cic-ids2017")
        print(f"✓ Feature extractor loaded: {type(extractor).__name__}")
        print(f"  Feature count: {len(extractor.get_feature_names())}")
        
        # Test with sample packet
        sample_packet = {
            "src_ip": "192.168.1.100",
            "dst_ip": "10.0.0.1",
            "src_port": 12345,
            "dst_port": 80,
            "protocol": "TCP",
            "timestamp": 1234567890.0,
            "length": 1500
        }
        
        features = extractor.extract_features(sample_packet)
        print(f"✓ Feature extraction: OK")
        print(f"  Output shape: {np.array(features).shape}")
        
        # Test preprocessing
        preprocessed = extractor.preprocess(features)
        print(f"✓ Preprocessing: OK")
        print(f"  Output shape: {np.array(preprocessed).shape}")
        
        return True
        
    except Exception as e:
        print(f"✗ Feature extraction FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_model_inference():
    """Check model inference"""
    print("\n" + "="*50)
    print("3. CHECKING MODEL INFERENCE")
    print("="*50)
    
    try:
        from ml.inference_engine import InferenceEngine
        
        engine = InferenceEngine()
        print(f"✓ Inference engine created")
        print(f"  Models directory: {engine.models_dir}")
        
        # List available models
        import os
        models_dir = engine.models_dir
        if os.path.exists(models_dir):
            joblib_files = [f for f in os.listdir(models_dir) if f.endswith('.joblib')]
            print(f"✓ Available models: {joblib_files}")
        else:
            print(f"✗ Models directory not found: {models_dir}")
            return False
        
        # Try loading LightGBM model
        if "lightgbm_cicids.joblib" in joblib_files:
            success = engine.load_model("lightgbm_cicids", "lightgbm")
            if success:
                print(f"✓ LightGBM model loaded successfully")
            else:
                print(f"✗ Failed to load LightGBM model")
                return False
        
        # Test inference with dummy data
        dummy_features = np.random.rand(1, 78)  # 78 features for CIC-IDS2017
        result = engine.predict_batch(dummy_features)
        
        print(f"✓ Model inference: OK")
        print(f"  Prediction: {result['predictions']}")
        print(f"  Confidence: {result['confidences']}")
        print(f"  Inference time: {result['inference_time_ms']:.2f}ms")
        
        return True
        
    except Exception as e:
        print(f"✗ Model inference FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_database():
    """Check database connection"""
    print("\n" + "="*50)
    print("4. CHECKING DATABASE CONNECTION")
    print("="*50)
    
    try:
        from db.db_manager import SessionLocal
        from db.models import AlertModel
        
        db = SessionLocal()
        
        # Test query
        alert_count = db.query(AlertModel).count()
        print(f"✓ Database connection: OK")
        print(f"  Alert count in database: {alert_count}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"✗ Database connection FAILED: {e}")
        print("  → Check if MySQL is running: docker ps | grep mysql")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*50)
    print("NIDS SYSTEM DIAGNOSTIC")
    print("="*50)
    
    results = {
        "Redis": check_redis(),
        "Feature Extraction": check_feature_extraction(),
        "Model Inference": check_model_inference(),
        "Database": check_database()
    }
    
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    
    all_ok = True
    for component, status in results.items():
        status_str = "✓ OK" if status else "✗ FAILED"
        print(f"  {component}: {status_str}")
        if not status:
            all_ok = False
    
    if all_ok:
        print("\n✓ All components are working correctly!")
        print("  If no alerts appear, the PCAP file may not contain attacks yet.")
        print("  Check backend logs for 'Detected X attacks' messages.")
    else:
        print("\n✗ Some components have issues. Please fix them first.")

if __name__ == "__main__":
    main()
