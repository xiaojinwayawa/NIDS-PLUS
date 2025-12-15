
import pytest
import numpy as np
import time
from ml.shap_analyzer import SHAPAnalyzer
import lightgbm as lgb
from sklearn.datasets import make_classification

@pytest.fixture
def mock_lgbm_model():
    # Train a simple LightGBM model
    X, y = make_classification(n_samples=100, n_features=20, random_state=42)
    train_data = lgb.Dataset(X, label=y)
    params = {'objective': 'binary', 'verbosity': -1}
    model = lgb.train(params, train_data, num_boost_round=10)
    return model

def test_shap_calculation_timeliness(mock_lgbm_model):
    """
    Property 8: SHAP Calculation Timeliness
    Req 7.3: Verify SHAP calculation is reasonably fast (e.g. < 200ms for TreeExplainer)
    """
    analyzer = SHAPAnalyzer()
    analyzer.initialize_explainer("test_model", mock_lgbm_model, "lightgbm")
    
    # Create a single sample
    features = np.random.rand(1, 20)
    feature_names = [f"f{i}" for i in range(20)]
    
    start = time.time()
    result = analyzer.compute_shap_values("test_model", features, feature_names)
    duration = (time.time() - start) * 1000
    
    assert result is not None
    assert "top_features" in result
    assert len(result["top_features"]) <= 5
    
    # Check timeliness
    # TreeExplainer is usually very fast (<50ms for small models)
    # We set a loose bound of 200ms to account for CI environments
    assert duration < 200
    print(f"\nSHAP calculation time: {duration:.2f}ms")

def test_shap_structure_correctness(mock_lgbm_model):
    """
    Verify structure of SHAP output
    """
    analyzer = SHAPAnalyzer()
    analyzer.initialize_explainer("test_model", mock_lgbm_model, "lightgbm")
    
    features = np.random.rand(1, 20)
    result = analyzer.compute_shap_values("test_model", features)
    
    assert "base_value" in result
    assert "top_features" in result
    
    top = result["top_features"]
    assert isinstance(top, list)
    if len(top) > 0:
        item = top[0]
        assert "feature" in item
        assert "value" in item
        assert "shap_value" in item
        assert "contribution" in item
        assert item["contribution"] in ["positive", "negative"]
