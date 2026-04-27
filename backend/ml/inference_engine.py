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
    - Deep Learning: cnn, cnn_resattn, gru (TensorFlow/Keras)
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
            model_type: Type (lightgbm, xgboost, cnn, cnn_resattn, gru)
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
                elif model_type in ["cnn", "cnn_resattn", "gru", "transformer"]:
                    model, model_path = self._load_dl_model(model_name, model_type)
                elif model_type == "fusion":
                    return self._load_fusion_model(model_name, version)
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
                        "is_deep_learning": model_type in ["cnn", "cnn_resattn", "gru", "transformer"]
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
            # Try to load custom objects if they exist
            try:
                from ml.experiment_runner import focal_loss_fixed
                custom_objects = {'focal_loss_fixed': focal_loss_fixed}
            except ImportError:
                custom_objects = {}
                
            try:
                # Keras 3.x way
                model = tf.keras.models.load_model(model_path, custom_objects=custom_objects)
            except Exception as e1:
                logger.warning(f"Standard load failed, trying alternative: {e1}")
                # Sometimes saving as .keras with custom functions requires safe_mode=False
                model = tf.keras.models.load_model(model_path, custom_objects=custom_objects, safe_mode=False)
            
            # Load associated scaler if exists
            scaler_path = os.path.join(self.models_dir, f"{model_name}_scaler.joblib")
            if os.path.exists(scaler_path):
                self.model_scalers[model_name] = joblib.load(scaler_path)
                logger.info(f"Loaded scaler for {model_name}")
            
            return model, model_path
            
        except Exception as e:
            logger.error(f"Error loading DL model: {e}")
            return None, None

    def _load_fusion_model(self, model_name: str, version: str) -> bool:
        """Load a fusion model and its sub-models"""
        import joblib
        model_path = os.path.join(self.models_dir, f"{model_name}.joblib")
        if not os.path.exists(model_path):
            logger.error(f"Fusion model file not found: {model_path}")
            return False
            
        try:
            from ml.fusion_wrapper import FusionModelWrapper
            fusion_model = joblib.load(model_path)
            
            if not isinstance(fusion_model, FusionModelWrapper):
                logger.error("Loaded file is not a valid FusionModelWrapper")
                return False
                
            logger.info(f"Loaded fusion model {model_name} with {len(fusion_model.sub_models)} sub-models")
            
            # Extract base directory from model name to find sub-models
            # E.g. model_name="experiments/exp_123/fusion"
            base_dir = os.path.dirname(model_name)
            
            # Load all sub-models
            sub_model_keys = []
            all_loaded = True
            for sub_config in fusion_model.sub_models:
                sub_type = sub_config["type"]
                sub_name = sub_config["name"]
                
                # Construct the full path name relative to models_dir
                if base_dir:
                    full_sub_name = f"{base_dir}/{sub_name}"
                else:
                    # Look for sub models prefixed with the fusion model's name
                    # When promoted, sub-models might be renamed to fusion_name_sub_type
                    # We need a robust way to locate them.
                    # Since we promote them together, let's assume they are stored like:
                    # {model_name}_{sub_name} or {model_name}_{sub_type}
                    full_sub_name = f"{model_name}_{sub_type}"
                    # Fallback to just the type (if they were promoted identically)
                    if not any(os.path.exists(os.path.join(self.models_dir, f"{full_sub_name}{ext}")) 
                               for ext in [".joblib", ".keras", ".h5"]):
                        full_sub_name = sub_type
                        
                success = self.load_model(full_sub_name, sub_type, version)
                if success:
                    sub_model_keys.append(f"{full_sub_name}_{version}")
                else:
                    logger.error(f"Failed to load sub-model {full_sub_name} for fusion model {model_name}")
                    all_loaded = False
                    
            if not all_loaded:
                return False
                
            # Register the fusion meta-model
            model_key = f"{model_name}_{version}"
            self.loaded_models[model_key] = "FUSION_META_MODEL"
            self.model_metadata[model_key] = {
                "name": model_name,
                "type": "fusion",
                "version": version,
                "path": model_path,
                "is_deep_learning": False,
                "sub_model_keys": sub_model_keys,
                "fusion_strategy": fusion_model.fusion_strategy
            }
            
            # Apply the fusion strategy from the wrapper
            self.set_fusion_strategy(
                strategy=fusion_model.fusion_strategy,
                weights=fusion_model.weights
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading fusion model: {e}", exc_info=True)
            return False

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
                        # If it's a fusion model, return its sub_models instead
                        if self.model_metadata[key]["type"] == "fusion":
                            target_models.extend(self.model_metadata[key].get("sub_model_keys", []))
                        else:
                            target_models.append(key)
                # Remove duplicates in case multiple fusion models share sub-models
                return list(set(target_models))
            else:
                # If no names specified, return all non-fusion models
                return [k for k, v in self.model_metadata.items() if v["type"] != "fusion"]
    
    def _predict_single_model(self, model_key: str, features: np.ndarray) -> Optional[np.ndarray]:
        """Run inference on a single model"""
        model = self.loaded_models[model_key]
        model_type = self.model_metadata[model_key]["type"]
        model_name = self.model_metadata[model_key]["name"]
        
        probs = None
        
        if model_type == "lightgbm":
            if hasattr(model, "predict_proba"):
                full_probs = model.predict_proba(features)
                if full_probs.ndim > 1 and full_probs.shape[1] > 2:
                    probs = full_probs  # Return all classes for multiclass
                else:
                    probs = full_probs[:, 1]  # Binary, return attack class probability
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
                
        elif model_type in ["cnn", "cnn_resattn", "gru", "transformer"]:
            # Deep learning model
            probs = self._predict_dl_model(model, model_name, features)
        
        return probs
    
    def _predict_dl_model(self, model, model_name: str, features: np.ndarray) -> np.ndarray:
        """Run inference on a deep learning model"""
        # Apply scaler if available
        if model_name in self.model_scalers:
            logger.debug(f"Applying scaler for DL model {model_name}")
            features = self.model_scalers[model_name].transform(features)
        else:
            logger.warning(f"No scaler found for DL model {model_name}! This may cause incorrect predictions.")
        
        # Predict
        predictions = model.predict(features, verbose=0)
        
        # Log prediction info for debugging
        logger.debug(f"DL model {model_name} predictions shape: {predictions.shape}")
        if predictions.size > 0:
            # Log min/max/mean of predictions to detect issues
            if predictions.ndim > 1:
                for i in range(min(5, predictions.shape[1])):
                    logger.debug(f"  Class {i} probs: min={predictions[:, i].min():.4f}, max={predictions[:, i].max():.4f}, mean={predictions[:, i].mean():.4f}")
            else:
                logger.debug(f"  Binary probs: min={predictions.min():.4f}, max={predictions.max():.4f}, mean={predictions.mean():.4f}")
        
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
        
        # NOTE: Experiment module only produces binary models. 
        # Multi-class fusion is not fully supported yet. 
        # Removed the buggy short-circuit that overrides the fusion strategy
        # if a multi-class model is found. All fusion now strictly follows the strategy.

        predictions = []
        confidences = []
        
        # Extract binary probabilities from all models
        # For multiclass models, compute attack probability by excluding the Normal class
        binary_probs = {}
        for key, probs in model_results.items():
            if probs.ndim > 1 and probs.shape[1] > 1:
                # Multiclass model: find Normal class index and compute attack probability
                meta = self.model_metadata.get(key, {})
                label_mapping = meta.get("label_mapping", {})
                
                normal_idx = None
                for idx_str, label in label_mapping.items():
                    if label.lower() in ["normal", "benign"]:
                        normal_idx = int(idx_str)
                        break
                
                if normal_idx is not None:
                    # Attack probability = 1 - probability of Normal class
                    binary_probs[key] = 1.0 - probs[:, normal_idx]
                else:
                    # Fallback: assume first class is Normal
                    binary_probs[key] = 1.0 - probs[:, 0]
            else:
                binary_probs[key] = probs.flatten()
                
        if self.fusion_strategy == FusionStrategy.VOTING:
            predictions, confidences = self._fusion_voting(binary_probs, n_samples)
        elif self.fusion_strategy == FusionStrategy.WEIGHTED:
            predictions, confidences = self._fusion_weighted(binary_probs, n_samples)
        elif self.fusion_strategy == FusionStrategy.CASCADE:
            predictions, confidences = self._fusion_cascade(binary_probs, n_samples)
        elif self.fusion_strategy == FusionStrategy.STACKING:
            # Fallback to weighted if stacking model not loaded
            predictions, confidences = self._fusion_weighted(binary_probs, n_samples)
        else:
            predictions, confidences = self._fusion_voting(binary_probs, n_samples)
            
        # Determine attack types
        attack_types = []
        
        # Check if we are running inference with only one model
        # If there's only one model and it's multiclass, we should preserve its attack types
        # instead of treating it as a fusion of generic attacks.
        if len(model_results) == 1:
            key = list(model_results.keys())[0]
            if model_results[key].ndim > 1 and model_results[key].shape[1] > 2:
                meta = self.model_metadata.get(key, {})
                label_mapping = meta.get("label_mapping", {})
                
                # Find Normal class index for consistency
                normal_idx = None
                for idx_str, label in label_mapping.items():
                    if label.lower() in ["normal", "benign"]:
                        normal_idx = int(idx_str)
                        break
                
                for i in range(n_samples):
                    probs = model_results[key][i]
                    
                    if predictions[i] == 1:
                        # Binary says attack: pick the highest-probability attack class
                        if normal_idx is not None:
                            attack_probs = probs.copy()
                            attack_probs[normal_idx] = -1  # Exclude Normal
                            attack_idx = int(np.argmax(attack_probs))
                        else:
                            attack_idx = int(np.argmax(probs))
                        
                        str_idx = str(attack_idx)
                        label = label_mapping.get(str_idx, label_mapping.get(attack_idx, str_idx))
                        attack_types.append(label)
                    else:
                        attack_types.append("Normal")
                
                return predictions, confidences, attack_types

        # For actual fusion or binary models, fallback to generic types
        for i in range(n_samples):
            if predictions[i] == 1:
                attack_types.append("Generic Attack (Fusion)")
            else:
                attack_types.append("Normal")
                
        return predictions, confidences, attack_types
    
    def _fusion_voting(self, binary_probs: Dict[str, np.ndarray], 
                      n_samples: int) -> Tuple[List[int], List[float]]:
        """Hard voting fusion"""
        votes = np.zeros(n_samples)
        
        for probs in binary_probs.values():
            votes += (probs > 0.5).astype(int)
        
        # Majority vote
        threshold = len(binary_probs) / 2
        predictions = (votes > threshold).astype(int).tolist()
        
        # Confidence = proportion of models agreeing
        confidences = (votes / len(binary_probs)).tolist()
        
        return predictions, confidences

    def _fusion_weighted(self, binary_probs: Dict[str, np.ndarray], 
                        n_samples: int) -> Tuple[List[int], List[float]]:
        """Weighted average fusion (Dynamic Soft Voting)"""
        weighted_probs = np.zeros(n_samples)
        total_weight = 0.0
        
        for key, probs in binary_probs.items():
            weight = self.model_weights.get(key, 1.0)
            weighted_probs += probs * weight
            total_weight += weight
            
        if total_weight > 0:
            weighted_probs /= total_weight
            
        predictions = (weighted_probs > 0.5).astype(int).tolist()
        confidences = weighted_probs.tolist()
        
        return predictions, confidences

    def _fusion_cascade(self, binary_probs: Dict[str, np.ndarray], 
                       n_samples: int) -> Tuple[List[int], List[float]]:
        """Cascade fusion: ML first, then DL if uncertain"""
        # Categorize models
        ml_keys = [k for k in binary_probs.keys() if "lightgbm" in k.lower() or "xgboost" in k.lower()]
        dl_keys = [k for k in binary_probs.keys() if k not in ml_keys]
        
        # Fallback to weighted if separation fails
        if not ml_keys or not dl_keys:
            return self._fusion_weighted(binary_probs, n_samples)
            
        predictions = []
        confidences = []
        
        # Average ML probabilities
        ml_probs = np.zeros(n_samples)
        for k in ml_keys:
            ml_probs += binary_probs[k]
        ml_probs /= len(ml_keys)
        
        # Average DL probabilities
        dl_probs = np.zeros(n_samples)
        for k in dl_keys:
            dl_probs += binary_probs[k]
        dl_probs /= len(dl_keys)
        
        for i in range(n_samples):
            ml_prob = ml_probs[i]
            
            # If ML is very confident (either very low or very high probability)
            if ml_prob < (1 - self.cascade_threshold) or ml_prob > self.cascade_threshold:
                predictions.append(1 if ml_prob > 0.5 else 0)
                confidences.append(float(ml_prob))
            else:
                # ML is uncertain, defer to DL
                dl_prob = dl_probs[i]
                predictions.append(1 if dl_prob > 0.5 else 0)
                confidences.append(float(dl_prob))
                
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
