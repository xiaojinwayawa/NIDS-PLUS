"""
Model Training Module
Handles dataset loading, model training, evaluation, and saving
"""
import os
import json
import time
import numpy as np
import pandas as pd
import joblib
from typing import Dict, Any, Tuple, Optional
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import lightgbm as lgb
import xgboost as xgb

from config import settings
from logging_config import app_logger as logger

class TrainingManager:
    """
    Manages model training lifecycle
    """
    
    def __init__(self, models_dir: str = "models", data_dir: str = "data"):
        self.models_dir = models_dir
        self.data_dir = data_dir
        
        if not os.path.exists(self.models_dir):
            os.makedirs(self.models_dir)
            
    def load_dataset(self, dataset_path: str) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Load dataset from CSV
        Assumes last column is label or specific column name
        """
        try:
            logger.info(f"Loading dataset from {dataset_path}...")
            df = pd.read_csv(dataset_path)
            
            # Simple preprocessing for prototype
            # Drop non-numeric for now except encoded ones
            # Assume label is 'label' or 'class'
            target_col = None
            if 'label' in df.columns:
                target_col = 'label'
            elif 'class' in df.columns:
                target_col = 'class'
            else:
                # Assume last column
                target_col = df.columns[-1]
                
            X = df.drop(columns=[target_col])
            y = df[target_col]
            
            # Basic encoding for string columns if any (simple label encoding)
            for col in X.select_dtypes(include=['object']).columns:
                X[col] = X[col].astype('category').cat.codes
                
            # Encode target if string
            if y.dtype == 'object':
                 y = y.astype('category').cat.codes
                 
            return X, y
        except Exception as e:
            logger.error(f"Error loading dataset: {e}")
            raise e

    def train_model(self, 
                   model_type: str, 
                   dataset_path: str, 
                   params: Dict[str, Any] = None,
                   model_name: str = "new_model") -> Dict[str, Any]:
        """
        Train a new model
        
        Args:
            model_type: 'lightgbm' or 'xgboost'
            dataset_path: Path to CSV data
            params: Hyperparameters
            model_name: Name for saving
            
        Returns:
            Dictionary with training metrics
        """
        start_time = time.time()
        
        # Load Data
        X, y = self.load_dataset(dataset_path)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        model = None
        
        try:
            if model_type == "lightgbm":
                if params is None:
                    params = {'objective': 'binary', 'verbosity': -1}
                
                # Convert to Dataset
                train_data = lgb.Dataset(X_train, label=y_train)
                test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
                
                model = lgb.train(
                    params,
                    train_data,
                    valid_sets=[test_data],
                    num_boost_round=100,
                    callbacks=[lgb.early_stopping(stopping_rounds=10), lgb.log_evaluation(0)]
                )
                
                # Predict
                y_pred_prob = model.predict(X_test)
                y_pred = (y_pred_prob > 0.5).astype(int)
                
            elif model_type == "xgboost":
                if params is None:
                    params = {'objective': 'binary:logistic', 'eval_metric': 'logloss'}
                    
                dtrain = xgb.DMatrix(X_train, label=y_train)
                dtest = xgb.DMatrix(X_test, label=y_test)
                
                model = xgb.train(
                    params,
                    dtrain,
                    num_boost_round=100,
                    evals=[(dtest, "Test")],
                    early_stopping_rounds=10,
                    verbose_eval=False
                )
                
                y_pred_prob = model.predict(dtest)
                y_pred = (y_pred_prob > 0.5).astype(int)
                
            else:
                raise ValueError(f"Unsupported model type: {model_type}")
                
            # Calculate Metrics
            metrics = {
                "accuracy": float(accuracy_score(y_test, y_pred)),
                "precision": float(precision_score(y_test, y_pred, zero_division=0)),
                "recall": float(recall_score(y_test, y_pred, zero_division=0)),
                "f1": float(f1_score(y_test, y_pred, zero_division=0)),
                "training_time": time.time() - start_time
            }
            
            logger.info(f"Training completed for {model_name}. Accuracy: {metrics['accuracy']:.4f}")
            
            # Save Model
            save_path = os.path.join(self.models_dir, f"{model_name}.joblib")
            joblib.dump(model, save_path)
            
            # Save Metadata
            meta_path = os.path.join(self.models_dir, f"{model_name}_meta.json")
            with open(meta_path, 'w') as f:
                json.dump({
                    "name": model_name,
                    "type": model_type,
                    "params": params,
                    "metrics": metrics,
                    "timestamp": time.time()
                }, f, indent=4)
                
            return metrics
            
        except Exception as e:
            logger.error(f"Error during training: {e}")
            raise e
