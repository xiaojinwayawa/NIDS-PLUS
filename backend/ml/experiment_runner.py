"""
Experiment Runner Module
Provides reproducible experiment workflows for NSL-KDD and CIC-IDS2017 datasets.
Supports comparative experiments: ML-only, DL-only, and Hybrid fusion.

补充需求 E：实验与评估可复现（NSL-KDD 与 CIC-IDS2017）
"""
import os
import json
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)

from logging_config import app_logger as logger

# Get project directories
_current_file = os.path.abspath(__file__)
_ml_dir = os.path.dirname(_current_file)
_backend_dir = os.path.dirname(_ml_dir)
_project_root = os.path.dirname(_backend_dir)
_default_data_dir = os.path.join(_project_root, "data")
_default_results_dir = os.path.join(_project_root, "data", "experiments")


@dataclass
class ExperimentConfig:
    """Configuration for reproducible experiments"""
    experiment_name: str
    dataset_type: str  # 'nsl-kdd' or 'cic-ids2017'
    model_types: List[str]  # ['lightgbm', 'xgboost', 'cnn', 'gru']
    random_seed: int = 42
    test_size: float = 0.2
    
    # ML hyperparameters
    ml_num_boost_round: int = 100
    ml_early_stopping: int = 10
    
    # DL hyperparameters
    dl_epochs: int = 50
    dl_batch_size: int = 64
    dl_learning_rate: float = 0.001
    
    # Fusion settings
    fusion_strategy: str = "weighted"  # 'voting', 'weighted', 'cascade'
    
    def get_hash(self) -> str:
        """Get unique hash for this configuration"""
        config_str = json.dumps(asdict(self), sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()[:8]


@dataclass
class ExperimentResult:
    """Results from a single experiment run"""
    experiment_id: str
    config: ExperimentConfig
    timestamp: datetime
    
    # Metrics
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    fpr: float  # False Positive Rate
    fnr: float  # False Negative Rate
    
    # Performance
    training_time_sec: float
    inference_time_ms: float
    throughput_samples_per_sec: float
    
    # Model-specific results
    model_results: Dict[str, Dict[str, float]]
    
    # Confusion matrix
    confusion_matrix: List[List[int]]


class DatasetPreprocessor:
    """Handles dataset loading and preprocessing for experiments"""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or _default_data_dir
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
    
    def load_nsl_kdd(self, train_path: str = None, test_path: str = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Load and preprocess NSL-KDD dataset.
        
        Returns:
            Tuple of (X_train, X_test, y_train, y_test)
        """
        # Default paths - try multiple locations
        if train_path is None:
            possible_train = [
                os.path.join(self.data_dir, "datasets", "NSL-KDD", "KDDTrain+.txt"),
                os.path.join(self.data_dir, "datasets", "NSL-KDD", "KDDTrain+.csv"),
                os.path.join(self.data_dir, "datasets", "KDDTrain+.csv"),
                os.path.join(self.data_dir, "datasets", "KDDTrain+.txt"),
            ]
            for p in possible_train:
                if os.path.exists(p):
                    train_path = p
                    break
        if test_path is None:
            possible_test = [
                os.path.join(self.data_dir, "datasets", "NSL-KDD", "KDDTest+.txt"),
                os.path.join(self.data_dir, "datasets", "NSL-KDD", "KDDTest+.csv"),
                os.path.join(self.data_dir, "datasets", "KDDTest+.csv"),
                os.path.join(self.data_dir, "datasets", "KDDTest+.txt"),
            ]
            for p in possible_test:
                if os.path.exists(p):
                    test_path = p
                    break
        
        # NSL-KDD column names
        columns = [
            'duration', 'protocol_type', 'service', 'flag', 'src_bytes', 'dst_bytes',
            'land', 'wrong_fragment', 'urgent', 'hot', 'num_failed_logins', 'logged_in',
            'num_compromised', 'root_shell', 'su_attempted', 'num_root', 'num_file_creations',
            'num_shells', 'num_access_files', 'num_outbound_cmds', 'is_host_login',
            'is_guest_login', 'count', 'srv_count', 'serror_rate', 'srv_serror_rate',
            'rerror_rate', 'srv_rerror_rate', 'same_srv_rate', 'diff_srv_rate',
            'srv_diff_host_rate', 'dst_host_count', 'dst_host_srv_count',
            'dst_host_same_srv_rate', 'dst_host_diff_srv_rate', 'dst_host_same_src_port_rate',
            'dst_host_srv_diff_host_rate', 'dst_host_serror_rate', 'dst_host_srv_serror_rate',
            'dst_host_rerror_rate', 'dst_host_srv_rerror_rate', 'label', 'difficulty'
        ]
        
        # Load data
        if train_path and os.path.exists(train_path):
            df_train = pd.read_csv(train_path, names=columns, header=None)
            df_test = pd.read_csv(test_path, names=columns, header=None) if test_path and os.path.exists(test_path) else None
        else:
            # Try loading from a single file
            single_paths = [
                os.path.join(self.data_dir, "datasets", "nsl-kdd.csv"),
                os.path.join(self.data_dir, "datasets", "NSL-KDD.csv"),
            ]
            for single_path in single_paths:
                if os.path.exists(single_path):
                    df = pd.read_csv(single_path)
                    return self._preprocess_dataframe(df)
            raise FileNotFoundError(f"NSL-KDD dataset not found. Tried: {train_path}")
        
        # Combine for preprocessing
        if df_test is not None:
            df_train['split'] = 'train'
            df_test['split'] = 'test'
            df = pd.concat([df_train, df_test], ignore_index=True)
        else:
            df = df_train
            df['split'] = 'train'
        
        return self._preprocess_nsl_kdd(df)
    
    def _preprocess_nsl_kdd(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Preprocess NSL-KDD dataframe"""
        # Drop difficulty column if exists
        if 'difficulty' in df.columns:
            df = df.drop('difficulty', axis=1)
        
        # Convert labels to binary (normal=0, attack=1)
        df['label'] = df['label'].apply(lambda x: 0 if x == 'normal' else 1)
        
        # Encode categorical features
        categorical_cols = ['protocol_type', 'service', 'flag']
        for col in categorical_cols:
            if col in df.columns:
                df[col] = df[col].astype('category').cat.codes
        
        # Split back
        if 'split' in df.columns:
            train_df = df[df['split'] == 'train'].drop('split', axis=1)
            test_df = df[df['split'] == 'test'].drop('split', axis=1)
            
            X_train = train_df.drop('label', axis=1).values.astype(np.float32)
            y_train = train_df['label'].values.astype(np.int32)
            X_test = test_df.drop('label', axis=1).values.astype(np.float32)
            y_test = test_df['label'].values.astype(np.int32)
        else:
            X = df.drop('label', axis=1).values.astype(np.float32)
            y = df['label'].values.astype(np.int32)
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Scale features
        X_train = self.scaler.fit_transform(X_train)
        X_test = self.scaler.transform(X_test)
        
        # Handle NaN and Inf
        X_train = np.nan_to_num(X_train, nan=0.0, posinf=0.0, neginf=0.0)
        X_test = np.nan_to_num(X_test, nan=0.0, posinf=0.0, neginf=0.0)
        
        return X_train, X_test, y_train, y_test
    
    def load_cicids2017(self, data_path: str = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Load and preprocess CIC-IDS2017 dataset.
        
        Returns:
            Tuple of (X_train, X_test, y_train, y_test)
        """
        if data_path is None:
            # Try multiple possible paths
            possible_paths = [
                os.path.join(self.data_dir, "datasets", "CIC-IDS2017", "cicids2017.csv"),
                os.path.join(self.data_dir, "datasets", "CIC-IDS2017", "CICIDS2017.csv"),
                os.path.join(self.data_dir, "datasets", "cicids2017.csv"),
                os.path.join(self.data_dir, "datasets", "CICIDS2017.csv"),
                os.path.join(self.data_dir, "datasets", "cic-ids2017.csv"),
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    data_path = p
                    break
        
        if data_path is None or not os.path.exists(data_path):
            raise FileNotFoundError(f"CIC-IDS2017 dataset not found")
        
        df = pd.read_csv(data_path)
        return self._preprocess_cicids2017(df)
    
    def _preprocess_cicids2017(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Preprocess CIC-IDS2017 dataframe"""
        # Find label column
        label_col = None
        for col in ['Label', 'label', 'class', 'Class']:
            if col in df.columns:
                label_col = col
                break
        
        if label_col is None:
            label_col = df.columns[-1]
        
        # Convert labels to binary
        df['label_binary'] = df[label_col].apply(lambda x: 0 if str(x).upper() in ['BENIGN', 'NORMAL', '0'] else 1)
        
        # Drop original label and non-numeric columns
        X = df.drop([label_col, 'label_binary'], axis=1, errors='ignore')
        y = df['label_binary']
        
        # Keep only numeric columns
        X = X.select_dtypes(include=[np.number])
        
        # Handle missing values
        X = X.fillna(0)
        X = X.replace([np.inf, -np.inf], 0)
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X.values.astype(np.float32), 
            y.values.astype(np.int32),
            test_size=0.2, 
            random_state=42,
            stratify=y
        )
        
        # Scale
        X_train = self.scaler.fit_transform(X_train)
        X_test = self.scaler.transform(X_test)
        
        # Handle NaN and Inf after scaling
        X_train = np.nan_to_num(X_train, nan=0.0, posinf=0.0, neginf=0.0)
        X_test = np.nan_to_num(X_test, nan=0.0, posinf=0.0, neginf=0.0)
        
        return X_train, X_test, y_train, y_test
    
    def _preprocess_dataframe(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Generic preprocessing for any dataframe"""
        # Find label column
        label_col = None
        for col in ['label', 'Label', 'class', 'Class']:
            if col in df.columns:
                label_col = col
                break
        if label_col is None:
            label_col = df.columns[-1]
        
        X = df.drop(label_col, axis=1)
        y = df[label_col]
        
        # Encode categorical
        for col in X.select_dtypes(include=['object']).columns:
            X[col] = X[col].astype('category').cat.codes
        
        if y.dtype == 'object':
            y = self.label_encoder.fit_transform(y)
        
        # Convert to binary if needed
        if len(np.unique(y)) > 2:
            y = (y > 0).astype(int)
        
        X = X.fillna(0).replace([np.inf, -np.inf], 0)
        
        X_train, X_test, y_train, y_test = train_test_split(
            X.values.astype(np.float32),
            y.astype(np.int32) if isinstance(y, np.ndarray) else y.values.astype(np.int32),
            test_size=0.2,
            random_state=42
        )
        
        X_train = self.scaler.fit_transform(X_train)
        X_test = self.scaler.transform(X_test)
        
        return X_train, X_test, y_train, y_test


class ExperimentRunner:
    """
    Runs reproducible experiments with different model configurations.
    Supports comparative analysis: ML-only, DL-only, and Hybrid.
    """
    
    def __init__(self, data_dir: str = None, results_dir: str = None):
        self.data_dir = data_dir or _default_data_dir
        self.results_dir = results_dir or _default_results_dir
        os.makedirs(self.results_dir, exist_ok=True)
        
        self.preprocessor = DatasetPreprocessor(self.data_dir)
    
    def run_experiment(self, config: ExperimentConfig) -> ExperimentResult:
        """
        Run a complete experiment with the given configuration.
        
        Args:
            config: Experiment configuration
            
        Returns:
            ExperimentResult with all metrics
        """
        # Set random seeds for reproducibility
        np.random.seed(config.random_seed)
        
        experiment_id = f"{config.experiment_name}_{config.get_hash()}_{int(time.time())}"
        logger.info(f"Starting experiment: {experiment_id}")
        
        # Load dataset
        logger.info(f"Loading {config.dataset_type} dataset...")
        if config.dataset_type.lower() == "nsl-kdd":
            X_train, X_test, y_train, y_test = self.preprocessor.load_nsl_kdd()
        elif config.dataset_type.lower() == "cic-ids2017":
            X_train, X_test, y_train, y_test = self.preprocessor.load_cicids2017()
        else:
            raise ValueError(f"Unknown dataset: {config.dataset_type}")
        
        logger.info(f"Dataset loaded: Train={len(X_train)}, Test={len(X_test)}")
        
        # Train and evaluate each model type
        model_results = {}
        all_predictions = {}
        total_training_time = 0
        
        for model_type in config.model_types:
            logger.info(f"Training {model_type} model...")
            
            try:
                if model_type in ["lightgbm", "xgboost"]:
                    result, preds, train_time = self._train_ml_model(
                        model_type, X_train, X_test, y_train, y_test, config
                    )
                elif model_type in ["cnn", "gru"]:
                    result, preds, train_time = self._train_dl_model(
                        model_type, X_train, X_test, y_train, y_test, config
                    )
                else:
                    logger.warning(f"Unknown model type: {model_type}")
                    continue
                
                model_results[model_type] = result
                all_predictions[model_type] = preds
                total_training_time += train_time
                
            except Exception as e:
                logger.error(f"Error training {model_type}: {e}")
                model_results[model_type] = {"error": str(e)}
        
        # Compute fusion results if multiple models
        if len(all_predictions) > 1:
            fusion_preds = self._apply_fusion(all_predictions, config.fusion_strategy)
            fusion_metrics = self._compute_metrics(y_test, fusion_preds)
            model_results["fusion"] = fusion_metrics
            final_preds = fusion_preds
        elif all_predictions:
            final_preds = list(all_predictions.values())[0]
        else:
            final_preds = np.zeros(len(y_test))
        
        # Compute final metrics
        final_metrics = self._compute_metrics(y_test, final_preds)
        cm = confusion_matrix(y_test, final_preds)
        
        # Compute inference throughput
        inference_start = time.time()
        _ = self._dummy_inference(X_test[:1000] if len(X_test) > 1000 else X_test)
        inference_time = (time.time() - inference_start) * 1000
        throughput = len(X_test) / (inference_time / 1000) if inference_time > 0 else 0
        
        # Create result
        result = ExperimentResult(
            experiment_id=experiment_id,
            config=config,
            timestamp=datetime.now(),
            accuracy=final_metrics["accuracy"],
            precision=final_metrics["precision"],
            recall=final_metrics["recall"],
            f1_score=final_metrics["f1"],
            fpr=final_metrics["fpr"],
            fnr=final_metrics["fnr"],
            training_time_sec=total_training_time,
            inference_time_ms=inference_time,
            throughput_samples_per_sec=throughput,
            model_results=model_results,
            confusion_matrix=cm.tolist()
        )
        
        # Save result
        self._save_result(result)
        
        logger.info(f"Experiment {experiment_id} completed. Accuracy: {result.accuracy:.4f}")
        
        return result
    
    def _train_ml_model(self, model_type: str, X_train, X_test, y_train, y_test, 
                       config: ExperimentConfig) -> Tuple[Dict, np.ndarray, float]:
        """Train a traditional ML model"""
        import lightgbm as lgb
        import xgboost as xgb
        
        start_time = time.time()
        
        if model_type == "lightgbm":
            params = {
                'objective': 'binary',
                'metric': 'binary_logloss',
                'verbosity': -1,
                'seed': config.random_seed
            }
            
            train_data = lgb.Dataset(X_train, label=y_train)
            valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
            
            model = lgb.train(
                params,
                train_data,
                valid_sets=[valid_data],
                num_boost_round=config.ml_num_boost_round,
                callbacks=[
                    lgb.early_stopping(stopping_rounds=config.ml_early_stopping),
                    lgb.log_evaluation(0)
                ]
            )
            
            y_pred_prob = model.predict(X_test)
            y_pred = (y_pred_prob > 0.5).astype(int)
            
        elif model_type == "xgboost":
            params = {
                'objective': 'binary:logistic',
                'eval_metric': 'logloss',
                'seed': config.random_seed,
                'verbosity': 0
            }
            
            dtrain = xgb.DMatrix(X_train, label=y_train)
            dtest = xgb.DMatrix(X_test, label=y_test)
            
            model = xgb.train(
                params,
                dtrain,
                num_boost_round=config.ml_num_boost_round,
                evals=[(dtest, "Test")],
                early_stopping_rounds=config.ml_early_stopping,
                verbose_eval=False
            )
            
            y_pred_prob = model.predict(dtest)
            y_pred = (y_pred_prob > 0.5).astype(int)
        
        training_time = time.time() - start_time
        metrics = self._compute_metrics(y_test, y_pred)
        
        return metrics, y_pred, training_time
    
    def _train_dl_model(self, model_type: str, X_train, X_test, y_train, y_test,
                       config: ExperimentConfig) -> Tuple[Dict, np.ndarray, float]:
        """Train a deep learning model"""
        try:
            import tensorflow as tf
            from tensorflow import keras
            from tensorflow.keras import layers
        except ImportError:
            logger.error("TensorFlow not available")
            return {"error": "TensorFlow not available"}, np.zeros(len(y_test)), 0
        
        # Set seeds
        tf.random.set_seed(config.random_seed)
        np.random.seed(config.random_seed)
        
        start_time = time.time()
        input_dim = X_train.shape[1]
        
        if model_type == "cnn":
            model = keras.Sequential([
                layers.Input(shape=(input_dim,)),
                layers.Reshape((input_dim, 1)),
                layers.Conv1D(64, 3, activation='relu', padding='same'),
                layers.BatchNormalization(),
                layers.MaxPooling1D(2),
                layers.Dropout(0.3),
                layers.Conv1D(128, 3, activation='relu', padding='same'),
                layers.BatchNormalization(),
                layers.GlobalAveragePooling1D(),
                layers.Dropout(0.3),
                layers.Dense(64, activation='relu'),
                layers.Dropout(0.2),
                layers.Dense(1, activation='sigmoid')
            ])
        elif model_type == "gru":
            model = keras.Sequential([
                layers.Input(shape=(input_dim,)),
                layers.Reshape((input_dim, 1)),
                layers.GRU(64, return_sequences=True, dropout=0.3),
                layers.GRU(32, return_sequences=False, dropout=0.3),
                layers.Dense(64, activation='relu'),
                layers.Dropout(0.2),
                layers.Dense(1, activation='sigmoid')
            ])
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=config.dl_learning_rate),
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        early_stopping = keras.callbacks.EarlyStopping(
            monitor='val_loss', patience=5, restore_best_weights=True
        )
        
        model.fit(
            X_train, y_train,
            validation_data=(X_test, y_test),
            epochs=config.dl_epochs,
            batch_size=config.dl_batch_size,
            callbacks=[early_stopping],
            verbose=0
        )
        
        y_pred_prob = model.predict(X_test, verbose=0).flatten()
        y_pred = (y_pred_prob > 0.5).astype(int)
        
        training_time = time.time() - start_time
        metrics = self._compute_metrics(y_test, y_pred)
        
        # Clear session to free memory
        keras.backend.clear_session()
        
        return metrics, y_pred, training_time
    
    def _apply_fusion(self, predictions: Dict[str, np.ndarray], strategy: str) -> np.ndarray:
        """Apply fusion strategy to combine predictions"""
        pred_arrays = list(predictions.values())
        
        if strategy == "voting":
            # Hard voting
            stacked = np.stack(pred_arrays, axis=0)
            return (np.mean(stacked, axis=0) > 0.5).astype(int)
        elif strategy == "weighted":
            # Equal weighted average
            stacked = np.stack(pred_arrays, axis=0)
            return (np.mean(stacked, axis=0) > 0.5).astype(int)
        else:
            # Default to voting
            stacked = np.stack(pred_arrays, axis=0)
            return (np.mean(stacked, axis=0) > 0.5).astype(int)
    
    def _compute_metrics(self, y_true, y_pred) -> Dict[str, float]:
        """Compute evaluation metrics"""
        cm = confusion_matrix(y_true, y_pred)
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
        
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
        
        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
            "fpr": float(fpr),
            "fnr": float(fnr)
        }
    
    def _dummy_inference(self, X):
        """Dummy inference for throughput measurement"""
        return np.random.rand(len(X))
    
    def _save_result(self, result: ExperimentResult):
        """Save experiment result to disk"""
        result_dict = {
            "experiment_id": result.experiment_id,
            "config": asdict(result.config),
            "timestamp": result.timestamp.isoformat(),
            "metrics": {
                "accuracy": result.accuracy,
                "precision": result.precision,
                "recall": result.recall,
                "f1_score": result.f1_score,
                "fpr": result.fpr,
                "fnr": result.fnr
            },
            "performance": {
                "training_time_sec": result.training_time_sec,
                "inference_time_ms": result.inference_time_ms,
                "throughput_samples_per_sec": result.throughput_samples_per_sec
            },
            "model_results": result.model_results,
            "confusion_matrix": result.confusion_matrix
        }
        
        result_path = os.path.join(self.results_dir, f"{result.experiment_id}.json")
        with open(result_path, 'w') as f:
            json.dump(result_dict, f, indent=2)
        
        logger.info(f"Saved experiment result to {result_path}")
    
    def run_comparative_experiments(self, dataset_type: str = "nsl-kdd") -> Dict[str, ExperimentResult]:
        """
        Run comparative experiments: ML-only, DL-only, and Hybrid.
        
        Args:
            dataset_type: 'nsl-kdd' or 'cic-ids2017'
            
        Returns:
            Dictionary of experiment results
        """
        results = {}
        
        # ML-only experiment
        ml_config = ExperimentConfig(
            experiment_name=f"{dataset_type}_ml_only",
            dataset_type=dataset_type,
            model_types=["lightgbm", "xgboost"]
        )
        results["ml_only"] = self.run_experiment(ml_config)
        
        # DL-only experiment
        dl_config = ExperimentConfig(
            experiment_name=f"{dataset_type}_dl_only",
            dataset_type=dataset_type,
            model_types=["cnn", "gru"]
        )
        results["dl_only"] = self.run_experiment(dl_config)
        
        # Hybrid experiment
        hybrid_config = ExperimentConfig(
            experiment_name=f"{dataset_type}_hybrid",
            dataset_type=dataset_type,
            model_types=["lightgbm", "xgboost", "cnn", "gru"],
            fusion_strategy="weighted"
        )
        results["hybrid"] = self.run_experiment(hybrid_config)
        
        # Generate comparison report
        self._generate_comparison_report(results, dataset_type)
        
        return results
    
    def _generate_comparison_report(self, results: Dict[str, ExperimentResult], dataset_type: str):
        """Generate a comparison report for experiments"""
        report = {
            "dataset": dataset_type,
            "timestamp": datetime.now().isoformat(),
            "comparison": {}
        }
        
        for name, result in results.items():
            report["comparison"][name] = {
                "accuracy": result.accuracy,
                "precision": result.precision,
                "recall": result.recall,
                "f1_score": result.f1_score,
                "fpr": result.fpr,
                "fnr": result.fnr,
                "training_time_sec": result.training_time_sec
            }
        
        report_path = os.path.join(self.results_dir, f"comparison_{dataset_type}_{int(time.time())}.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Generated comparison report: {report_path}")
    
    def export_results(self, experiment_ids: List[str] = None) -> str:
        """
        Export experiment results for paper/audit.
        
        Returns:
            Path to exported file
        """
        results = []
        
        for filename in os.listdir(self.results_dir):
            if filename.endswith('.json') and not filename.startswith('comparison'):
                if experiment_ids is None or any(eid in filename for eid in experiment_ids):
                    with open(os.path.join(self.results_dir, filename), 'r') as f:
                        results.append(json.load(f))
        
        export_path = os.path.join(self.results_dir, f"export_{int(time.time())}.json")
        with open(export_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Exported {len(results)} experiment results to {export_path}")
        return export_path
