
import pytest
import os
import pandas as pd
import numpy as np
from ml.trainer import TrainingManager
from sklearn.datasets import make_classification

@pytest.fixture
def mock_dataset(tmp_path):
    # Create a dummy CSV dataset
    X, y = make_classification(n_samples=200, n_features=10, random_state=42)
    df = pd.DataFrame(X, columns=[f"f{i}" for i in range(10)])
    df['label'] = y
    
    file_path = tmp_path / "test_data.csv"
    df.to_csv(file_path, index=False)
    return str(file_path)

@pytest.fixture
def trainer(tmp_path):
    return TrainingManager(models_dir=str(tmp_path / "models"))

def test_model_reproducibility(trainer, mock_dataset):
    """
    Property 12: Model Reproducibility
    Req 12.1: Verify training twice with same seed produces same metrics
    """
    params = {'objective': 'binary', 'verbosity': -1, 'seed': 42}
    
    # Train 1
    metrics1 = trainer.train_model("lightgbm", mock_dataset, params, "model1")
    
    # Train 2
    metrics2 = trainer.train_model("lightgbm", mock_dataset, params, "model2")
    
    # Check metrics identity
    assert metrics1["accuracy"] == metrics2["accuracy"]
    assert metrics1["f1"] == metrics2["f1"]

def test_training_evaluation_metrics(trainer, mock_dataset):
    """
    Property 13: Training Evaluation Metrics
    Req 13.1: Verify all required metrics are calculated
    """
    metrics = trainer.train_model("lightgbm", mock_dataset, params=None, model_name="test_metrics")
    
    assert "accuracy" in metrics
    assert "precision" in metrics
    assert "recall" in metrics
    assert "f1" in metrics
    assert "training_time" in metrics
    
    # Sanity check values
    assert 0 <= metrics["accuracy"] <= 1.0
