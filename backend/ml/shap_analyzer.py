"""
SHAP Analysis Module
Provides interpretability for model predictions using SHAP values
"""
import time
import numpy as np
import shap
import pandas as pd
from typing import Dict, List, Any, Optional, Union
import joblib
from functools import lru_cache
import threading

from logging_config import app_logger as logger

class SHAPAnalyzer:
    """
    Analyzer for computing SHAP values
    Supports TreeExplainer for LightGBM/XGBoost
    """
    
    def __init__(self, background_data: Optional[np.ndarray] = None):
        """
        Initialize analyzer
        
        Args:
            background_data: Optional background dataset for KernelExplainer (not needed for TreeExplainer)
        """
        self.explainers: Dict[str, Any] = {}
        self.background_data = background_data
        self.lock = threading.RLock()
        
    def initialize_explainer(self, model_key: str, model: Any, model_type: str):
        """
        Initialize SHAP explainer for a model
        
        Args:
            model_key: Unique key for the model
            model: Model object (LightGBM/XGBoost booster or sklearn wrapper)
            model_type: Type of model
        """
        with self.lock:
            if model_key in self.explainers:
                return

            try:
                logger.info(f"Initializing SHAP explainer for {model_key} ({model_type})...")
                
                if model_type in ["lightgbm", "xgboost"]:
                    # TreeExplainer is fast and optimized for trees
                    explainer = shap.TreeExplainer(model)
                    self.explainers[model_key] = explainer
                    logger.info(f"TreeExplainer initialized for {model_key}")
                else:
                    # Fallback to KernelExplainer (slower) or DeepExplainer
                    if self.background_data is not None:
                        explainer = shap.KernelExplainer(model.predict, self.background_data)
                        self.explainers[model_key] = explainer
                        logger.info(f"KernelExplainer initialized for {model_key}")
                    else:
                        logger.warning(f"Cannot initialize explainer for {model_type}: no background data")
                        
            except Exception as e:
                logger.error(f"Error initializing SHAP explainer: {e}")

    def compute_shap_values(self, 
                          model_key: str, 
                          features: np.ndarray, 
                          feature_names: List[str] = None,
                          top_k: int = 5) -> Dict[str, Any]:
        """
        Compute SHAP values for a single sample (or batch)
        
        Args:
            model_key: Model identifier
            features: Feature array (1, N_features) or (N_samples, N_features)
            feature_names: List of feature names
            top_k: Number of top contributing features to return
            
        Returns:
            Dictionary containing SHAP values and metadata
        """
        start_time = time.time()
        
        if model_key not in self.explainers:
            logger.warning(f"Explainer not found for {model_key}")
            return {}

        try:
            explainer = self.explainers[model_key]
            
            # Compute SHAP values
            # check_additivity=False to suppress errors if model output slightly diverges
            shap_values = explainer.shap_values(features, check_additivity=False)
            
            # Handle different output formats of shap_values
            # For binary classification, LightGBM/XGBoost might return list [class0, class1] or just class1
            if isinstance(shap_values, list):
                # Usually we care about the positive class (attack)
                if len(shap_values) > 1:
                     # Binary classification: index 1 is usually positive class
                     vals = shap_values[1]
                else:
                     vals = shap_values[0]
            else:
                vals = shap_values

            # If batch, take the first one for detailed analysis (prototype limitation)
            if vals.ndim > 1:
                vals = vals[0]
                sample_features = features[0]
            else:
                sample_features = features
                
            # Calculate top K features
            # Absolute value determines importance magnitude
            abs_vals = np.abs(vals)
            top_indices = np.argsort(abs_vals)[::-1][:top_k]
            
            top_features = []
            for idx in top_indices:
                name = feature_names[idx] if feature_names and idx < len(feature_names) else f"feature_{idx}"
                top_features.append({
                    "feature": name,
                    "value": float(sample_features[idx]),
                    "shap_value": float(vals[idx]),
                    "contribution": "positive" if vals[idx] > 0 else "negative"
                })
                
            duration = (time.time() - start_time) * 1000
            
            return {
                "base_value": float(explainer.expected_value[-1] if isinstance(explainer.expected_value, list) else explainer.expected_value),
                "top_features": top_features,
                "calculation_time_ms": duration
            }
            
        except Exception as e:
            logger.error(f"Error computing SHAP values: {e}")
            return {}
