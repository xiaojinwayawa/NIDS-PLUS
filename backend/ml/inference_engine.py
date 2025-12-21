"""
Inference Engine Module
Handles model loading, batch inference, and result aggregation
"""
import os
import time
import threading
import numpy as np
import joblib
from typing import Dict, List, Any, Optional, Tuple, Union
import lightgbm as lgb
import xgboost as xgb
# Import deep learning frameworks conditionally to avoid overhead if not used
# import tensorflow as tf
# import torch

from config import settings
from logging_config import app_logger as logger

class InferenceEngine:
    """
    Engine for running ML/DL model inference
    Supports single model and hybrid (ensemble) modes
    """

    def __init__(self, models_dir: str = None):
        # Default to project root models directory
        if models_dir is None:
            # Get the project root (parent of backend)
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.dirname(backend_dir)
            models_dir = os.path.join(project_root, "models")
        self.models_dir = models_dir
        self.loaded_models: Dict[str, Any] = {}
        self.model_metadata: Dict[str, Dict] = {}
        self.lock = threading.RLock()
        
    def load_model(self, model_name: str, model_type: str, version: str = "latest") -> bool:
        """
        Load a model from disk
        
        Args:
            model_name: Name of the model
            model_type: Type (lightgbm, xgboost, cnn, gru)
            version: Model version
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            # Check if already loaded (Idempotency)
            model_key = f"{model_name}_{version}"
            if model_key in self.loaded_models:
                logger.info(f"Model {model_key} already loaded")
                return True
            
            try:
                # Construct path
                # For prototype, assume flat structure or versioned folders
                model_path = os.path.join(self.models_dir, f"{model_name}.joblib")
                if not os.path.exists(model_path):
                     # Try other extensions
                     model_path = os.path.join(self.models_dir, f"{model_name}.json")
                
                if not os.path.exists(model_path):
                    logger.error(f"Model file not found for {model_name}")
                    return False
                
                logger.info(f"Loading model {model_name} from {model_path}...")
                
                model = None
                if model_type == "lightgbm":
                    # Load LightGBM
                    if model_path.endswith(".joblib"):
                        model = joblib.load(model_path)
                    else:
                        model = lgb.Booster(model_file=model_path)
                        
                elif model_type == "xgboost":
                    # Load XGBoost
                    if model_path.endswith(".joblib"):
                         model = joblib.load(model_path)
                    else:
                        model = xgb.Booster()
                        model.load_model(model_path)
                        
                # TODO: Add TF/PyTorch loading
                
                if model:
                    self.loaded_models[model_key] = model
                    self.model_metadata[model_key] = {
                        "name": model_name,
                        "type": model_type,
                        "version": version,
                        "path": model_path
                    }
                    logger.info(f"Model {model_key} loaded successfully")
                    return True
                else:
                    logger.error(f"Failed to load model {model_name}: Unknown type or load error")
                    return False
                    
            except Exception as e:
                logger.error(f"Error loading model {model_name}: {e}")
                return False

    def unload_model(self, model_name: str, version: str = "latest"):
        """Unload a model to free memory"""
        with self.lock:
            model_key = f"{model_name}_{version}"
            if model_key in self.loaded_models:
                del self.loaded_models[model_key]
                del self.model_metadata[model_key]
                logger.info(f"Model {model_key} unloaded")

    def predict_batch(self, features: np.ndarray, model_names: List[str] = None) -> Dict[str, Any]:
        """
        Run batch inference using specified models
        
        Args:
            features: Numpy array of features (N_samples, N_features)
            model_names: List of model names to use (if None, use all loaded)
            
        Returns:
            Dictionary with results:
            {
                "predictions": List[int], # 0 or 1
                "confidences": List[float],
                "inference_time_ms": float,
                "model_breakdown": Dict
            }
        """
        start_time = time.time()
        
        if features.ndim == 1:
            features = features.reshape(1, -1)
            
        if not self.loaded_models:
            logger.warning("No models loaded for inference")
            return {
                "predictions": [0] * len(features),
                "confidences": [0.0] * len(features),
                "inference_time_ms": (time.time() - start_time) * 1000,
                "error": "No models loaded"
            }
            
        results = {}
        target_models = []
        
        with self.lock:
            if model_names:
                for key in self.loaded_models:
                    # Simple matching logic, can be improved
                    name = self.model_metadata[key]["name"]
                    if name in model_names:
                        target_models.append(key)
            else:
                target_models = list(self.loaded_models.keys())
        
        if not target_models:
             logger.warning("No matching models found")
             return {
                "predictions": [0] * len(features),
                "confidences": [0.0] * len(features),
                "inference_time_ms": (time.time() - start_time) * 1000,
                "error": "No matching models"
            }

        # Run inference for each model
        # Using simple averaging (soft voting) for hybrid inference
        aggregated_probs = np.zeros(len(features))
        
        for model_key in target_models:
            try:
                model = self.loaded_models[model_key]
                model_type = self.model_metadata[model_key]["type"]
                
                probs = None
                if model_type == "lightgbm":
                    # LightGBM predict returns probabilities for binary class
                    if hasattr(model, "predict_proba"):
                        probs = model.predict_proba(features)[:, 1]
                    else:
                        probs = model.predict(features)
                elif model_type == "xgboost":
                    # XGBoost - handle both sklearn API and native Booster
                    if hasattr(model, "predict_proba"):
                        # sklearn XGBClassifier - need to handle feature names
                        try:
                            # Try direct prediction first
                            probs = model.predict_proba(features)[:, 1]
                        except Exception:
                            # If feature name mismatch, try with feature validation disabled
                            import pandas as pd
                            if hasattr(model, 'feature_names_in_'):
                                feature_names = model.feature_names_in_
                                df = pd.DataFrame(features, columns=feature_names)
                                probs = model.predict_proba(df)[:, 1]
                            else:
                                dtest = xgb.DMatrix(features)
                                probs = model.predict(dtest)
                    else:
                        # Native XGBoost Booster - must use DMatrix with feature names
                        # Get feature names from the model if available
                        feature_names = getattr(model, 'feature_names', None)
                        if feature_names:
                            dtest = xgb.DMatrix(features, feature_names=feature_names)
                        else:
                            dtest = xgb.DMatrix(features)
                        probs = model.predict(dtest)
                
                if probs is not None:
                    results[model_key] = probs
                    aggregated_probs += probs
                
            except Exception as e:
                logger.error(f"Inference error for {model_key}: {e}")
        
        # Average probabilities
        if results:
            aggregated_probs /= len(results)
            
        predictions = (aggregated_probs > 0.5).astype(int).tolist()
        confidences = aggregated_probs.tolist()
        
        end_time = time.time()
        inference_time_ms = (end_time - start_time) * 1000
        
        return {
            "predictions": predictions,
            "confidences": confidences,
            "inference_time_ms": inference_time_ms,
            "model_breakdown": results
        }
