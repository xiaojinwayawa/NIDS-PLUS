"""
Model Training Module
Handles dataset loading, model training, evaluation, and saving.
Supports both traditional ML (LightGBM/XGBoost) and deep learning (CNN/GRU) models.
"""
import os
import json
import time
import numpy as np
import pandas as pd
import joblib
from typing import Dict, Any, Tuple, Optional, Callable
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import lightgbm as lgb
import xgboost as xgb

from config import settings
from logging_config import app_logger as logger

# Get project root directory
_current_file = os.path.abspath(__file__)
_ml_dir = os.path.dirname(_current_file)         # backend/ml
_backend_dir = os.path.dirname(_ml_dir)          # backend
_project_root = os.path.dirname(_backend_dir)    # project_root
_default_models_dir = os.path.join(_project_root, "models")
_default_data_dir = os.path.join(_project_root, "data")

# Global training progress storage
_training_progress: Dict[str, Dict[str, Any]] = {}
_stop_flags: Dict[str, bool] = {}

def get_training_progress(task_id: str) -> Optional[Dict[str, Any]]:
    """Get training progress for a task"""
    return _training_progress.get(task_id)

def set_training_progress(task_id: str, progress: Dict[str, Any]):
    """Set training progress for a task"""
    _training_progress[task_id] = progress

def clear_training_progress(task_id: str):
    """Clear training progress for a task"""
    if task_id in _training_progress:
        del _training_progress[task_id]

def stop_training_task(task_id: str):
    """Signal a training task to stop"""
    _stop_flags[task_id] = True

def is_training_stopped(task_id: str) -> bool:
    """Check if training should stop"""
    return _stop_flags.get(task_id, False)

def clear_stop_flag(task_id: str):
    """Clear stop flag for a task"""
    if task_id in _stop_flags:
        del _stop_flags[task_id]

class TrainingManager:
    """
    Manages model training lifecycle for both ML and DL models.
    """
    
    def __init__(self, models_dir: str = None, data_dir: str = None):
        self.models_dir = models_dir or _default_models_dir
        self.data_dir = data_dir or _default_data_dir
        self.scaler = StandardScaler()
        
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
            elif 'Label' in df.columns:
                target_col = 'Label'
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
            
            # Handle missing and infinite values
            X = X.fillna(0)
            X = X.replace([np.inf, -np.inf], 0)
                 
            return X, y
        except Exception as e:
            logger.error(f"Error loading dataset: {e}")
            raise e

    def train_model(self, 
                   model_type: str, 
                   dataset_path: str, 
                   params: Dict[str, Any] = None,
                   model_name: str = "new_model",
                   task_id: str = None) -> Dict[str, Any]:
        """
        Train a new model.
        
        Args:
            model_type: 'lightgbm', 'xgboost', 'cnn', or 'gru'
            dataset_path: Path to CSV data
            params: Hyperparameters
            model_name: Name for saving
            task_id: Optional task ID for progress tracking
            
        Returns:
            Dictionary with training metrics
        """
        # Route to appropriate trainer
        if model_type in ["cnn", "gru"]:
            return self._train_deep_learning_model(
                model_type, dataset_path, params, model_name, task_id
            )
        else:
            return self._train_ml_model(
                model_type, dataset_path, params, model_name, task_id
            )
    
    def _train_deep_learning_model(self,
                                   model_type: str,
                                   dataset_path: str,
                                   params: Dict[str, Any] = None,
                                   model_name: str = "dl_model",
                                   task_id: str = None) -> Dict[str, Any]:
        """Train a deep learning model (CNN or GRU)"""
        from ml.deep_learning_trainer import DeepLearningTrainer, DeepLearningConfig
        
        # Create config from params
        config = DeepLearningConfig(model_type=model_type)
        if params:
            if "epochs" in params:
                config.epochs = params["epochs"]
            if "batch_size" in params:
                config.batch_size = params["batch_size"]
            if "learning_rate" in params:
                config.learning_rate = params["learning_rate"]
            if "random_seed" in params:
                config.random_seed = params["random_seed"]
        
        trainer = DeepLearningTrainer(self.models_dir, self.data_dir)
        return trainer.train_model(
            model_type=model_type,
            dataset_path=dataset_path,
            config=config,
            model_name=model_name,
            task_id=task_id
        )
    
    def _train_ml_model(self, 
                       model_type: str, 
                       dataset_path: str, 
                       params: Dict[str, Any] = None,
                       model_name: str = "new_model",
                       task_id: str = None) -> Dict[str, Any]:
        """Train a traditional ML model (LightGBM or XGBoost)"""
        start_time = time.time()
        num_boost_round = 100
        
        def update_progress(stage: str, current: int, total: int, message: str = ""):
            if task_id:
                progress = {
                    "stage": stage,
                    "current": current,
                    "total": total,
                    "percent": int((current / total) * 100) if total > 0 else 0,
                    "message": message,
                    "elapsed": time.time() - start_time
                }
                set_training_progress(task_id, progress)
        
        # Stage 1: Load Data (10%)
        update_progress("loading", 0, 100, "Loading dataset...")
        X, y = self.load_dataset(dataset_path)
        update_progress("loading", 10, 100, f"Dataset loaded: {len(X)} samples")
        
        # Stage 2: Split Data (15%)
        update_progress("preprocessing", 10, 100, "Splitting data...")
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        update_progress("preprocessing", 15, 100, f"Train: {len(X_train)}, Test: {len(X_test)}")
        
        model = None
        
        try:
            if model_type == "lightgbm":
                if params is None:
                    params = {'objective': 'binary', 'verbosity': -1}
                
                # Convert to Dataset
                train_data = lgb.Dataset(X_train, label=y_train)
                test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
                
                # Custom callback for progress
                def lgb_progress_callback(env):
                    iteration = env.iteration + 1
                    # Training is 15% to 85%
                    progress_pct = 15 + int((iteration / num_boost_round) * 70)
                    update_progress("training", progress_pct, 100, f"Training iteration {iteration}/{num_boost_round}")
                
                update_progress("training", 15, 100, "Starting LightGBM training...")
                model = lgb.train(
                    params,
                    train_data,
                    valid_sets=[test_data],
                    num_boost_round=num_boost_round,
                    callbacks=[
                        lgb.early_stopping(stopping_rounds=10), 
                        lgb.log_evaluation(0),
                        lgb_progress_callback
                    ]
                )
                
                # Predict
                update_progress("evaluating", 85, 100, "Evaluating model...")
                y_pred_prob = model.predict(X_test)
                y_pred = (y_pred_prob > 0.5).astype(int)
                
            elif model_type == "xgboost":
                if params is None:
                    params = {'objective': 'binary:logistic', 'eval_metric': 'logloss'}
                    
                dtrain = xgb.DMatrix(X_train, label=y_train)
                dtest = xgb.DMatrix(X_test, label=y_test)
                
                # Custom callback for progress
                class XGBProgressCallback(xgb.callback.TrainingCallback):
                    def after_iteration(self, model, epoch, evals_log):
                        iteration = epoch + 1
                        progress_pct = 15 + int((iteration / num_boost_round) * 70)
                        update_progress("training", progress_pct, 100, f"Training iteration {iteration}/{num_boost_round}")
                        return False
                
                update_progress("training", 15, 100, "Starting XGBoost training...")
                model = xgb.train(
                    params,
                    dtrain,
                    num_boost_round=num_boost_round,
                    evals=[(dtest, "Test")],
                    early_stopping_rounds=10,
                    verbose_eval=False,
                    callbacks=[XGBProgressCallback()]
                )
                
                update_progress("evaluating", 85, 100, "Evaluating model...")
                y_pred_prob = model.predict(dtest)
                y_pred = (y_pred_prob > 0.5).astype(int)
                
            else:
                raise ValueError(f"Unsupported ML model type: {model_type}")
                
            # Calculate Metrics (90%)
            update_progress("evaluating", 90, 100, "Calculating metrics...")
            metrics = {
                "accuracy": float(accuracy_score(y_test, y_pred)),
                "precision": float(precision_score(y_test, y_pred, zero_division=0)),
                "recall": float(recall_score(y_test, y_pred, zero_division=0)),
                "f1": float(f1_score(y_test, y_pred, zero_division=0)),
                "training_time": time.time() - start_time
            }
            
            logger.info(f"Training completed for {model_name}. Accuracy: {metrics['accuracy']:.4f}")
            
            # Save Model (95%)
            update_progress("saving", 95, 100, "Saving model...")
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
            
            # Complete (100%)
            update_progress("complete", 100, 100, "Training complete!")
                
            return metrics
            
        except Exception as e:
            logger.error(f"Error during training: {e}")
            if task_id:
                set_training_progress(task_id, {
                    "stage": "error",
                    "current": 0,
                    "total": 100,
                    "percent": 0,
                    "message": str(e),
                    "elapsed": time.time() - start_time
                })
            raise e
