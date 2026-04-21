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
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
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
            
    def load_single_dataset(self, dataset_path: str) -> pd.DataFrame:
        """Load a single dataset file"""
        logger.info(f"Loading dataset from {dataset_path}...")
        
        file_ext = os.path.splitext(dataset_path)[1].lower()
        
        if file_ext == '.csv':
            df = pd.read_csv(dataset_path)
        elif file_ext == '.txt':
            if 'NSL-KDD' in dataset_path or 'KDD' in dataset_path:
                nsl_kdd_columns = [
                    'duration', 'protocol_type', 'service', 'flag', 'src_bytes', 'dst_bytes',
                    'land', 'wrong_fragment', 'urgent', 'hot', 'num_failed_logins',
                    'logged_in', 'num_compromised', 'root_shell', 'su_attempted',
                    'num_root', 'num_file_creations', 'num_shells', 'num_access_files',
                    'num_outbound_cmds', 'is_host_login', 'is_guest_login', 'count',
                    'srv_count', 'serror_rate', 'srv_serror_rate', 'rerror_rate',
                    'srv_rerror_rate', 'same_srv_rate', 'diff_srv_rate', 'srv_diff_host_rate',
                    'dst_host_count', 'dst_host_srv_count', 'dst_host_same_srv_rate',
                    'dst_host_diff_srv_rate', 'dst_host_same_src_port_rate',
                    'dst_host_srv_diff_host_rate', 'dst_host_serror_rate',
                    'dst_host_srv_serror_rate', 'dst_host_rerror_rate',
                    'dst_host_srv_rerror_rate', 'label', 'difficulty_level'
                ]
                df = pd.read_csv(dataset_path, names=nsl_kdd_columns)
            else:
                df = pd.read_csv(dataset_path)
        elif file_ext == '.arff':
            df = pd.read_csv(dataset_path, comment='@', header=None)
        else:
            df = pd.read_csv(dataset_path)
        
        return df
    
    def load_dataset(self, dataset_path_or_paths: str or List[str]) -> Tuple[pd.DataFrame, pd.Series, Dict[int, str]]:
        """
        Load dataset(s) from CSV, TXT, or ARFF
        Can load single or multiple datasets
        
        Returns:
            X (features), y (labels), label_mapping (dict)
        """
        try:
            dfs = []
            
            if isinstance(dataset_path_or_paths, str):
                dataset_path_or_paths = [dataset_path_or_paths]
            
            for dataset_path in dataset_path_or_paths:
                df = self.load_single_dataset(dataset_path)
                dfs.append(df)
            
            # Merge all dataframes
            if len(dfs) == 1:
                df = dfs[0]
            else:
                # Check if all datasets have the same columns
                reference_columns = set(dfs[0].columns)
                for i, df in enumerate(dfs[1:], 2):
                    if set(df.columns) != reference_columns:
                        raise ValueError(
                            f"Dataset {i} has different columns than the first dataset. "
                            f"All datasets must have the same schema for merging."
                        )
                
                df = pd.concat(dfs, ignore_index=True)
                logger.info(f"Merged {len(dfs)} datasets, total {len(df)} samples")
            
            # Simple preprocessing for prototype
            # Drop non-numeric for now except encoded ones
            # Assume label is 'label' or 'class'
            target_col = None
            
            # For NSL-KDD, specifically look for 'label' column and drop 'difficulty_level'
            first_path = dataset_path_or_paths[0] if isinstance(dataset_path_or_paths, list) else dataset_path_or_paths
            if 'NSL-KDD' in first_path or 'KDD' in first_path:
                if 'difficulty_level' in df.columns:
                    df = df.drop(columns=['difficulty_level'])
            
            for col in ['label', 'class', 'Label', 'Class', 'attack_cat']:
                if col in df.columns:
                    target_col = col
                    break
            
            if target_col is None:
                # Assume last column
                target_col = df.columns[-1]
                
            X = df.drop(columns=[target_col])
            y = df[target_col]
            
            # Note: 'Destination Port' is NO LONGER dropped. We keep all 78 features.
            drop_cols = [
                'Source IP', 'Source Port', 'Destination IP',
                'Flow ID', 'Timestamp', 'Unnamed: 0', 'Fwd Header Length.1'
            ]
            for col in drop_cols:
                if col in X.columns:
                    X = X.drop(columns=[col])
                    logger.info(f"Dropped strong identifier feature: {col}")
            
            # Handle Label Encoding
            label_mapping = {}
            if y.dtype == 'object' or not pd.api.types.is_numeric_dtype(y):
                le = LabelEncoder()
                y = le.fit_transform(y)
                # Create mapping: index -> label name
                label_mapping = {int(i): str(label) for i, label in enumerate(le.classes_)}
            else:
                # If already numeric, assume 0=Normal, 1=Attack if binary, or keep as is
                # Just create a dummy mapping based on unique values
                unique_vals = sorted(np.unique(y))
                for val in unique_vals:
                    label_mapping[int(val)] = str(val)
            
            # Basic encoding for string columns if any (simple label encoding)
            for col in X.select_dtypes(include=['object']).columns:
                le = LabelEncoder()
                X[col] = le.fit_transform(X[col].astype(str))
                
            # Handle missing and infinite values
            X = X.fillna(0)
            X = X.replace([np.inf, -np.inf], 0)
                 
            return X, pd.Series(y), label_mapping
        except Exception as e:
            logger.error(f"Error loading dataset: {e}")
            raise e

    def train_model(self, 
                   model_type: str, 
                   dataset_path_or_paths: str or List[str], 
                   params: Dict[str, Any] = None,
                   model_name: str = "new_model",
                   task_id: str = None,
                   epochs: int = None) -> Dict[str, Any]:
        """
        Train a new model.
        
        Args:
            model_type: 'lightgbm', 'xgboost', 'cnn', 'cnn_resattn', 'gru', or 'transformer'
            dataset_path: Path to CSV data
            params: Hyperparameters
            model_name: Name for saving
            task_id: Optional task ID for progress tracking
            
        Returns:
            Dictionary with training metrics
        """
        # Route to appropriate trainer
        if model_type in ["cnn", "cnn_resattn", "gru", "transformer"]:
            return self._train_deep_learning_model(
                model_type, dataset_path_or_paths, params, model_name, task_id, epochs
            )
        else:
            return self._train_ml_model(
                model_type, dataset_path_or_paths, params, model_name, task_id
            )
    
    def _train_deep_learning_model(self,
                                   model_type: str,
                                   dataset_path_or_paths: str or List[str],
                                   params: Dict[str, Any] = None,
                                   model_name: str = "dl_model",
                                   task_id: str = None,
                                   epochs: int = None) -> Dict[str, Any]:
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
            if "use_smote" in params:
                config.use_smote = params["use_smote"]
        
        trainer = DeepLearningTrainer(self.models_dir, self.data_dir)
        return trainer.train_model(
            model_type=model_type,
            dataset_path=dataset_path_or_paths,
            config=config,
            model_name=model_name,
            task_id=task_id
        )
    
    def _train_ml_model(self, 
                       model_type: str, 
                       dataset_path_or_paths: str or List[str], 
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
        X, y, label_mapping = self.load_dataset(dataset_path_or_paths)
        update_progress("loading", 10, 100, f"Dataset loaded: {len(X)} samples")
        
        # Determine num_classes
        num_classes = len(np.unique(y))
        logger.info(f"Detected {num_classes} classes: {label_mapping}")
        
        # Stage 2: Split Data (15%)
        update_progress("preprocessing", 10, 100, "Splitting data...")
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # FEATURE ENGINEERING: SMOTE for class imbalance
        if params and params.get('use_smote', False):
            update_progress("preprocessing", 12, 100, "Applying SMOTE for class imbalance...")
            try:
                from imblearn.over_sampling import SMOTE
                logger.info(f"Original class distribution: {np.bincount(y_train)}")
                smote = SMOTE(random_state=42, n_jobs=-1)
                X_train, y_train = smote.fit_resample(X_train, y_train)
                logger.info(f"Resampled class distribution: {np.bincount(y_train)}")
            except ImportError:
                logger.warning("imbalanced-learn not installed. Skipping SMOTE.")
            except Exception as e:
                logger.warning(f"SMOTE failed: {e}. Proceeding with original data.")
                
        update_progress("preprocessing", 15, 100, f"Train: {len(X_train)}, Test: {len(X_test)}")
        
        model = None
        
        try:
            if model_type == "lightgbm":
                if params is None:
                    params = {}
                
                # Ensure correct objective and num_class
                if num_classes > 2:
                    params['objective'] = 'multiclass'
                    params['num_class'] = num_classes
                    if 'metric' not in params:
                        params['metric'] = 'multi_logloss'
                else:
                    if params.get('objective') != 'binary':
                        params['objective'] = 'binary'
                    if 'metric' not in params:
                        params['metric'] = 'binary_logloss'
                
                params['verbosity'] = -1
                
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
                if num_classes > 2:
                    y_pred = np.argmax(y_pred_prob, axis=1)
                else:
                    y_pred = (y_pred_prob > 0.5).astype(int)
                
            elif model_type == "xgboost":
                if params is None:
                    params = {}
                
                # Ensure correct objective and num_class
                if num_classes > 2:
                    params['objective'] = 'multi:softmax'
                    params['num_class'] = num_classes
                    if 'eval_metric' not in params:
                        params['eval_metric'] = 'mlogloss'
                else:
                    if params.get('objective') != 'binary:logistic':
                        params['objective'] = 'binary:logistic'
                    if 'eval_metric' not in params:
                        params['eval_metric'] = 'logloss'
                
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
                if num_classes > 2:
                    # XGBoost multi:softmax returns class indices directly
                    if params['objective'] == 'multi:softmax':
                        y_pred = y_pred_prob.astype(int)
                    else:
                        # if multi:softprob
                        y_pred = np.argmax(y_pred_prob, axis=1)
                else:
                    y_pred = (y_pred_prob > 0.5).astype(int)
                
            else:
                raise ValueError(f"Unsupported ML model type: {model_type}")
                
            # Calculate Metrics (90%)
            update_progress("evaluating", 90, 100, "Calculating metrics...")
            
            avg_method = 'binary' if num_classes == 2 else 'weighted'
            metrics = {
                "accuracy": float(accuracy_score(y_test, y_pred)),
                "precision": float(precision_score(y_test, y_pred, average=avg_method, zero_division=0)),
                "recall": float(recall_score(y_test, y_pred, average=avg_method, zero_division=0)),
                "f1": float(f1_score(y_test, y_pred, average=avg_method, zero_division=0)),
                "training_time": time.time() - start_time
            }
            
            # Calculate FPR and FNR for binary classification
            if num_classes == 2:
                cm = confusion_matrix(y_test, y_pred)
                if cm.size == 4:
                    tn, fp, fn, tp = cm.ravel()
                    metrics["fpr"] = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
                    metrics["fnr"] = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0
                else:
                    metrics["fpr"] = 0.0
                    metrics["fnr"] = 0.0
            else:
                metrics["fpr"] = 0.0
                metrics["fnr"] = 0.0
            
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
                    "timestamp": time.time(),
                    "label_mapping": label_mapping,
                    "num_classes": num_classes
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
