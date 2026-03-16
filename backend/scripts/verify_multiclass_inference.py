
import os
import sys
import json
import numpy as np
import joblib
import lightgbm as lgb
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from unittest.mock import MagicMock

# Mock tensorflow to speed up test and avoid import issues if we only test LightGBM
sys.modules["tensorflow"] = MagicMock()
# Ensure InferenceEngine sees it as not available or just doesn't crash
# Actually, InferenceEngine tries to import it. If we mock it, it will succeed but be a mock.
# That's fine as long as we don't try to use it.

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from ml.inference_engine import InferenceEngine

def test_multiclass_inference():
    print("Starting multi-class inference verification...")
    
    # 1. Create a dummy multi-class dataset
    X, y = make_classification(n_samples=100, n_features=20, n_informative=10, 
                               n_classes=3, n_clusters_per_class=1, random_state=42)
    
    # Class 0: Normal
    # Class 1: DoS
    # Class 2: PortScan
    label_mapping = {
        0: "Normal",
        1: "DoS",
        2: "PortScan"
    }
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 2. Train a LightGBM model
    print("Training dummy LightGBM model...")
    params = {
        'objective': 'multiclass',
        'num_class': 3,
        'metric': 'multi_logloss',
        'verbosity': -1,
        'seed': 42
    }
    
    train_data = lgb.Dataset(X_train, label=y_train)
    model = lgb.train(params, train_data, num_boost_round=10)
    
    # 3. Save model and metadata
    models_dir = os.path.join(os.path.dirname(__file__), '..', 'models', 'test_multiclass')
    os.makedirs(models_dir, exist_ok=True)
    
    model_path = os.path.join(models_dir, "lgb_multiclass.joblib")
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")
    
    meta_path = os.path.join(models_dir, "lgb_multiclass_meta.json")
    metadata = {
        "model_name": "lgb_multiclass",
        "type": "lightgbm",
        "label_mapping": label_mapping,
        "created_at": "2024-01-01"
    }
    with open(meta_path, 'w') as f:
        json.dump(metadata, f)
    print(f"Metadata saved to {meta_path}")
    
    # 4. Test InferenceEngine
    print("Testing InferenceEngine...")
    engine = InferenceEngine(models_dir=models_dir)
    
    # Load model
    success = engine.load_model("lgb_multiclass", "lightgbm")
    if not success:
        print("Failed to load model!")
        return False
    
    # Predict
    print("Running prediction...")
    # Use X_test for prediction
    results = engine.predict_batch(X_test)
    
    predictions = results["predictions"]
    confidences = results["confidences"]
    attack_types = results.get("attack_types")
    
    print(f"Predictions: {predictions[:5]}")
    print(f"Confidences: {confidences[:5]}")
    print(f"Attack Types: {attack_types[:5]}")
    
    # Verify results
    if attack_types is None:
        print("Error: attack_types missing from results")
        return False
        
    # Check if we have specific labels
    has_specific_labels = any(t in ["DoS", "PortScan"] for t in attack_types)
    if has_specific_labels:
        print("Success: Specific attack types detected!")
    else:
        print("Warning: Only Normal or generic labels found (might be due to random data)")
        
    # Verify mapping logic
    # Manually check one prediction
    raw_pred = model.predict(X_test[:1])
    class_idx = np.argmax(raw_pred, axis=1)[0]
    expected_label = label_mapping[class_idx]
    
    actual_label = attack_types[0]
    
    print(f"Manual check: Class {class_idx} -> {expected_label}, Engine output: {actual_label}")
    
    if expected_label == actual_label:
        print("Verification PASSED")
        return True
    else:
        print("Verification FAILED: Label mismatch")
        return False

if __name__ == "__main__":
    try:
        test_multiclass_inference()
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
