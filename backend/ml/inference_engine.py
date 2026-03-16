"""
Inference Engine Module
Handles model loading, batch inference, and result aggregation.
Supports traditional ML (LightGBM/XGBoost) and deep learning (1D-CNN/GRU) models.

补充需求 A：深度学习模型训练与推理链路（1D-CNN/GRU）
补充需求 B：混合模型融合策略（ML + DL）
"""
import os
import time
import threading
import json
import numpy as np
import joblib
from typing import Dict, List, Any, Optional, Tuple, Union
from enum import Enum
import lightgbm as lgb
import xgboost as xgb

from config import settings
from logging_config import app_logger as logger


class FusionStrategy(Enum):
    """Model fusion strategies for hybrid inference"""
    VOTING = "voting"           # Hard voting (majority)
    WEIGHTED = "weighted"       # Weighted average of probabilities
    CASCADE = "cascade"         # ML first, DL for uncertain cases
    STACKING = "stacking"       # Meta-learner on model outputs


class InferenceEngine:
    """
    Engine for running ML/DL model inference.
    Supports single model, hybrid (ensemble), and fusion modes.
    
    Model types supported:
    - Traditional ML: lightgbm, xgboost
    - Deep Learning: cnn, gru (TensorFlow/Keras)
    """

    def __init__(self, models_dir: str = None):
        # Default to project root models directory
        if models_dir is None:
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.dirname(backend_dir)
            models_dir = os.path.join(project_root, "models")
        self.models_dir = models_dir
        self.loaded_models: Dict[str, Any] = {}
        self.model_metadata: Dict[str, Dict] = {}
        self.model_scalers: Dict[str, Any] = {}  # Scalers for DL models
        self.lock = threading.RLock()
        
        # Fusion configuration
        self.fusion_strategy = FusionStrategy.WEIGHTED
        self.model_weights: Dict[str, float] = {}  # Weights for weighted fusion
        self.cascade_threshold = 0.7  # Confidence threshold for cascade strategy
        
        # TensorFlow availability
        self._tf_available = self._check_tensorflow()
    
    def _check_tensorflow(self) -> bool:
        """Check if TensorFlow is available"""
        try:
            import tensorflow as tf
            return True
        except ImportError:
            logger.warning("TensorFlow not available. Deep learning inference disabled.")
            return False
    
    def set_fusion_strategy(self, strategy: str, weights: Dict[str, float] = None, 
                           cascade_threshold: float = 0.7):
        """
        Configure fusion strategy for hybrid inference.
        
        Args:
            strategy: 'voting', 'weighted', 'cascade', or 'stacking'
            weights: Model weights for weighted fusion (model_name -> weight)
            cascade_threshold: Confidence threshold for cascade strategy
        """
        self.fusion_strategy = FusionStrategy(strategy)
        if weights:
            self.model_weights = weights
        self.cascade_threshold = cascade_threshold
        logger.info(f"Fusion strategy set to: {strategy}")
        
    def load_model(self, model_name: str, model_type: str, version: str = "latest") -> bool:
        """
        Load a model from disk.
        
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
                model = None
                model_path = None
                
                # Handle different model types
                if model_type in ["lightgbm", "xgboost"]:
                    model, model_path = self._load_ml_model(model_name, model_type)
                elif model_type in ["cnn", "gru", "transformer"]:
                    model, model_path = self._load_dl_model(model_name, model_type)
                else:
                    logger.error(f"Unknown model type: {model_type}")
                    return False
                
                if model:
                    self.loaded_models[model_key] = model
                    
                    # Try to load metadata (label mapping, etc.)
                    metadata = {
                        "name": model_name,
                        "type": model_type,
                        "version": version,
                        "path": model_path,
                        "is_deep_learning": model_type in ["cnn", "gru", "transformer"]
                    }
                    
                    # Check for _meta.json file
                    try:
                        base_path = os.path.splitext(model_path)[0]
                        # Handle case where extension might be different or path construction varies
                        # Try to find meta file in the same directory
                        dir_name = os.path.dirname(model_path)
                        meta_path = os.path.join(dir_name, f"{model_name}_meta.json")
                        
                        if os.path.exists(meta_path):
                            with open(meta_path, 'r') as f:
                                meta_content = json.load(f)
                                metadata.update(meta_content)
                                logger.info(f"Loaded metadata for {model_name}")
                    except Exception as e:
                        logger.warning(f"Could not load metadata for {model_name}: {e}")
                    
                    self.model_metadata[model_key] = metadata
                    logger.info(f"Model {model_key} loaded successfully")
                    return True
                else:
                    logger.error(f"Failed to load model {model_name}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error loading model {model_name}: {e}")
                return False
    
    def _load_ml_model(self, model_name: str, model_type: str) -> Tuple[Any, str]:
        """Load traditional ML model (LightGBM/XGBoost)"""
        # Try different file extensions
        for ext in [".joblib", ".json", ".pkl"]:
            model_path = os.path.join(self.models_dir, f"{model_name}{ext}")
            if os.path.exists(model_path):
                break
        else:
            logger.error(f"Model file not found for {model_name}")
            return None, None
        
        logger.info(f"Loading ML model {model_name} from {model_path}...")
        
        if model_type == "lightgbm":
            if model_path.endswith(".joblib") or model_path.endswith(".pkl"):
                model = joblib.load(model_path)
            else:
                model = lgb.Booster(model_file=model_path)
        elif model_type == "xgboost":
            if model_path.endswith(".joblib") or model_path.endswith(".pkl"):
                model = joblib.load(model_path)
            else:
                model = xgb.Booster()
                model.load_model(model_path)
        else:
            return None, None
        
        return model, model_path
    
    def _load_dl_model(self, model_name: str, model_type: str) -> Tuple[Any, str]:
        """Load deep learning model (CNN/GRU)"""
        if not self._tf_available:
            logger.error("TensorFlow not available. Cannot load deep learning model.")
            return None, None
        
        import tensorflow as tf
        
        # Try different file extensions
        for ext in [".h5", ".keras", ".pb"]:
            model_path = os.path.join(self.models_dir, f"{model_name}{ext}")
            if os.path.exists(model_path):
                break
        else:
            logger.error(f"DL model file not found for {model_name}")
            return None, None
        
        logger.info(f"Loading DL model {model_name} from {model_path}...")
        
        try:
            model = tf.keras.models.load_model(model_path)
            
            # Load associated scaler if exists
            scaler_path = os.path.join(self.models_dir, f"{model_name}_scaler.joblib")
            if os.path.exists(scaler_path):
                self.model_scalers[model_name] = joblib.load(scaler_path)
                logger.info(f"Loaded scaler for {model_name}")
            
            return model, model_path
            
        except Exception as e:
            logger.error(f"Error loading DL model: {e}")
            return None, None

    def unload_model(self, model_name: str, version: str = "latest"):
        """Unload a model to free memory"""
        with self.lock:
            model_key = f"{model_name}_{version}"
            if model_key in self.loaded_models:
                # Clear TensorFlow session if DL model
                if self.model_metadata.get(model_key, {}).get("is_deep_learning"):
                    try:
                        import tensorflow as tf
                        tf.keras.backend.clear_session()
                    except:
                        pass
                
                del self.loaded_models[model_key]
                del self.model_metadata[model_key]
                
                # Remove scaler if exists
                if model_name in self.model_scalers:
                    del self.model_scalers[model_name]
                
                logger.info(f"Model {model_key} unloaded")

    def predict_batch(self, features: np.ndarray, model_names: List[str] = None) -> Dict[str, Any]:
        """
        Run batch inference using specified models with fusion strategy.
        
        Args:
            features: Numpy array of features (N_samples, N_features)
            model_names: List of model names to use (if None, use all loaded)
            
        Returns:
            Dictionary with results:
            {
                "predictions": List[int],     # 0=Normal, 1=Attack
                "confidences": List[float],   # Probability of attack
                "attack_types": List[str],    # Specific attack types (if available)
                "inference_time_ms": float,
                "model_breakdown": Dict,
                "fusion_strategy": str
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
                "attack_types": ["Normal"] * len(features),
                "inference_time_ms": (time.time() - start_time) * 1000,
                "error": "No models loaded"
            }
        
        # Get target models
        target_models = self._get_target_models(model_names)
        
        if not target_models:
            logger.warning("No matching models found")
            return {
                "predictions": [0] * len(features),
                "confidences": [0.0] * len(features),
                "attack_types": ["Normal"] * len(features),
                "inference_time_ms": (time.time() - start_time) * 1000,
                "error": "No matching models"
            }

        # Run inference for each model
        model_results = {}
        model_class_preds = {} # Store raw class predictions (indices)
        
        for model_key in target_models:
            try:
                # probs is either 1D array (binary prob) or 2D array (multi-class probs)
                probs = self._predict_single_model(model_key, features)
                
                if probs is not None:
                    model_results[model_key] = probs
                    
                    # Also get class predictions if possible
                    if probs.ndim > 1 and probs.shape[1] > 1:
                        # Multi-class
                        model_class_preds[model_key] = np.argmax(probs, axis=1)
                    else:
                        # Binary
                        model_class_preds[model_key] = (probs > 0.5).astype(int)
                        
            except Exception as e:
                logger.error(f"Inference error for {model_key}: {e}")
        
        # Apply fusion strategy
        predictions, confidences, attack_types = self._apply_fusion(model_results, model_class_preds, features)
        
        end_time = time.time()
        inference_time_ms = (end_time - start_time) * 1000
        
        return {
            "predictions": predictions,
            "confidences": confidences,
            "attack_types": attack_types,
            "inference_time_ms": inference_time_ms,
            "model_breakdown": {k: v.tolist() if isinstance(v, np.ndarray) else v 
                               for k, v in model_results.items()},
            "fusion_strategy": self.fusion_strategy.value
        }
    
    def _get_target_models(self, model_names: List[str] = None) -> List[str]:
        """Get list of model keys to use for inference"""
        with self.lock:
            if model_names:
                target_models = []
                for key in self.loaded_models:
                    name = self.model_metadata[key]["name"]
                    if name in model_names:
                        target_models.append(key)
                return target_models
            else:
                return list(self.loaded_models.keys())
    
    def _predict_single_model(self, model_key: str, features: np.ndarray) -> Optional[np.ndarray]:
        """Run inference on a single model"""
        model = self.loaded_models[model_key]
        model_type = self.model_metadata[model_key]["type"]
        model_name = self.model_metadata[model_key]["name"]
        
        probs = None
        
        if model_type == "lightgbm":
            # Check if multiclass
            is_multiclass = False
            if hasattr(model, "params") and model.params.get("objective") == "multiclass":
                is_multiclass = True
            
            if hasattr(model, "predict_proba"):
                if is_multiclass:
                     probs = model.predict_proba(features)
                else:
                     probs = model.predict_proba(features)[:, 1]
            else:
                raw_pred = model.predict(features)
                # LightGBM predict returns raw probs for binary or array for multiclass
                probs = raw_pred
                
        elif model_type == "xgboost":
            # Check if multiclass via metadata or output shape
            if hasattr(model, "predict_proba"):
                try:
                    full_probs = model.predict_proba(features)
                    if full_probs.ndim > 1 and full_probs.shape[1] > 2:
                        probs = full_probs # Return all classes
                    else:
                        probs = full_probs[:, 1] # Binary
                except Exception:
                    import pandas as pd
                    if hasattr(model, 'feature_names_in_'):
                        feature_names = model.feature_names_in_
                        df = pd.DataFrame(features, columns=feature_names)
                        full_probs = model.predict_proba(df)
                        if full_probs.ndim > 1 and full_probs.shape[1] > 2:
                            probs = full_probs
                        else:
                            probs = full_probs[:, 1]
                    else:
                        dtest = xgb.DMatrix(features)
                        probs = model.predict(dtest)
            else:
                feature_names = getattr(model, 'feature_names', None)
                if feature_names:
                    dtest = xgb.DMatrix(features, feature_names=feature_names)
                else:
                    dtest = xgb.DMatrix(features)
                probs = model.predict(dtest)
                
        elif model_type in ["cnn", "gru", "transformer"]:
            # Deep learning model
            probs = self._predict_dl_model(model, model_name, features)
        
        return probs
    
    def _predict_dl_model(self, model, model_name: str, features: np.ndarray) -> np.ndarray:
        """Run inference on a deep learning model"""
        # Apply scaler if available
        if model_name in self.model_scalers:
            features = self.model_scalers[model_name].transform(features)
        
        # Predict
        predictions = model.predict(features, verbose=0)
        
        # Handle output shape
        if predictions.ndim > 1 and predictions.shape[1] > 1:
            # Multi-class: return full probability distribution
            return predictions
        else:
            # Binary: return 1D array
            return predictions.flatten()
    
    def _apply_fusion(self, model_results: Dict[str, np.ndarray], 
                     model_class_preds: Dict[str, np.ndarray],
                     features: np.ndarray) -> Tuple[List[int], List[float], List[str]]:
        """Apply fusion strategy to combine model predictions"""
        n_samples = len(features)
        if not model_results:
            return [0] * n_samples, [0.0] * n_samples, ["Normal"] * n_samples
        
        # Current simplified strategy: 
        # If we have multi-class results, prioritize them.
        # Otherwise fall back to standard fusion.
        
        # Check if we have any multi-class results
        multiclass_models = []
        for key, probs in model_results.items():
            if probs.ndim > 1 and probs.shape[1] > 1:
                multiclass_models.append(key)
        
        if multiclass_models:
            # Use the first multi-class model found (simple strategy for now)
            # In future: could average probabilities across multi-class models
            primary_key = multiclass_models[0]
            probs = model_results[primary_key]
            
            # Get class indices
            class_indices = np.argmax(probs, axis=1)
            confidences = np.max(probs, axis=1).tolist()
            
            # Get label mapping if available
            label_mapping = {}
            if "label_mapping" in self.model_metadata[primary_key]:
                label_mapping = self.model_metadata[primary_key]["label_mapping"]
                # Convert string keys to int if necessary
                label_mapping = {int(k): v for k, v in label_mapping.items()}
            
            attack_types = []
            predictions = []
            
            for idx in class_indices:
                label = label_mapping.get(idx, str(idx))
                attack_types.append(label)
                
                # Determine binary prediction (Normal/Benign = 0, others = 1)
                if label.lower() in ["benign", "normal", "0"]:
                    predictions.append(0)
                else:
                    predictions.append(1)
            
            return predictions, confidences, attack_types
            
        else:
            # Binary fusion logic
            if self.fusion_strategy == FusionStrategy.VOTING:
                preds, confs = self._fusion_voting(model_results, n_samples)
            elif self.fusion_strategy == FusionStrategy.WEIGHTED:
                preds, confs = self._fusion_weighted(model_results, n_samples)
            elif self.fusion_strategy == FusionStrategy.CASCADE:
                preds, confs = self._fusion_cascade(model_results, n_samples)
            else:
                preds, confs = self._fusion_weighted(model_results, n_samples)
            
            # Map binary predictions to attack types
            attack_types = []
            for p in preds:
                if p == 1:
                    attack_types.append("Malicious") # Generic label for binary models
                else:
                    attack_types.append("Normal")
                    
            return preds, confs, attack_types
    
    def _fusion_voting(self, model_results: Dict[str, np.ndarray], 
                      n_samples: int) -> Tuple[List[int], List[float]]:
        """Hard voting fusion"""
        votes = np.zeros(n_samples)
        
        for probs in model_results.values():
            votes += (probs > 0.5).astype(int)
        
        # Majority vote
        threshold = len(model_results) / 2
        predictions = (votes > threshold).astype(int).tolist()
        
        # Confidence = proportion of models agreeing
        confidences = (votes / len(model_results)).tolist()
        
        return predictions, confidences
    
    def _fusion_weighted(self, model_results: Dict[str, np.ndarray],
                        n_samples: int) -> Tuple[List[int], List[float]]:
        """Weighted average fusion"""
        aggregated_probs = np.zeros(n_samples)
        total_weight = 0.0
        
        for model_key, probs in model_results.items():
            model_name = self.model_metadata[model_key]["name"]
            weight = self.model_weights.get(model_name, 1.0)
            aggregated_probs += probs * weight
            total_weight += weight
        
        if total_weight > 0:
            aggregated_probs /= total_weight
        
        predictions = (aggregated_probs > 0.5).astype(int).tolist()
        confidences = aggregated_probs.tolist()
        
        return predictions, confidences
    
    def _fusion_cascade(self, model_results: Dict[str, np.ndarray],
                       n_samples: int) -> Tuple[List[int], List[float]]:
        """
        Cascade fusion: Use ML model first, then DL for uncertain cases.
        This reduces DL inference overhead for clear-cut cases.
        """
        # Separate ML and DL results
        ml_results = {}
        dl_results = {}
        
        for model_key, probs in model_results.items():
            if self.model_metadata[model_key].get("is_deep_learning"):
                dl_results[model_key] = probs
            else:
                ml_results[model_key] = probs
        
        # Start with ML predictions
        if ml_results:
            ml_probs = np.mean(list(ml_results.values()), axis=0)
        else:
            ml_probs = np.full(n_samples, 0.5)
        
        # Identify uncertain samples
        uncertain_mask = (ml_probs > (1 - self.cascade_threshold)) & (ml_probs < self.cascade_threshold)
        
        # Use DL for uncertain samples
        final_probs = ml_probs.copy()
        if dl_results and np.any(uncertain_mask):
            dl_probs = np.mean(list(dl_results.values()), axis=0)
            final_probs[uncertain_mask] = dl_probs[uncertain_mask]
        
        predictions = (final_probs > 0.5).astype(int).tolist()
        confidences = final_probs.tolist()
        
        return predictions, confidences
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded models"""
        with self.lock:
            return {
                "loaded_models": list(self.loaded_models.keys()),
                "model_details": self.model_metadata.copy(),
                "fusion_strategy": self.fusion_strategy.value,
                "model_weights": self.model_weights.copy()
            }
