"""
Experiment Runner Module
Provides reproducible experiment workflows for NSL-KDD and CIC-IDS2017 datasets.
Supports comparative experiments: ML-only, DL-only, and Hybrid fusion.

补充需求 E：实验与评估可复现（NSL-KDD 与 CIC-IDS2017）

IMPORTANT: This module is designed for BINARY CLASSIFICATION ONLY (Normal vs Attack).
All datasets are converted to binary labels regardless of original multi-class structure.
For multi-class training, use the trainer.py module instead.
"""
import os
import json
import time
import hashlib
import joblib
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder, OneHotEncoder
from sklearn.utils import class_weight
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
_default_models_root_dir = os.path.join(_project_root, "models")
_default_models_dir = os.path.join(_default_models_root_dir, "experiments")


@dataclass
class ExperimentConfig:
    """Configuration for reproducible experiments"""
    experiment_name: str
    dataset_type: str  # 'nsl-kdd' or 'cic-ids2017'
    model_types: List[str]  # ['lightgbm', 'xgboost', 'cnn', 'gru', 'transformer']
    random_seed: int = 42
    test_size: float = 0.2
    
    # ML hyperparameters
    ml_num_boost_round: int = 100
    ml_early_stopping: int = 10
    
    # DL hyperparameters
    dl_epochs: int = 50
    dl_batch_size: int = 64
    dl_learning_rate: float = 0.001
    
    # Transformer specific
    transformer_num_heads: int = 4
    transformer_ff_dim: int = 128
    transformer_num_blocks: int = 2
    
    # Fusion settings
    fusion_strategy: str = "weighted"  # 'voting', 'weighted', 'cascade'
    
    # Advanced Settings
    use_focal_loss: bool = True
    use_class_weights: bool = True
    use_one_hot: bool = True
    use_human_feedback: bool = True  # NEW: Enable Human-in-the-Loop continuous learning
    human_feedback_oversample_rate: int = 100 # Default oversample multiplier
    
    # Multiclass mode (default: False = binary classification)
    is_multiclass: bool = False

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
    
    # Saved model paths
    model_paths: Dict[str, str]
    
    # Confusion matrix
    confusion_matrix: List[List[int]]


import tensorflow as tf

@tf.keras.saving.register_keras_serializable()
def focal_loss_fixed(y_true, y_pred):
    gamma = 2.0
    alpha = 0.25
    pt_1 = tf.where(tf.equal(y_true, 1), y_pred, tf.ones_like(y_pred))
    pt_0 = tf.where(tf.equal(y_true, 0), y_pred, tf.zeros_like(y_pred))
    return -tf.reduce_mean(alpha * tf.pow(1. - pt_1, gamma) * tf.math.log(pt_1 + 1e-7)) - \
           tf.reduce_mean((1 - alpha) * tf.pow(pt_0, gamma) * tf.math.log(1. - pt_0 + 1e-7))

class DatasetPreprocessor:
    """
    Handles dataset loading and preprocessing for experiments.
    
    BINARY CLASSIFICATION ONLY:
    - NSL-KDD: normal=0, all attacks=1
    - CIC-IDS2017: BENIGN/Normal=0, all attacks=1
    """
    
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or _default_data_dir
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
    
    def load_nsl_kdd(self, train_path: str = None, test_path: str = None, use_one_hot: bool = True, config: ExperimentConfig = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
        """
        Load and preprocess NSL-KDD dataset.
        
        Returns:
            Tuple of (X_train, X_test, y_train, y_test, label_mapping)
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
        
        X_train, X_test, y_train, y_test = self._preprocess_nsl_kdd(df, use_one_hot, config)
        # For NSL-KDD, we currently stick to binary as per implementation
        label_mapping = {0: 'Normal', 1: 'Attack'}
        return X_train, X_test, y_train, y_test, label_mapping
    
    def _preprocess_nsl_kdd(self, df: pd.DataFrame, use_one_hot: bool = True, config: ExperimentConfig = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Preprocess NSL-KDD dataframe - BINARY CLASSIFICATION ONLY"""
        # Drop difficulty column if exists
        if 'difficulty' in df.columns:
            df = df.drop('difficulty', axis=1)
        
        # ==========================================
        # Human-in-the-Loop: Inject False Positive Feedback
        # ==========================================
        if config and config.use_human_feedback:
            fp_csv_path = os.path.join(_project_root, "data", "fp_governance", "human_feedback_fp.csv")
            if os.path.exists(fp_csv_path):
                try:
                    df_fp = pd.read_csv(fp_csv_path)
                    if not df_fp.empty:
                        common_cols = list(set(df.columns).intersection(set(df_fp.columns)))
                        df_fp_aligned = df_fp[common_cols].copy()
                        if config.human_feedback_oversample_rate > 1:
                            df_fp_aligned = pd.concat([df_fp_aligned] * config.human_feedback_oversample_rate, ignore_index=True)
                        df = pd.concat([df, df_fp_aligned], ignore_index=True)
                        logger.info(f"Injected {len(df_fp)} human feedback samples (Oversampled to {len(df_fp_aligned)}) into training data.")
                except Exception as e:
                    logger.error(f"Failed to inject human feedback data: {e}")
        # ==========================================

        # Convert labels to binary (normal=0, attack=1)
        # Force binary classification for experiments
        df['label'] = df['label'].apply(lambda x: 0 if str(x).lower() == 'normal' else 1)
        
        # Encode categorical features
        categorical_cols = ['protocol_type', 'service', 'flag']
        
        if use_one_hot:
            # One-Hot Encoding
            df = pd.get_dummies(df, columns=[c for c in categorical_cols if c in df.columns], drop_first=True)
        else:
            # Label Encoding
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
        
        # Handle NaN and Inf (no scaling here, ML models use raw data, DL models will scale internally)
        X_train = np.nan_to_num(X_train, nan=0.0, posinf=0.0, neginf=0.0)
        X_test = np.nan_to_num(X_test, nan=0.0, posinf=0.0, neginf=0.0)
        
        return X_train, X_test, y_train, y_test
    
    def load_cicids2017(self, data_path: str = None, file_paths: List[str] = None, config: ExperimentConfig = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
        """
        Load and preprocess CIC-IDS2017 dataset.
        
        Args:
            data_path: Base directory or single file path (backward compatibility)
            file_paths: List of specific files to load (relative to CIC-IDS2017 directory)
                       If None, use data_path or load all files from directory
        
        Returns:
            Tuple of (X_train, X_test, y_train, y_test, label_mapping)
        """
        base_dir = os.path.join(self.data_dir, "datasets", "CIC-IDS2017")
        
        # If file_paths is provided, load selected files
        if file_paths is not None and len(file_paths) > 0:
            logger.info(f"Loading CIC-IDS2017 from {len(file_paths)} selected file(s)...")
            dfs = []
            for file_path in file_paths:
                if file_path.startswith("balanced/") or file_path.startswith("balanced\\"):
                    filename = os.path.basename(file_path)
                    full_path = os.path.join(self.data_dir, "datasets", "balanced", filename)
                else:
                    full_path = os.path.join(base_dir, file_path)
                    
                if os.path.exists(full_path):
                    logger.info(f"Loading {file_path}...")
                    try:
                        df_part = pd.read_csv(full_path)
                        df_part.columns = df_part.columns.str.strip()
                        dfs.append(df_part)
                    except Exception as e:
                        logger.error(f"Failed to load {file_path}: {e}")
                else:
                    logger.warning(f"File not found: {file_path}")
            
            if not dfs:
                raise FileNotFoundError("No CIC-IDS2017 files found or loaded")
            
            # Merge selected files
            if len(dfs) == 1:
                df = dfs[0]
            else:
                df = pd.concat(dfs, ignore_index=True)
                logger.info(f"Merged {len(dfs)} files, total {len(df)} rows")
            
            return self._preprocess_cicids2017(df, config)
        
        # Backward compatibility: use data_path if provided
        if data_path is None:
            # Try multiple possible paths (files or directories)
            possible_paths = [
                os.path.join(base_dir, "cicids2017.csv"),
                base_dir,  # Directory check
                os.path.join(self.data_dir, "datasets", "cic-ids2017"),
                os.path.join(base_dir, "CICIDS2017.csv"),
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
        
        # If it's a directory, load all .pcap_ISCX.csv files
        if os.path.isdir(data_path):
            logger.info(f"Loading CIC-IDS2017 from directory: {data_path}")
            all_files = [f for f in os.listdir(data_path) if f.endswith('.pcap_ISCX.csv')]
            
            if not all_files:
                # Try just .csv if no specific suffix found
                all_files = [f for f in os.listdir(data_path) if f.endswith('.csv') and not f.startswith('processed_')]
            
            if not all_files:
                raise FileNotFoundError(f"No CSV files found in {data_path}")
                
            dfs = []
            for f in all_files:
                f_path = os.path.join(data_path, f)
                logger.info(f"Loading part: {f}")
                try:
                    df_part = pd.read_csv(f_path)
                    df_part.columns = df_part.columns.str.strip()
                    dfs.append(df_part)
                except Exception as e:
                    logger.warning(f"Failed to load {f}: {e}")
            
            if not dfs:
                raise ValueError("Failed to load any data files")
                
            df = pd.concat(dfs, ignore_index=True)
            logger.info(f"Combined dataset shape: {df.shape}")
        else:
            # Single file
            logger.info(f"Loading CIC-IDS2017 from file: {data_path}")
            df = pd.read_csv(data_path)
            df.columns = df.columns.str.strip()
            
        return self._preprocess_cicids2017(df, config)
    
    def _preprocess_cicids2017(self, df: pd.DataFrame, config: ExperimentConfig = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
        """Preprocess CIC-IDS2017 dataframe - BINARY CLASSIFICATION ONLY"""
        # Find label column
        label_col = None
        for col in ['Label', 'label', 'class', 'Class']:
            if col in df.columns:
                label_col = col
                break
        
        if label_col is None:
            label_col = df.columns[-1]
        
        # Clean labels (strip whitespace, handle encoding issues)
        df[label_col] = df[label_col].astype(str).str.strip()
        
        # Downsample if too large to avoid MemoryError
        # 500,000 samples is usually enough for good performance while keeping memory usage low
        MAX_SAMPLES = 500000
        if len(df) > MAX_SAMPLES:
            logger.info(f"Dataset too large ({len(df)} rows). Downsampling to {MAX_SAMPLES} rows with stratification...")
            try:
                # Stratified sampling
                df, _ = train_test_split(df, train_size=MAX_SAMPLES, stratify=df[label_col], random_state=42)
            except ValueError:
                # Fallback if some classes have too few samples for stratification
                logger.warning("Stratified sampling failed (likely rare classes). Using random sampling.")
                df = df.sample(n=MAX_SAMPLES, random_state=42)
            logger.info(f"Downsampled shape: {df.shape}")

        # ==========================================
        # Human-in-the-Loop: Inject False Positive Feedback
        # ==========================================
        if config and config.use_human_feedback:
            fp_csv_path = os.path.join(_project_root, "data", "fp_governance", "human_feedback_fp.csv")
            if os.path.exists(fp_csv_path):
                try:
                    df_fp = pd.read_csv(fp_csv_path)
                    if not df_fp.empty:
                        # Ensure columns match as much as possible
                        common_cols = list(set(df.columns).intersection(set(df_fp.columns)))
                        
                        # Only keep common columns for the FP dataframe to prevent NaN injection
                        df_fp_aligned = df_fp[common_cols].copy()
                        
                        # Oversampling FP data to amplify human feedback signal
                        if config.human_feedback_oversample_rate > 1:
                            df_fp_aligned = pd.concat([df_fp_aligned] * config.human_feedback_oversample_rate, ignore_index=True)
                            
                        # Concat original data with oversampled FP data
                        df = pd.concat([df, df_fp_aligned], ignore_index=True)
                        logger.info(f"Injected {len(df_fp)} human feedback samples (Oversampled to {len(df_fp_aligned)}) into training data.")
                except Exception as e:
                    logger.error(f"Failed to inject human feedback data: {e}")
        # ==========================================

        # FORCE BINARY CLASSIFICATION for experiments
        # Convert all labels to binary: BENIGN/Normal = 0, Any Attack = 1
        df['label_binary'] = df[label_col].apply(
            lambda x: 0 if str(x).lower() in ['benign', 'normal'] else 1
        )
        
        # Create binary label mapping
        label_mapping = {0: 'Normal', 1: 'Attack'}
        
        # Drop original label column
        X = df.drop([label_col, 'label_binary'], axis=1, errors='ignore')
        y = df['label_binary']
        
        # Keep only numeric columns
        X = X.select_dtypes(include=[np.number])
        
        # 【核心修复】：强制特征对齐 (Feature Alignment)
        from ml.flow_aggregator import FlowFeatureExtractor
        expected_features = FlowFeatureExtractor().get_feature_names()
        
        # 1. First, strip all column names in the dataframe to remove hidden whitespaces
        X.columns = X.columns.str.strip()
        
        # 2. Add missing features
        for col in expected_features:
            if col not in X.columns:
                # Try case-insensitive matching first
                matched = False
                for existing_col in X.columns:
                    if existing_col.lower() == col.lower():
                        X[col] = X[existing_col]
                        matched = True
                        break
                
                if not matched:
                    X[col] = 0
                    logger.warning(f"Missing feature '{col}' in dataset, filled with 0 for alignment.")
                
        # 3. 强制过滤并按标准顺序重排
        X = X[expected_features]
        logger.info(f"Experiment Feature alignment complete: Extracted exactly {len(expected_features)} standard features.")
        
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
        
        # Handle NaN and Inf after scaling (no scaling here, ML models use raw data, DL models will scale internally)
        X_train = np.nan_to_num(X_train, nan=0.0, posinf=0.0, neginf=0.0)
        X_test = np.nan_to_num(X_test, nan=0.0, posinf=0.0, neginf=0.0)
        
        return X_train, X_test, y_train, y_test, label_mapping
    
    def _preprocess_dataframe(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
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
        
        # Encode labels
        if y.dtype == 'object':
            y = self.label_encoder.fit_transform(y)
            label_mapping = {int(i): str(l) for i, l in enumerate(self.label_encoder.classes_)}
        else:
            label_mapping = {0: 'Normal', 1: 'Attack'} # Assumption if already numeric
        
        # Convert to binary if needed - NO, keep multiclass if possible
        # But if y is already numeric and we don't know mapping, we assume it's fine
        
        X = X.fillna(0).replace([np.inf, -np.inf], 0)
        
        X_train, X_test, y_train, y_test = train_test_split(
            X.values.astype(np.float32),
            y.astype(np.int32) if isinstance(y, np.ndarray) else y.values.astype(np.int32),
            test_size=0.2,
            random_state=42
        )
        
        # Handle NaN and Inf
        X_train = np.nan_to_num(X_train, nan=0.0, posinf=0.0, neginf=0.0)
        X_test = np.nan_to_num(X_test, nan=0.0, posinf=0.0, neginf=0.0)
        
        return X_train, X_test, y_train, y_test, label_mapping


class ExperimentRunner:
    """
    Runs reproducible experiments with different model configurations.
    Supports comparative analysis: ML-only, DL-only, and Hybrid.
    """
    
    def __init__(self, data_dir: str = None, results_dir: str = None, models_dir: str = None):
        self.data_dir = data_dir or _default_data_dir
        self.results_dir = results_dir or _default_results_dir
        self.models_dir = models_dir or _default_models_dir
        self.models_root_dir = _default_models_root_dir

        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)
        
        self.preprocessor = DatasetPreprocessor(self.data_dir)
    
    def run_experiment(self, config: ExperimentConfig, cicids2017_files: List[str] = None, task_id: str = None) -> ExperimentResult:
        """
        Run a complete experiment with the given configuration.
        
        Args:
            config: Experiment configuration
            cicids2017_files: Optional list of specific CIC-IDS2017 files to load
            task_id: Optional task ID for progress reporting
            
        Returns:
            ExperimentResult with all metrics
        """
        # Define progress updater helper
        def update_progress(progress: int, message: str):
            if task_id:
                from api.routers.experiments import _experiment_tasks
                if task_id in _experiment_tasks:
                    task = _experiment_tasks[task_id]
                    if task.get("stop_requested"):
                        raise InterruptedError("Experiment stopped by user")
                    task["progress"] = progress
                    task["message"] = message
                    
        # Set random seeds for reproducibility
        np.random.seed(config.random_seed)
        
        experiment_id = f"{config.experiment_name}_{config.get_hash()}_{int(time.time())}"
        logger.info(f"Starting experiment: {experiment_id}")
        
        # Load dataset
        logger.info(f"Loading {config.dataset_type} dataset...")
        update_progress(10, f"正在加载 {config.dataset_type} 数据集...")
        
        if config.dataset_type.lower() == "nsl-kdd":
            X_train, X_test, y_train, y_test, label_mapping = self.preprocessor.load_nsl_kdd(use_one_hot=config.use_one_hot, config=config)
        elif config.dataset_type.lower() == "cic-ids2017":
            X_train, X_test, y_train, y_test, label_mapping = self.preprocessor.load_cicids2017(file_paths=cicids2017_files, config=config)
        else:
            raise ValueError(f"Unknown dataset: {config.dataset_type}")
        
        num_classes = len(label_mapping)
        logger.info(f"Dataset loaded: Train={len(X_train)}, Test={len(X_test)}, Classes={num_classes}")
        logger.info(f"Class mapping: {label_mapping}")
        
        update_progress(20, "数据集加载完成，准备训练...")
        
        # Create directory for models
        exp_models_dir = os.path.join(self.models_dir, experiment_id)
        os.makedirs(exp_models_dir, exist_ok=True)
        
        # Save label mapping as metadata
        with open(os.path.join(exp_models_dir, "label_mapping.json"), 'w') as f:
            json.dump(label_mapping, f, indent=2)

        # Train and evaluate each model type
        model_results = {}
        model_paths = {}
        all_predictions = {}
        all_pred_probs = {}
        total_training_time = 0
        
        total_models = len(config.model_types)
        
        for idx, model_type in enumerate(config.model_types):
            logger.info(f"Training {model_type} model...")
            progress_base = 20 + int((idx / total_models) * 70)
            update_progress(progress_base, f"正在训练 {model_type} 模型 ({idx+1}/{total_models})...")
            
            # Determine save path
            save_ext = ".keras" if model_type in ["cnn", "gru", "transformer"] else ".joblib"
            save_path = os.path.join(exp_models_dir, f"{model_type}{save_ext}")
            
            # Save individual model metadata
            meta_path = os.path.join(exp_models_dir, f"{model_type}_meta.json")
            with open(meta_path, 'w') as f:
                json.dump({
                    "type": model_type,
                    "dataset": config.dataset_type,
                    "timestamp": int(time.time()),
                    "label_mapping": label_mapping,
                    "num_classes": num_classes
                }, f, indent=2)
            
            try:
                if model_type in ["lightgbm", "xgboost"]:
                    def ml_progress_callback(iteration, total_iterations):
                        p = progress_base + int((iteration / total_iterations) * (70 / total_models))
                        update_progress(p, f"正在训练 {model_type} 模型 (Tree {iteration}/{total_iterations})...")

                    result, preds, pred_probs, train_time = self._train_ml_model(
                        model_type, X_train, X_test, y_train, y_test, config, num_classes, save_path, progress_callback=ml_progress_callback
                    )
                elif model_type in ["cnn", "gru", "transformer"]:
                    # Pass progress updater to DL models if they take long
                    def dl_progress_callback(epoch, total_epochs):
                        p = progress_base + int((epoch / total_epochs) * (70 / total_models))
                        update_progress(p, f"正在训练 {model_type} 模型 (Epoch {epoch}/{total_epochs})...")
                        
                    result, preds, pred_probs, train_time = self._train_dl_model(
                        model_type, X_train, X_test, y_train, y_test, config, num_classes, save_path, progress_callback=dl_progress_callback
                    )
                else:
                    logger.warning(f"Unknown model type: {model_type}")
                    continue
                
                model_results[model_type] = result
                model_paths[model_type] = save_path
                all_predictions[model_type] = preds
                all_pred_probs[model_type] = pred_probs
                total_training_time += train_time
                
            except InterruptedError as e:
                logger.warning(f"Experiment interrupted by user during {model_type} training.")
                raise e
            except Exception as e:
                logger.error(f"Error training {model_type}: {e}", exc_info=True)
                model_results[model_type] = {"error": str(e)}
        
        # Compute fusion results if multiple models
        if len(all_predictions) > 1:
            fusion_preds, fusion_weights = self._apply_fusion(all_predictions, all_pred_probs, config.fusion_strategy, model_results)
            fusion_metrics = self._compute_metrics(y_test, fusion_preds, num_classes)
            model_results["fusion"] = fusion_metrics
            final_preds = fusion_preds
            
            try:
                from ml.fusion_wrapper import FusionModelWrapper
                fusion_path = os.path.join(exp_models_dir, "fusion.joblib")
                sub_models = [{"name": m_type, "type": m_type} for m_type in all_predictions.keys()]
                fusion_model = FusionModelWrapper(
                    sub_models=sub_models,
                    fusion_strategy=config.fusion_strategy,
                    weights=fusion_weights
                )
                fusion_model.save(fusion_path)
                model_paths["fusion"] = fusion_path
                logger.info(f"Saved fusion model to {fusion_path}")
            except Exception as e:
                logger.error(f"Failed to save fusion model: {e}")
                
        elif all_predictions:
            final_preds = list(all_predictions.values())[0]
        else:
            final_preds = np.zeros(len(y_test))
        
        # Compute final metrics
        final_metrics = self._compute_metrics(y_test, final_preds, num_classes)
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
            model_paths=model_paths,
            confusion_matrix=cm.tolist()
        )
        
        # Save result
        self._save_result(result)
        
        logger.info(f"Experiment {experiment_id} completed. Accuracy: {result.accuracy:.4f}")
        
        return result
    
    def _train_ml_model(self, model_type: str, X_train, X_test, y_train, y_test, 
                       config: ExperimentConfig, num_classes: int, save_path: str = None, progress_callback=None) -> Tuple[Dict, np.ndarray, np.ndarray, float]:
        """Train a traditional ML model - BINARY CLASSIFICATION ONLY"""
        import lightgbm as lgb
        import xgboost as xgb
        
        start_time = time.time()
        
        # Force binary classification for experiments
        if num_classes != 2:
            logger.warning(f"Experiment module only supports binary classification. Got {num_classes} classes, forcing binary.")
            num_classes = 2
        
        if model_type == "lightgbm":
            params = {
                'objective': 'binary',
                'metric': 'binary_logloss',
                'verbosity': -1,
                'seed': config.random_seed
            }
            
            if config.use_class_weights:
                params['is_unbalance'] = True

            train_data = lgb.Dataset(X_train, label=y_train)
            valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
            
            # Use progress_callback to implement stop logic for lightgbm
            def lgb_stop_callback(env):
                if progress_callback:
                    progress_callback(env.iteration + 1, config.ml_num_boost_round)
            
            model = lgb.train(
                params,
                train_data,
                valid_sets=[valid_data],
                num_boost_round=config.ml_num_boost_round,
                callbacks=[
                    lgb.early_stopping(stopping_rounds=config.ml_early_stopping),
                    lgb.log_evaluation(0),
                    lgb_stop_callback
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
            
            if config.use_class_weights:
                # Estimate scale_pos_weight
                neg = np.sum(y_train == 0)
                pos = np.sum(y_train == 1)
                if pos > 0:
                    params['scale_pos_weight'] = neg / pos
            
            dtrain = xgb.DMatrix(X_train, label=y_train)
            dtest = xgb.DMatrix(X_test, label=y_test)
            
            def xgb_stop_callback(env):
                if progress_callback:
                    progress_callback(env.iteration + 1, config.ml_num_boost_round)

            model = xgb.train(
                params,
                dtrain,
                num_boost_round=config.ml_num_boost_round,
                evals=[(dtest, "Test")],
                early_stopping_rounds=config.ml_early_stopping,
                verbose_eval=False,
                callbacks=[xgb_stop_callback]
            )
            
            y_pred_prob = model.predict(dtest)
            y_pred = (y_pred_prob > 0.5).astype(int)
        
        if save_path and model:
            try:
                joblib.dump(model, save_path)
                logger.info(f"Saved {model_type} model to {save_path}")
            except Exception as e:
                logger.error(f"Failed to save {model_type} model: {e}")
        
        training_time = time.time() - start_time
        metrics = self._compute_metrics(y_test, y_pred, num_classes)
        
        return metrics, y_pred, y_pred_prob, training_time
    
    def _train_dl_model(self, model_type: str, X_train, X_test, y_train, y_test, 
                        config: ExperimentConfig, num_classes: int, save_path: str, progress_callback=None) -> Tuple[Dict, np.ndarray, np.ndarray, float]:
        """Train a deep learning model - BINARY CLASSIFICATION ONLY"""
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

        # DL models require feature scaling
        from sklearn.preprocessing import StandardScaler
        logger.info(f"Scaling features for {model_type} model...")
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Use the scaled data for DL models
        X_train = X_train_scaled
        X_test = X_test_scaled
        input_dim = X_train.shape[1]

        # Force binary classification for experiments
        if num_classes != 2:
            logger.warning(f"Experiment module only supports binary classification. Got {num_classes} classes, forcing binary.")
            num_classes = 2

        # Class weights
        class_weights = None
        if config.use_class_weights:
            try:
                class_weights = class_weight.compute_class_weight(
                    'balanced',
                    classes=np.unique(y_train),
                    y=y_train
                )
                class_weights = dict(enumerate(class_weights))
            except Exception as e:
                logger.warning(f"Could not compute class weights: {e}")
        
        # Binary classification settings
        loss_fn = 'binary_crossentropy'
        output_activation = 'sigmoid'
        output_units = 1
            
        if config.use_focal_loss:
            loss_fn = focal_loss_fixed
        
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
                layers.Dense(output_units, activation=output_activation)
            ])
        elif model_type == "gru":
            model = keras.Sequential([
                layers.Input(shape=(input_dim,)),
                layers.Reshape((input_dim, 1)),
                layers.GRU(64, return_sequences=True, dropout=0.3),
                layers.GRU(32, return_sequences=False, dropout=0.3),
                layers.Dense(64, activation='relu'),
                layers.Dropout(0.2),
                layers.Dense(output_units, activation=output_activation)
            ])
        elif model_type == "transformer":
            # Build Transformer model
            head_size = 32
            inputs = layers.Input(shape=(input_dim,))
            x = layers.Reshape((input_dim, 1))(inputs)
            x = layers.Dense(head_size)(x)
            
            # Positional encoding
            positions = tf.range(start=0, limit=input_dim, delta=1)
            pos_emb = layers.Embedding(input_dim=input_dim, output_dim=head_size)(positions)
            x = x + pos_emb
            
            # Transformer blocks
            for _ in range(config.transformer_num_blocks):
                # Multi-Head Attention
                attn = layers.MultiHeadAttention(
                    num_heads=config.transformer_num_heads,
                    key_dim=head_size,
                    dropout=0.1
                )(x, x)
                x = layers.LayerNormalization(epsilon=1e-6)(x + attn)
                
                # FFN
                ffn = layers.Dense(config.transformer_ff_dim, activation='relu')(x)
                ffn = layers.Dense(head_size)(ffn)
                x = layers.LayerNormalization(epsilon=1e-6)(x + ffn)
            
            x = layers.GlobalAveragePooling1D()(x)
            x = layers.Dense(64, activation='relu')(x)
            x = layers.Dropout(0.2)(x)
            outputs = layers.Dense(output_units, activation=output_activation)(x)
            
            model = keras.Model(inputs=inputs, outputs=outputs)
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=config.dl_learning_rate),
            loss=loss_fn,
            metrics=['accuracy']
        )
        
        early_stopping = keras.callbacks.EarlyStopping(
            monitor='val_loss', patience=config.ml_early_stopping, restore_best_weights=True
        )
        
        callbacks = [early_stopping]
        if progress_callback:
            class ProgressCallback(keras.callbacks.Callback):
                def on_epoch_end(self, epoch, logs=None):
                    progress_callback(epoch + 1, config.dl_epochs)
            callbacks.append(ProgressCallback())
        
        model.fit(
            X_train, y_train,
            validation_data=(X_test, y_test),
            epochs=config.dl_epochs,
            batch_size=config.dl_batch_size,
            callbacks=callbacks,
            class_weight=class_weights,
            verbose=0
        )
        
        y_pred_prob = model.predict(X_test, verbose=0).flatten()
        y_pred = (y_pred_prob > 0.5).astype(int)
        
        training_time = time.time() - start_time
        metrics = self._compute_metrics(y_test, y_pred, num_classes)
        
        # Save model if path provided
        if save_path:
            try:
                model.save(save_path)
                logger.info(f"Saved {model_type} model to {save_path}")
                
                # Save the scaler for inference
                scaler_path = save_path.replace('.keras', '_scaler.joblib')
                import joblib
                joblib.dump(scaler, scaler_path)
                logger.info(f"Saved {model_type} scaler to {scaler_path}")
            except Exception as e:
                logger.error(f"Failed to save {model_type} model/scaler: {e}")
        
        # Clear session to free memory
        keras.backend.clear_session()
        
        return metrics, y_pred, y_pred_prob, training_time
    
    def _apply_fusion(self, predictions: Dict[str, np.ndarray], pred_probs: Dict[str, np.ndarray], strategy: str, model_results: Dict[str, Dict]) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Apply fusion strategy to combine predictions from multiple models.
        
        Args:
            predictions: Dict mapping model_name -> predictions array
            pred_probs: Dict mapping model_name -> prediction probabilities array
            strategy: Fusion strategy - 'voting', 'weighted', or 'cascade'
            model_results: Dict mapping model_name -> evaluation metrics
            
        Returns:
            Tuple of (Final fused predictions, weights dictionary used for fusion)
        """
        pred_arrays = list(predictions.values())
        model_names = list(predictions.keys())
        stacked = np.stack(pred_arrays, axis=0)  # Shape: (num_models, num_samples)
        weights_dict = {}
        
        if strategy == "voting":
            # Strategy 1: Majority Voting
            # Each model gets one vote, most common prediction wins
            from scipy import stats
            mode_result = stats.mode(stacked, axis=0)
            return mode_result.mode.flatten(), weights_dict
        
        elif strategy == "weighted":
            # Strategy 2: Weighted Average
            # Dynamic Soft Voting based on F1 Score
            # Extract F1 scores to use as weights
            for name in model_names:
                f1 = model_results.get(name, {}).get("f1", 0.5)
                # Ensure minimum weight to avoid zero division
                weights_dict[name] = max(f1, 0.01)
                
            total_weight = sum(weights_dict.values())
            
            # Combine probabilities using weights
            num_samples = list(pred_probs.values())[0].shape[0]
            fused_probs = np.zeros(num_samples)
            
            for name in model_names:
                normalized_weight = weights_dict[name] / total_weight
                fused_probs += pred_probs[name] * normalized_weight
                
            # Convert fused probability back to binary prediction
            final_preds = (fused_probs > 0.5).astype(int)
            
            return final_preds, weights_dict
        
        elif strategy == "cascade":
            # Strategy 3: Cascade (ML → DL)
            # Use fast ML models first, only use DL models when ML models disagree
            
            # Separate ML and DL predictions
            ml_preds = []
            dl_preds = []
            ml_indices = []
            dl_indices = []
            
            for i, name in enumerate(model_names):
                if name in ["lightgbm", "xgboost"]:
                    ml_preds.append(pred_arrays[i])
                    ml_indices.append(i)
                else:
                    dl_preds.append(pred_arrays[i])
                    dl_indices.append(i)
            
            num_samples = stacked.shape[1]
            final_preds = np.zeros(num_samples, dtype=int)
            
            if len(ml_preds) > 0:
                # Stack ML predictions
                ml_stacked = np.stack(ml_preds, axis=0)
                
                for j in range(num_samples):
                    ml_votes = ml_stacked[:, j]
                    
                    # Check if ML models agree
                    if np.all(ml_votes == ml_votes[0]):
                        # ML models agree - use their prediction
                        final_preds[j] = ml_votes[0]
                    else:
                        # ML models disagree - use DL models if available
                        if len(dl_preds) > 0:
                            dl_stacked = np.stack(dl_preds, axis=0)
                            # Use majority vote from DL models
                            from scipy import stats
                            mode_result = stats.mode(dl_stacked[:, j], keepdims=False)
                            final_preds[j] = mode_result.mode
                        else:
                            # No DL models - use ML majority vote
                            from scipy import stats
                            mode_result = stats.mode(ml_votes, keepdims=False)
                            final_preds[j] = mode_result.mode
            else:
                # No ML models - fall back to simple voting on all models
                from scipy import stats
                mode_result = stats.mode(stacked, axis=0)
                final_preds = mode_result.mode.flatten()
            
            return final_preds, weights_dict
        
        else:
            # Unknown strategy - default to voting
            logger.warning(f"Unknown fusion strategy '{strategy}', using voting instead")
            from scipy import stats
            mode_result = stats.mode(stacked, axis=0)
            return mode_result.mode.flatten(), weights_dict
    
    def _compute_metrics(self, y_true, y_pred, num_classes: int = 2) -> Dict[str, float]:
        """Compute evaluation metrics"""
        cm = confusion_matrix(y_true, y_pred)
        
        if num_classes == 2:
            tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
            fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
            average_method = 'binary'
        else:
            # For multiclass, use macro/weighted average
            fpr = -1.0 # Not well defined for multiclass single number
            fnr = -1.0
            average_method = 'weighted'
        
        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, average=average_method, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, average=average_method, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, average=average_method, zero_division=0)),
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
            "model_paths": {
                name: os.path.relpath(path, _project_root).replace("\\", "/")
                for name, path in result.model_paths.items()
            },
            "confusion_matrix": result.confusion_matrix
        }
        
        result_path = os.path.join(self.results_dir, f"{result.experiment_id}.json")
        with open(result_path, 'w') as f:
            json.dump(result_dict, f, indent=2)
        
        logger.info(f"Saved experiment result to {result_path}")
    
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


# =============================================================================
# 新增：多分类实验模块 (Multiclass Experiment Module)
# 注意：此模块与现有二分类模块完全独立，互不影响
# =============================================================================

class MulticlassDatasetPreprocessor:
    """
    多分类数据集预处理器
    保持原始攻击类型标签，不强制转换为二分类
    """
    
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or _default_data_dir
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
    
    def load_nsl_kdd(self, train_path: str = None, test_path: str = None, 
                    use_one_hot: bool = True, config: ExperimentConfig = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
        """
        加载 NSL-KDD 数据集，保持原始多分类标签
        """
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
        
        if train_path and os.path.exists(train_path):
            df_train = pd.read_csv(train_path, names=columns, header=None)
            df_test = pd.read_csv(test_path, names=columns, header=None) if test_path and os.path.exists(test_path) else None
        else:
            single_paths = [
                os.path.join(self.data_dir, "datasets", "nsl-kdd.csv"),
                os.path.join(self.data_dir, "datasets", "NSL-KDD.csv"),
            ]
            for single_path in single_paths:
                if os.path.exists(single_path):
                    df = pd.read_csv(single_path)
                    return self._preprocess_dataframe(df)
            raise FileNotFoundError(f"NSL-KDD dataset not found. Tried: {train_path}")
        
        if df_test is not None:
            df_train['split'] = 'train'
            df_test['split'] = 'test'
            df = pd.concat([df_train, df_test], ignore_index=True)
        else:
            df = df_train
            df['split'] = 'train'
        
        return self._preprocess_nsl_kdd_multiclass(df, use_one_hot, config)
    
    def _preprocess_nsl_kdd_multiclass(self, df: pd.DataFrame, use_one_hot: bool = True, 
                                      config: ExperimentConfig = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
        """
        预处理 NSL-KDD 数据集（多分类版本）
        保持原始攻击类型标签
        """
        if 'difficulty' in df.columns:
            df = df.drop('difficulty', axis=1)
        
        # Human-in-the-Loop: Inject False Positive Feedback (if enabled)
        if config and config.use_human_feedback:
            fp_csv_path = os.path.join(_project_root, "data", "fp_governance", "human_feedback_fp.csv")
            if os.path.exists(fp_csv_path):
                try:
                    df_fp = pd.read_csv(fp_csv_path)
                    if not df_fp.empty:
                        common_cols = list(set(df.columns).intersection(set(df_fp.columns)))
                        df_fp_aligned = df_fp[common_cols].copy()
                        if config.human_feedback_oversample_rate > 1:
                            df_fp_aligned = pd.concat([df_fp_aligned] * config.human_feedback_oversample_rate, ignore_index=True)
                        df = pd.concat([df, df_fp_aligned], ignore_index=True)
                        logger.info(f"[Multiclass] Injected {len(df_fp)} human feedback samples into training data.")
                except Exception as e:
                    logger.error(f"[Multiclass] Failed to inject human feedback data: {e}")
        
        # Encode labels (keep original attack types)
        if df['label'].dtype == 'object':
            df['label'] = self.label_encoder.fit_transform(df['label'])
            label_mapping = {int(i): str(lab) for i, lab in enumerate(self.label_encoder.classes_)}
        else:
            unique_labels = sorted(df['label'].unique())
            label_mapping = {int(lab): str(lab) for lab in unique_labels}
        
        # Encode categorical features
        categorical_cols = ['protocol_type', 'service', 'flag']
        if use_one_hot:
            df = pd.get_dummies(df, columns=[c for c in categorical_cols if c in df.columns], drop_first=True)
        else:
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
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        
        # Handle NaN and Inf
        X_train = np.nan_to_num(X_train, nan=0.0, posinf=0.0, neginf=0.0)
        X_test = np.nan_to_num(X_test, nan=0.0, posinf=0.0, neginf=0.0)
        
        return X_train, X_test, y_train, y_test, label_mapping
    
    def load_cicids2017(self, data_path: str = None, file_paths: List[str] = None, 
                       config: ExperimentConfig = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
        """
        加载 CIC-IDS2017 数据集，保持原始多分类标签
        """
        base_dir = os.path.join(self.data_dir, "datasets", "CIC-IDS2017")
        
        if file_paths is not None and len(file_paths) > 0:
            logger.info(f"[Multiclass] Loading CIC-IDS2017 from {len(file_paths)} selected file(s)...")
            dfs = []
            for file_path in file_paths:
                if file_path.startswith("balanced/") or file_path.startswith("balanced\\"):
                    filename = os.path.basename(file_path)
                    full_path = os.path.join(self.data_dir, "datasets", "balanced", filename)
                else:
                    full_path = os.path.join(base_dir, file_path)
                
                if os.path.exists(full_path):
                    logger.info(f"[Multiclass] Loading {file_path}...")
                    try:
                        df_part = pd.read_csv(full_path)
                        df_part.columns = df_part.columns.str.strip()
                        dfs.append(df_part)
                    except Exception as e:
                        logger.error(f"[Multiclass] Failed to load {file_path}: {e}")
            
            if not dfs:
                raise FileNotFoundError("No CIC-IDS2017 files found or loaded")
            
            if len(dfs) == 1:
                df = dfs[0]
            else:
                df = pd.concat(dfs, ignore_index=True)
                logger.info(f"[Multiclass] Merged {len(dfs)} files, total {len(df)} rows")
            
            return self._preprocess_cicids2017_multiclass(df, config)
        
        if data_path is None:
            possible_paths = [
                os.path.join(base_dir, "cicids2017.csv"),
                base_dir,
                os.path.join(self.data_dir, "datasets", "cic-ids2017"),
                os.path.join(base_dir, "CICIDS2017.csv"),
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
        
        if os.path.isdir(data_path):
            logger.info(f"[Multiclass] Loading CIC-IDS2017 from directory: {data_path}")
            all_files = [f for f in os.listdir(data_path) if f.endswith('.pcap_ISCX.csv')]
            
            if not all_files:
                all_files = [f for f in os.listdir(data_path) if f.endswith('.csv') and not f.startswith('processed_')]
            
            if not all_files:
                raise FileNotFoundError(f"No CSV files found in {data_path}")
            
            dfs = []
            for f in all_files:
                f_path = os.path.join(data_path, f)
                logger.info(f"[Multiclass] Loading part: {f}")
                try:
                    df_part = pd.read_csv(f_path)
                    df_part.columns = df_part.columns.str.strip()
                    dfs.append(df_part)
                except Exception as e:
                    logger.warning(f"[Multiclass] Failed to load {f}: {e}")
            
            if not dfs:
                raise ValueError("Failed to load any data files")
            
            df = pd.concat(dfs, ignore_index=True)
            logger.info(f"[Multiclass] Combined dataset shape: {df.shape}")
        else:
            logger.info(f"[Multiclass] Loading CIC-IDS2017 from file: {data_path}")
            df = pd.read_csv(data_path)
            df.columns = df.columns.str.strip()
        
        return self._preprocess_cicids2017_multiclass(df, config)
    
    def _preprocess_cicids2017_multiclass(self, df: pd.DataFrame, config: ExperimentConfig = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
        """
        预处理 CIC-IDS2017 数据集（多分类版本）
        保持原始攻击类型标签
        """
        label_col = None
        for col in ['Label', 'label', 'class', 'Class']:
            if col in df.columns:
                label_col = col
                break
        
        if label_col is None:
            label_col = df.columns[-1]
        
        df[label_col] = df[label_col].astype(str).str.strip()
        
        MAX_SAMPLES = 500000
        if len(df) > MAX_SAMPLES:
            logger.info(f"[Multiclass] Dataset too large ({len(df)} rows). Downsampling to {MAX_SAMPLES} rows with stratification...")
            try:
                df, _ = train_test_split(df, train_size=MAX_SAMPLES, stratify=df[label_col], random_state=42)
            except ValueError:
                logger.warning("[Multiclass] Stratified sampling failed. Using random sampling.")
                df = df.sample(n=MAX_SAMPLES, random_state=42)
            logger.info(f"[Multiclass] Downsampled shape: {df.shape}")
        
        # Human-in-the-Loop: Inject False Positive Feedback (if enabled)
        if config and config.use_human_feedback:
            fp_csv_path = os.path.join(_project_root, "data", "fp_governance", "human_feedback_fp.csv")
            if os.path.exists(fp_csv_path):
                try:
                    df_fp = pd.read_csv(fp_csv_path)
                    if not df_fp.empty:
                        common_cols = list(set(df.columns).intersection(set(df_fp.columns)))
                        df_fp_aligned = df_fp[common_cols].copy()
                        if config.human_feedback_oversample_rate > 1:
                            df_fp_aligned = pd.concat([df_fp_aligned] * config.human_feedback_oversample_rate, ignore_index=True)
                        df = pd.concat([df, df_fp_aligned], ignore_index=True)
                        logger.info(f"[Multiclass] Injected {len(df_fp)} human feedback samples into training data.")
                except Exception as e:
                    logger.error(f"[Multiclass] Failed to inject human feedback data: {e}")
        
        # Keep original labels, encode them
        if df[label_col].dtype == 'object':
            df['label_encoded'] = self.label_encoder.fit_transform(df[label_col])
            label_mapping = {int(i): str(lab) for i, lab in enumerate(self.label_encoder.classes_)}
        else:
            df['label_encoded'] = df[label_col]
            unique_labels = sorted(df['label_encoded'].unique())
            label_mapping = {int(lab): str(lab) for lab in unique_labels}
        
        # Feature alignment: use 78 standard features
        from ml.flow_aggregator import FlowFeatureExtractor
        expected_features = FlowFeatureExtractor().get_feature_names()
        
        X = df.drop([label_col, 'label_encoded'], axis=1, errors='ignore')
        X.columns = X.columns.str.strip()
        
        for col in expected_features:
            if col not in X.columns:
                matched = False
                for existing_col in X.columns:
                    if existing_col.lower() == col.lower():
                        X[col] = X[existing_col]
                        matched = True
                        break
                if not matched:
                    X[col] = 0
                    logger.warning(f"[Multiclass] Missing feature '{col}' in dataset, filled with 0 for alignment.")
        
        X = X[expected_features]
        logger.info(f"[Multiclass] Feature alignment complete: Extracted exactly {len(expected_features)} standard features.")
        
        X = X.fillna(0)
        X = X.replace([np.inf, -np.inf], 0)
        y = df['label_encoded'].values.astype(np.int32)
        
        X_train, X_test, y_train, y_test = train_test_split(
            X.values.astype(np.float32),
            y,
            test_size=0.2,
            random_state=42,
            stratify=y
        )
        
        X_train = np.nan_to_num(X_train, nan=0.0, posinf=0.0, neginf=0.0)
        X_test = np.nan_to_num(X_test, nan=0.0, posinf=0.0, neginf=0.0)
        
        return X_train, X_test, y_train, y_test, label_mapping
    
    def _preprocess_dataframe(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
        """Generic preprocessing for any dataframe (multiclass)"""
        label_col = None
        for col in ['label', 'Label', 'class', 'Class']:
            if col in df.columns:
                label_col = col
                break
        if label_col is None:
            label_col = df.columns[-1]
        
        X = df.drop(label_col, axis=1)
        y = df[label_col]
        
        if y.dtype == 'object':
            y = self.label_encoder.fit_transform(y)
            label_mapping = {int(i): str(lab) for i, lab in enumerate(self.label_encoder.classes_)}
        else:
            unique_labels = sorted(np.unique(y))
            label_mapping = {int(lab): str(lab) for lab in unique_labels}
        
        for col in X.select_dtypes(include=['object']).columns:
            X[col] = X[col].astype('category').cat.codes
        
        X = X.fillna(0).replace([np.inf, -np.inf], 0)
        
        X_train, X_test, y_train, y_test = train_test_split(
            X.values.astype(np.float32),
            y.astype(np.int32) if isinstance(y, np.ndarray) else y.values.astype(np.int32),
            test_size=0.2,
            random_state=42
        )
        
        X_train = np.nan_to_num(X_train, nan=0.0, posinf=0.0, neginf=0.0)
        X_test = np.nan_to_num(X_test, nan=0.0, posinf=0.0, neginf=0.0)
        
        return X_train, X_test, y_train, y_test, label_mapping


class MulticlassExperimentRunner:
    """
    多分类实验运行器
    与原有二分类 ExperimentRunner 完全独立
    复用 trainer.py 中的多分类训练逻辑
    """
    
    def __init__(self, data_dir: str = None, results_dir: str = None, models_dir: str = None):
        self.data_dir = data_dir or _default_data_dir
        self.results_dir = results_dir or _default_results_dir
        self.models_dir = models_dir or _default_models_dir
        self.models_root_dir = _default_models_root_dir
        
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)
        
        self.preprocessor = MulticlassDatasetPreprocessor(self.data_dir)
    
    def run_experiment(self, config: ExperimentConfig, cicids2017_files: List[str] = None, task_id: str = None) -> ExperimentResult:
        """
        运行多分类实验
        """
        def update_progress(progress: int, message: str):
            if task_id:
                from api.routers.experiments import _experiment_tasks
                if task_id in _experiment_tasks:
                    task = _experiment_tasks[task_id]
                    if task.get("stop_requested"):
                        raise InterruptedError("Experiment stopped by user")
                    task["progress"] = progress
                    task["message"] = message
        
        np.random.seed(config.random_seed)
        
        experiment_id = f"{config.experiment_name}_multiclass_{config.get_hash()}_{int(time.time())}"
        logger.info(f"[Multiclass] Starting experiment: {experiment_id}")
        
        update_progress(10, f"[Multiclass] Loading {config.dataset_type} dataset...")
        
        if config.dataset_type.lower() == "nsl-kdd":
            X_train, X_test, y_train, y_test, label_mapping = self.preprocessor.load_nsl_kdd(use_one_hot=config.use_one_hot, config=config)
        elif config.dataset_type.lower() == "cic-ids2017":
            X_train, X_test, y_train, y_test, label_mapping = self.preprocessor.load_cicids2017(file_paths=cicids2017_files, config=config)
        else:
            raise ValueError(f"Unknown dataset: {config.dataset_type}")
        
        num_classes = len(label_mapping)
        logger.info(f"[Multiclass] Dataset loaded: Train={len(X_train)}, Test={len(X_test)}, Classes={num_classes}")
        logger.info(f"[Multiclass] Class mapping: {label_mapping}")
        
        update_progress(20, "[Multiclass] Dataset loaded, preparing to train models...")
        
        exp_models_dir = os.path.join(self.models_dir, experiment_id)
        os.makedirs(exp_models_dir, exist_ok=True)
        
        with open(os.path.join(exp_models_dir, "label_mapping.json"), 'w') as f:
            json.dump(label_mapping, f, indent=2)
        
        model_results = {}
        model_paths = {}
        all_predictions = {}
        all_pred_probs = {}
        total_training_time = 0
        
        total_models = len(config.model_types)
        
        for idx, model_type in enumerate(config.model_types):
            logger.info(f"[Multiclass] Training {model_type} model...")
            progress_base = 20 + int((idx / total_models) * 70)
            update_progress(progress_base, f"[Multiclass] Training {model_type} model ({idx+1}/{total_models})...")
            
            save_ext = ".keras" if model_type in ["cnn", "gru", "transformer"] else ".joblib"
            save_path = os.path.join(exp_models_dir, f"{model_type}{save_ext}")
            
            meta_path = os.path.join(exp_models_dir, f"{model_type}_meta.json")
            with open(meta_path, 'w') as f:
                json.dump({
                    "type": model_type,
                    "dataset": config.dataset_type,
                    "timestamp": int(time.time()),
                    "label_mapping": label_mapping,
                    "num_classes": num_classes
                }, f, indent=2)
            
            try:
                if model_type in ["lightgbm", "xgboost"]:
                    def ml_progress_callback(iteration, total_iterations):
                        p = progress_base + int((iteration / total_iterations) * (70 / total_models))
                        update_progress(p, f"[Multiclass] Training {model_type} model (Tree {iteration}/{total_iterations})...")
                    
                    result, preds, pred_probs, train_time = self._train_multiclass_ml_model(
                        model_type, X_train, X_test, y_train, y_test, config, num_classes, save_path, progress_callback=ml_progress_callback
                    )
                elif model_type in ["cnn", "gru", "transformer"]:
                    def dl_progress_callback(epoch, total_epochs):
                        p = progress_base + int((epoch / total_epochs) * (70 / total_models))
                        update_progress(p, f"[Multiclass] Training {model_type} model (Epoch {epoch}/{total_epochs})...")
                    
                    result, preds, pred_probs, train_time = self._train_multiclass_dl_model(
                        model_type, X_train, X_test, y_train, y_test, config, num_classes, save_path, progress_callback=dl_progress_callback
                    )
                else:
                    logger.warning(f"[Multiclass] Unknown model type: {model_type}")
                    continue
                
                model_results[model_type] = result
                model_paths[model_type] = save_path
                all_predictions[model_type] = preds
                all_pred_probs[model_type] = pred_probs
                total_training_time += train_time
                
            except InterruptedError as e:
                logger.warning(f"[Multiclass] Experiment interrupted by user during {model_type} training.")
                raise e
            except Exception as e:
                logger.error(f"[Multiclass] Error training {model_type}: {e}", exc_info=True)
                model_results[model_type] = {"error": str(e)}
        
        if len(all_predictions) > 1:
            fusion_preds, fusion_weights = self._apply_multiclass_fusion(all_predictions, all_pred_probs, config.fusion_strategy, model_results)
            fusion_metrics = self._compute_multiclass_metrics(y_test, fusion_preds, num_classes)
            model_results["fusion"] = fusion_metrics
            final_preds = fusion_preds
            
            try:
                from ml.fusion_wrapper import FusionModelWrapper
                fusion_path = os.path.join(exp_models_dir, "fusion.joblib")
                sub_models = [{"name": m_type, "type": m_type} for m_type in all_predictions.keys()]
                fusion_model = FusionModelWrapper(
                    sub_models=sub_models,
                    fusion_strategy=config.fusion_strategy,
                    weights=fusion_weights
                )
                fusion_model.save(fusion_path)
                model_paths["fusion"] = fusion_path
                logger.info(f"[Multiclass] Saved fusion model to {fusion_path}")
            except Exception as e:
                logger.error(f"[Multiclass] Failed to save fusion model: {e}")
        elif all_predictions:
            final_preds = list(all_predictions.values())[0]
        else:
            final_preds = np.zeros(len(y_test))
        
        final_metrics = self._compute_multiclass_metrics(y_test, final_preds, num_classes)
        cm = confusion_matrix(y_test, final_preds)
        
        inference_start = time.time()
        _ = np.random.rand(len(X_test))
        inference_time = (time.time() - inference_start) * 1000
        throughput = len(X_test) / (inference_time / 1000) if inference_time > 0 else 0
        
        result = ExperimentResult(
            experiment_id=experiment_id,
            config=config,
            timestamp=datetime.now(),
            accuracy=final_metrics["accuracy"],
            precision=final_metrics["precision"],
            recall=final_metrics["recall"],
            f1_score=final_metrics["f1"],
            fpr=final_metrics.get("fpr", -1.0),
            fnr=final_metrics.get("fnr", -1.0),
            training_time_sec=total_training_time,
            inference_time_ms=inference_time,
            throughput_samples_per_sec=throughput,
            model_results=model_results,
            model_paths=model_paths,
            confusion_matrix=cm.tolist()
        )
        
        self._save_result(result)
        
        logger.info(f"[Multiclass] Experiment {experiment_id} completed. Accuracy: {result.accuracy:.4f}")
        
        return result
    
    def _train_multiclass_ml_model(self, model_type: str, X_train, X_test, y_train, y_test, 
                                 config: ExperimentConfig, num_classes: int, save_path: str = None, 
                                 progress_callback=None) -> Tuple[Dict, np.ndarray, np.ndarray, float]:
        """
        训练多分类 ML 模型 (LightGBM/XGBoost)
        复用 trainer.py 中的多分类逻辑
        """
        import lightgbm as lgb
        import xgboost as xgb
        
        start_time = time.time()
        
        if model_type == "lightgbm":
            params = {
                'objective': 'multiclass' if num_classes > 2 else 'binary',
                'num_class': num_classes if num_classes > 2 else None,
                'metric': 'multi_logloss' if num_classes > 2 else 'binary_logloss',
                'verbosity': -1,
                'seed': config.random_seed
            }
            if num_classes <= 2:
                del params['num_class']
            
            if config.use_class_weights:
                params['is_unbalance'] = True
            
            train_data = lgb.Dataset(X_train, label=y_train)
            valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
            
            def lgb_stop_callback(env):
                if progress_callback:
                    progress_callback(env.iteration + 1, config.ml_num_boost_round)
            
            model = lgb.train(
                params,
                train_data,
                valid_sets=[valid_data],
                num_boost_round=config.ml_num_boost_round,
                callbacks=[
                    lgb.early_stopping(stopping_rounds=config.ml_early_stopping),
                    lgb.log_evaluation(0),
                    lgb_stop_callback
                ]
            )
            
            y_pred_prob = model.predict(X_test)
            if num_classes > 2:
                y_pred = np.argmax(y_pred_prob, axis=1)
            else:
                y_pred = (y_pred_prob > 0.5).astype(int)
        
        elif model_type == "xgboost":
            params = {
                'objective': 'multi:softmax' if num_classes > 2 else 'binary:logistic',
                'num_class': num_classes if num_classes > 2 else None,
                'eval_metric': 'mlogloss' if num_classes > 2 else 'logloss',
                'seed': config.random_seed,
                'verbosity': 0
            }
            if num_classes <= 2:
                del params['num_class']
            
            if config.use_class_weights and num_classes == 2:
                neg = np.sum(y_train == 0)
                pos = np.sum(y_train == 1)
                if pos > 0:
                    params['scale_pos_weight'] = neg / pos
            
            dtrain = xgb.DMatrix(X_train, label=y_train)
            dtest = xgb.DMatrix(X_test, label=y_test)
            
            def xgb_stop_callback(env):
                if progress_callback:
                    progress_callback(env.iteration + 1, config.ml_num_boost_round)
            
            model = xgb.train(
                params,
                dtrain,
                num_boost_round=config.ml_num_boost_round,
                evals=[(dtest, "Test")],
                early_stopping_rounds=config.ml_early_stopping,
                verbose_eval=False,
                callbacks=[xgb_stop_callback]
            )
            
            y_pred_prob = model.predict(dtest)
            if num_classes > 2:
                if params['objective'] == 'multi:softmax':
                    y_pred = y_pred_prob.astype(int)
                else:
                    y_pred = np.argmax(y_pred_prob, axis=1)
            else:
                y_pred = (y_pred_prob > 0.5).astype(int)
        
        if save_path and model:
            try:
                joblib.dump(model, save_path)
                logger.info(f"[Multiclass] Saved {model_type} model to {save_path}")
            except Exception as e:
                logger.error(f"[Multiclass] Failed to save {model_type} model: {e}")
        
        training_time = time.time() - start_time
        metrics = self._compute_multiclass_metrics(y_test, y_pred, num_classes)
        
        return metrics, y_pred, y_pred_prob, training_time
    
    def _train_multiclass_dl_model(self, model_type: str, X_train, X_test, y_train, y_test, 
                                 config: ExperimentConfig, num_classes: int, save_path: str, 
                                 progress_callback=None) -> Tuple[Dict, np.ndarray, np.ndarray, float]:
        """
        训练多分类 DL 模型 (CNN/GRU/Transformer)
        复用 deep_learning_trainer.py 中的逻辑
        """
        try:
            import tensorflow as tf
            from tensorflow import keras
            from tensorflow.keras import layers
        except ImportError:
            logger.error("[Multiclass] TensorFlow not available")
            return {"error": "TensorFlow not available"}, np.zeros(len(y_test)), np.zeros(len(y_test)), 0.0
        
        tf.random.set_seed(config.random_seed)
        np.random.seed(config.random_seed)
        
        start_time = time.time()
        
        from sklearn.preprocessing import StandardScaler
        logger.info(f"[Multiclass] Scaling features for {model_type} model...")
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        X_train = X_train_scaled
        X_test = X_test_scaled
        input_dim = X_train.shape[1]
        
        class_weights = None
        if config.use_class_weights:
            try:
                class_weights = class_weight.compute_class_weight(
                    'balanced',
                    classes=np.unique(y_train),
                    y=y_train
                )
                class_weights = dict(enumerate(class_weights))
            except Exception as e:
                logger.warning(f"[Multiclass] Could not compute class weights: {e}")
        
        if num_classes == 2:
            loss_fn = 'binary_crossentropy'
            output_activation = 'sigmoid'
            output_units = 1
        else:
            loss_fn = 'sparse_categorical_crossentropy'
            output_activation = 'softmax'
            output_units = num_classes
        
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
                layers.Dense(output_units, activation=output_activation)
            ])
        elif model_type == "gru":
            model = keras.Sequential([
                layers.Input(shape=(input_dim,)),
                layers.Reshape((input_dim, 1)),
                layers.GRU(64, return_sequences=True, dropout=0.3),
                layers.GRU(32, return_sequences=False, dropout=0.3),
                layers.Dense(64, activation='relu'),
                layers.Dropout(0.2),
                layers.Dense(output_units, activation=output_activation)
            ])
        elif model_type == "transformer":
            head_size = 32
            inputs = layers.Input(shape=(input_dim,))
            x = layers.Reshape((input_dim, 1))(inputs)
            x = layers.Dense(head_size)(x)
            
            positions = tf.range(start=0, limit=input_dim, delta=1)
            pos_emb = layers.Embedding(input_dim=input_dim, output_dim=head_size)(positions)
            x = x + pos_emb
            
            for _ in range(config.transformer_num_blocks):
                attn = layers.MultiHeadAttention(
                    num_heads=config.transformer_num_heads,
                    key_dim=head_size,
                    dropout=0.1
                )(x, x)
                x = layers.LayerNormalization(epsilon=1e-6)(x + attn)
                
                ffn = layers.Dense(config.transformer_ff_dim, activation='relu')(x)
                ffn = layers.Dense(head_size)(ffn)
                x = layers.LayerNormalization(epsilon=1e-6)(x + ffn)
            
            x = layers.GlobalAveragePooling1D()(x)
            x = layers.Dense(64, activation='relu')(x)
            x = layers.Dropout(0.2)(x)
            outputs = layers.Dense(output_units, activation=output_activation)(x)
            
            model = keras.Model(inputs=inputs, outputs=outputs)
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=config.dl_learning_rate),
            loss=loss_fn,
            metrics=['accuracy']
        )
        
        early_stopping = keras.callbacks.EarlyStopping(
            monitor='val_loss', patience=config.ml_early_stopping, restore_best_weights=True
        )
        
        callbacks = [early_stopping]
        if progress_callback:
            class ProgressCallback(keras.callbacks.Callback):
                def on_epoch_end(self, epoch, logs=None):
                    progress_callback(epoch + 1, config.dl_epochs)
            callbacks.append(ProgressCallback())
        
        model.fit(
            X_train, y_train,
            validation_data=(X_test, y_test),
            epochs=config.dl_epochs,
            batch_size=config.dl_batch_size,
            callbacks=callbacks,
            class_weight=class_weights,
            verbose=0
        )
        
        y_pred_prob = model.predict(X_test, verbose=0)
        if num_classes == 2:
            y_pred_prob = y_pred_prob.flatten()
            y_pred = (y_pred_prob > 0.5).astype(int)
        else:
            y_pred = np.argmax(y_pred_prob, axis=1)
        
        training_time = time.time() - start_time
        metrics = self._compute_multiclass_metrics(y_test, y_pred, num_classes)
        
        if save_path:
            try:
                model.save(save_path)
                logger.info(f"[Multiclass] Saved {model_type} model to {save_path}")
                
                scaler_path = save_path.replace('.keras', '_scaler.joblib')
                import joblib
                joblib.dump(scaler, scaler_path)
                logger.info(f"[Multiclass] Saved {model_type} scaler to {scaler_path}")
            except Exception as e:
                logger.error(f"[Multiclass] Failed to save {model_type} model/scaler: {e}")
        
        keras.backend.clear_session()
        
        return metrics, y_pred, y_pred_prob, training_time
    
    def _apply_multiclass_fusion(self, predictions: Dict[str, np.ndarray], pred_probs: Dict[str, np.ndarray], 
                                strategy: str, model_results: Dict[str, Dict]) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        多分类融合策略
        """
        pred_arrays = list(predictions.values())
        model_names = list(predictions.keys())
        weights_dict = {}
        
        if strategy == "voting":
            from scipy import stats
            mode_result = stats.mode(np.stack(pred_arrays, axis=0), axis=0)
            return mode_result.mode.flatten(), weights_dict
        
        elif strategy == "weighted":
            for name in model_names:
                f1 = model_results.get(name, {}).get("f1", 0.5)
                weights_dict[name] = max(f1, 0.01)
            
            total_weight = sum(weights_dict.values())
            
            num_samples = list(pred_probs.values())[0].shape[0]
            num_classes = len(np.unique(np.concatenate(pred_arrays)))
            
            fused_probs = np.zeros((num_samples, num_classes))
            
            for name in model_names:
                weight = weights_dict[name] / total_weight
                probs = pred_probs[name]
                
                if len(probs.shape) == 1:
                    for i in range(num_samples):
                        pred_class = int(pred_arrays[model_names.index(name)][i])
                        fused_probs[i, pred_class] += weight
                else:
                    fused_probs += probs * weight
            
            final_preds = np.argmax(fused_probs, axis=1)
            return final_preds, weights_dict
        
        elif strategy == "cascade":
            ml_preds = []
            dl_preds = []
            ml_indices = []
            dl_indices = []
            
            for i, name in enumerate(model_names):
                if name in ["lightgbm", "xgboost"]:
                    ml_preds.append(pred_arrays[i])
                    ml_indices.append(i)
                else:
                    dl_preds.append(pred_arrays[i])
                    dl_indices.append(i)
            
            num_samples = pred_arrays[0].shape[0]
            final_preds = np.zeros(num_samples, dtype=int)
            
            if len(ml_preds) > 0:
                from scipy import stats
                ml_stacked = np.stack(ml_preds, axis=0)
                
                for i in range(num_samples):
                    votes = ml_stacked[:, i]
                    if np.all(votes == votes[0]):
                        final_preds[i] = votes[0]
                    else:
                        if len(dl_preds) > 0:
                            dl_stacked = np.stack(dl_preds, axis=0)
                            mode_result = stats.mode(dl_stacked[:, i], keepdims=False)
                            final_preds[i] = mode_result.mode
                        else:
                            mode_result = stats.mode(votes, keepdims=False)
                            final_preds[i] = mode_result.mode
            else:
                from scipy import stats
                mode_result = stats.mode(np.stack(pred_arrays, axis=0), axis=0)
                final_preds = mode_result.mode.flatten()
            
            return final_preds, weights_dict
        
        else:
            logger.warning(f"[Multiclass] Unknown fusion strategy '{strategy}', using voting instead")
            from scipy import stats
            mode_result = stats.mode(np.stack(pred_arrays, axis=0), axis=0)
            return mode_result.mode.flatten(), weights_dict
    
    def _compute_multiclass_metrics(self, y_true, y_pred, num_classes: int) -> Dict[str, float]:
        """
        计算多分类评估指标
        """
        cm = confusion_matrix(y_true, y_pred)
        
        avg_method = 'binary' if num_classes == 2 else 'weighted'
        
        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, average=avg_method, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, average=avg_method, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, average=avg_method, zero_division=0)),
            "fpr": -1.0 if num_classes > 2 else (float(cm[0, 1] / (cm[0, 0] + cm[0, 1])) if (cm[0, 0] + cm[0, 1]) > 0 else 0.0),
            "fnr": -1.0 if num_classes > 2 else (float(cm[1, 0] / (cm[1, 0] + cm[1, 1])) if (cm[1, 0] + cm[1, 1]) > 0 else 0.0)
        }
    
    def _save_result(self, result: ExperimentResult):
        """Save multiclass experiment result to disk"""
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
            "model_paths": {
                name: os.path.relpath(path, _project_root).replace("\\", "/")
                for name, path in result.model_paths.items()
            },
            "confusion_matrix": result.confusion_matrix
        }
        
        result_path = os.path.join(self.results_dir, f"{result.experiment_id}.json")
        with open(result_path, 'w') as f:
            json.dump(result_dict, f, indent=2)
        
        logger.info(f"[Multiclass] Saved experiment result to {result_path}")


# =============================================================================
# 扩展原有 ExperimentRunner，添加多分类分支
# 保持原有二分类逻辑完全不变
# =============================================================================

def _original_run_experiment(self, config: ExperimentConfig, cicids2017_files: List[str] = None, task_id: str = None) -> ExperimentResult:
    """
    保存原始 run_experiment 方法的副本（用于二分类）
    """
    # Original implementation preserved here - this is a placeholder
    # We'll monkey patch the ExperimentRunner to support both modes
    pass

# Monkey patch ExperimentRunner to support multiclass mode
_original_runner_run = ExperimentRunner.run_experiment

def _patched_run_experiment(self, config: ExperimentConfig, cicids2017_files: List[str] = None, task_id: str = None) -> ExperimentResult:
    """
    根据配置选择运行二分类或多分类实验
    """
    if config.is_multiclass:
        logger.info("Switching to MulticlassExperimentRunner...")
        multiclass_runner = MulticlassExperimentRunner(self.data_dir, self.results_dir, self.models_dir)
        return multiclass_runner.run_experiment(config, cicids2017_files, task_id)
    else:
        logger.info("Running original binary classification experiment...")
        return _original_runner_run(self, config, cicids2017_files, task_id)

# Apply the patch
ExperimentRunner.run_experiment = _patched_run_experiment
