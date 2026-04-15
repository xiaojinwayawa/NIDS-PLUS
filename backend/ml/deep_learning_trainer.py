"""
Deep Learning Model Training Module
Supports 1D-CNN, GRU and Transformer models for network intrusion detection.

补充需求 A：深度学习模型训练与推理链路（1D-CNN/GRU/Transformer）
"""
import os
import json
import time
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional, List
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.preprocessing import StandardScaler, LabelEncoder

from logging_config import app_logger as logger

# Get project root directory
_current_file = os.path.abspath(__file__)
_ml_dir = os.path.dirname(_current_file)
_backend_dir = os.path.dirname(_ml_dir)
_project_root = os.path.dirname(_backend_dir)
_default_models_dir = os.path.join(_project_root, "models")
_default_data_dir = os.path.join(_project_root, "data")

# Global training progress storage (shared with trainer.py)
_dl_training_progress: Dict[str, Dict[str, Any]] = {}


def get_dl_training_progress(task_id: str) -> Optional[Dict[str, Any]]:
    """Get deep learning training progress for a task"""
    return _dl_training_progress.get(task_id)


def set_dl_training_progress(task_id: str, progress: Dict[str, Any]):
    """Set deep learning training progress for a task"""
    _dl_training_progress[task_id] = progress


def clear_dl_training_progress(task_id: str):
    """Clear deep learning training progress for a task"""
    if task_id in _dl_training_progress:
        del _dl_training_progress[task_id]


class DeepLearningConfig:
    """Configuration for deep learning models"""
    def __init__(self,
                 model_type: str = "cnn",  # 'cnn', 'gru', or 'transformer'
                 input_dim: int = 78,       # Number of input features
                 sequence_length: int = 1,  # For sequence models
                 hidden_units: List[int] = None,
                 dropout_rate: float = 0.3,
                 learning_rate: float = 0.001,
                 batch_size: int = 64,
                 epochs: int = 50,
                 early_stopping_patience: int = 5,
                 random_seed: int = 42,
                 # Transformer specific
                 num_heads: int = 4,
                 ff_dim: int = 128,
                 num_transformer_blocks: int = 2):
        self.model_type = model_type
        self.input_dim = input_dim
        self.sequence_length = sequence_length
        self.hidden_units = hidden_units or [128, 64, 32]
        self.dropout_rate = dropout_rate
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.epochs = epochs
        self.early_stopping_patience = early_stopping_patience
        self.random_seed = random_seed
        # Transformer specific
        self.num_heads = num_heads
        self.ff_dim = ff_dim
        self.num_transformer_blocks = num_transformer_blocks


class DeepLearningTrainer:
    """
    Trainer for deep learning models (1D-CNN, GRU, and Transformer).
    Uses TensorFlow/Keras for model building and training.
    """
    
    def __init__(self, models_dir: str = None, data_dir: str = None):
        self.models_dir = models_dir or _default_models_dir
        self.data_dir = data_dir or _default_data_dir
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        
        if not os.path.exists(self.models_dir):
            os.makedirs(self.models_dir)
        
        # Check TensorFlow availability
        self._tf_available = self._check_tensorflow()
    
    def _check_tensorflow(self) -> bool:
        """Check if TensorFlow is available"""
        try:
            import tensorflow as tf
            logger.info(f"TensorFlow version: {tf.__version__}")
            return True
        except ImportError:
            logger.warning("TensorFlow not available. Deep learning features disabled.")
            return False
    
    def _build_cnn_model(self, config: DeepLearningConfig, num_classes: int):
        """Build 1D-CNN model for intrusion detection"""
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
        
        # Set random seed for reproducibility
        tf.random.set_seed(config.random_seed)
        np.random.seed(config.random_seed)
        
        model = keras.Sequential([
            # Input layer - reshape for 1D convolution
            layers.Input(shape=(config.input_dim,)),
            layers.Reshape((config.input_dim, 1)),
            
            # Single Conv block
            layers.Conv1D(filters=128, kernel_size=3, activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.GlobalAveragePooling1D(),
            layers.Dropout(config.dropout_rate),
            
            # Dense layers
            layers.Dense(config.hidden_units[0], activation='relu'),
            layers.Dropout(config.dropout_rate),
            layers.Dense(config.hidden_units[1], activation='relu'),
            layers.Dropout(config.dropout_rate / 2),
            
            # Output layer
            layers.Dense(1 if num_classes == 2 else num_classes, 
                        activation='sigmoid' if num_classes == 2 else 'softmax')
        ])
        
        # Compile model
        optimizer = keras.optimizers.Adam(learning_rate=config.learning_rate)
        
        if num_classes == 2:
            model.compile(
                optimizer=optimizer,
                loss='binary_crossentropy',
                metrics=['accuracy']
            )
        else:
            model.compile(
                optimizer=optimizer,
                loss='sparse_categorical_crossentropy',
                metrics=['accuracy']
            )
        
        return model
    
    def _build_gru_model(self, config: DeepLearningConfig, num_classes: int):
        """Build GRU model for intrusion detection"""
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
        
        # Set random seed
        tf.random.set_seed(config.random_seed)
        np.random.seed(config.random_seed)
        
        model = keras.Sequential([
            # Input layer - reshape for sequence processing
            layers.Input(shape=(config.input_dim,)),
            layers.Reshape((config.input_dim, 1)),
            
            # GRU layers
            layers.GRU(128, return_sequences=True, dropout=config.dropout_rate),
            layers.GRU(64, return_sequences=True, dropout=config.dropout_rate),
            layers.GRU(32, return_sequences=False, dropout=config.dropout_rate),
            
            # Dense layers
            layers.Dense(config.hidden_units[0], activation='relu'),
            layers.Dropout(config.dropout_rate),
            layers.Dense(config.hidden_units[1], activation='relu'),
            layers.Dropout(config.dropout_rate / 2),
            
            # Output layer
            layers.Dense(1 if num_classes == 2 else num_classes,
                        activation='sigmoid' if num_classes == 2 else 'softmax')
        ])
        
        optimizer = keras.optimizers.Adam(learning_rate=config.learning_rate)
        
        if num_classes == 2:
            model.compile(
                optimizer=optimizer,
                loss='binary_crossentropy',
                metrics=['accuracy']
            )
        else:
            model.compile(
                optimizer=optimizer,
                loss='sparse_categorical_crossentropy',
                metrics=['accuracy']
            )
        
        return model
    
    def _build_transformer_model(self, config: DeepLearningConfig, num_classes: int):
        """
        Build Transformer model for intrusion detection.
        Uses Multi-Head Self-Attention to capture feature relationships.
        """
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
        
        # Set random seed
        tf.random.set_seed(config.random_seed)
        np.random.seed(config.random_seed)
        
        def transformer_encoder_block(inputs, head_size, num_heads, ff_dim, dropout=0.1):
            """Single Transformer encoder block"""
            # Multi-Head Self-Attention
            attention_output = layers.MultiHeadAttention(
                num_heads=num_heads, 
                key_dim=head_size,
                dropout=dropout
            )(inputs, inputs)
            attention_output = layers.Dropout(dropout)(attention_output)
            x1 = layers.LayerNormalization(epsilon=1e-6)(inputs + attention_output)
            
            # Feed Forward Network
            ffn_output = layers.Dense(ff_dim, activation='relu')(x1)
            ffn_output = layers.Dropout(dropout)(ffn_output)
            ffn_output = layers.Dense(inputs.shape[-1])(ffn_output)
            ffn_output = layers.Dropout(dropout)(ffn_output)
            x2 = layers.LayerNormalization(epsilon=1e-6)(x1 + ffn_output)
            
            return x2
        
        # Input layer
        inputs = layers.Input(shape=(config.input_dim,))
        
        # Reshape to sequence format: (batch, seq_len, features)
        # Treat each feature as a token in the sequence
        x = layers.Reshape((config.input_dim, 1))(inputs)
        
        # Project to higher dimension for attention
        head_size = 32
        x = layers.Dense(head_size)(x)
        
        # Positional encoding (learnable)
        positions = tf.range(start=0, limit=config.input_dim, delta=1)
        position_embedding = layers.Embedding(
            input_dim=config.input_dim, 
            output_dim=head_size
        )(positions)
        x = x + position_embedding
        
        # Stack Transformer encoder blocks
        for _ in range(config.num_transformer_blocks):
            x = transformer_encoder_block(
                x, 
                head_size=head_size,
                num_heads=config.num_heads, 
                ff_dim=config.ff_dim, 
                dropout=config.dropout_rate
            )
        
        # Global pooling
        x = layers.GlobalAveragePooling1D()(x)
        
        # Classification head
        x = layers.Dense(config.hidden_units[0], activation='relu')(x)
        x = layers.Dropout(config.dropout_rate)(x)
        x = layers.Dense(config.hidden_units[1], activation='relu')(x)
        x = layers.Dropout(config.dropout_rate / 2)(x)
        
        # Output layer
        if num_classes == 2:
            outputs = layers.Dense(1, activation='sigmoid')(x)
        else:
            outputs = layers.Dense(num_classes, activation='softmax')(x)
        
        model = keras.Model(inputs=inputs, outputs=outputs)
        
        optimizer = keras.optimizers.Adam(learning_rate=config.learning_rate)
        
        if num_classes == 2:
            model.compile(
                optimizer=optimizer,
                loss='binary_crossentropy',
                metrics=['accuracy']
            )
        else:
            model.compile(
                optimizer=optimizer,
                loss='sparse_categorical_crossentropy',
                metrics=['accuracy']
            )
        
        return model

    def load_dataset(self, dataset_path_or_paths: str or List[str]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Load and preprocess dataset for deep learning.
        
        Args:
            dataset_path_or_paths: Path to CSV dataset or list of paths
            
        Returns:
            Tuple of (X, y) numpy arrays
        """
        if isinstance(dataset_path_or_paths, str):
            dataset_path_or_paths = [dataset_path_or_paths]
        
        dfs = []
        for dataset_path in dataset_path_or_paths:
            logger.info(f"Loading dataset from {dataset_path}...")
            df_part = pd.read_csv(dataset_path)
            dfs.append(df_part)
        
        if len(dfs) == 1:
            df = dfs[0]
        else:
            df = pd.concat(dfs, ignore_index=True)
            logger.info(f"Merged {len(dfs)} datasets, total {len(df)} samples")
        
        # Identify target column
        target_col = None
        if 'label' in df.columns:
            target_col = 'label'
        elif 'class' in df.columns:
            target_col = 'class'
        elif 'Label' in df.columns:
            target_col = 'Label'
        else:
            target_col = df.columns[-1]
        
        X = df.drop(columns=[target_col])
        y = df[target_col]
        
        # Handle categorical features
        for col in X.select_dtypes(include=['object']).columns:
            X[col] = X[col].astype('category').cat.codes
        
        # Handle missing values
        X = X.fillna(0)
        
        # Replace infinity values
        X = X.replace([np.inf, -np.inf], 0)
        
        # Encode target
        if y.dtype == 'object':
            y = self.label_encoder.fit_transform(y)
        else:
            y = y.values
        
        # Convert to binary if needed (normal=0, attack=1)
        unique_labels = np.unique(y)
        if len(unique_labels) > 2:
            # Multi-class: keep as is
            pass
        
        return X.values.astype(np.float32), y.astype(np.int32)
    
    def train_model(self,
                   model_type: str,
                   dataset_path: str,
                   config: DeepLearningConfig = None,
                   model_name: str = "dl_model",
                   task_id: str = None) -> Dict[str, Any]:
        """
        Train a deep learning model.
        
        Args:
            model_type: 'cnn', 'gru', or 'transformer'
            dataset_path: Path to training data
            config: Model configuration
            model_name: Name for saving
            task_id: Task ID for progress tracking
            
        Returns:
            Dictionary with training metrics
        """
        if not self._tf_available:
            raise RuntimeError("TensorFlow is not available. Cannot train deep learning models.")
        
        import tensorflow as tf
        from tensorflow import keras
        
        start_time = time.time()
        
        def update_progress(stage: str, current: int, total: int, message: str = "", metrics: Dict = None):
            if task_id:
                progress = {
                    "stage": stage,
                    "current": current,
                    "total": total,
                    "percent": int((current / total) * 100) if total > 0 else 0,
                    "message": message,
                    "elapsed": time.time() - start_time,
                    "metrics": metrics or {}
                }
                set_dl_training_progress(task_id, progress)
        
        try:
            # Initialize config
            if config is None:
                config = DeepLearningConfig(model_type=model_type)
            else:
                config.model_type = model_type
            
            # Stage 1: Load Data (10%)
            update_progress("loading", 0, 100, "Loading dataset...")
            X, y = self.load_dataset(dataset_path)
            config.input_dim = X.shape[1]
            update_progress("loading", 10, 100, f"Dataset loaded: {len(X)} samples, {X.shape[1]} features")
            
            # Stage 2: Preprocess (15%)
            update_progress("preprocessing", 10, 100, "Preprocessing data...")
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=config.random_seed, stratify=y
            )
            
            # Scale features
            X_train = self.scaler.fit_transform(X_train)
            X_test = self.scaler.transform(X_test)
            
            num_classes = len(np.unique(y))
            update_progress("preprocessing", 15, 100, 
                          f"Train: {len(X_train)}, Test: {len(X_test)}, Classes: {num_classes}")
            
            # Stage 3: Build Model (20%)
            update_progress("building", 15, 100, f"Building {model_type.upper()} model...")
            
            if model_type.lower() == "cnn":
                model = self._build_cnn_model(config, num_classes)
            elif model_type.lower() == "gru":
                model = self._build_gru_model(config, num_classes)
            elif model_type.lower() == "transformer":
                model = self._build_transformer_model(config, num_classes)
            else:
                raise ValueError(f"Unsupported model type: {model_type}. Supported: cnn, gru, transformer")
            
            update_progress("building", 20, 100, "Model built successfully")
            
            # Stage 4: Training (20% - 85%)
            class ProgressCallback(keras.callbacks.Callback):
                def on_epoch_end(self, epoch, logs=None):
                    progress_pct = 20 + int(((epoch + 1) / config.epochs) * 65)
                    metrics = {
                        "loss": float(logs.get('loss', 0)),
                        "accuracy": float(logs.get('accuracy', 0)),
                        "val_loss": float(logs.get('val_loss', 0)),
                        "val_accuracy": float(logs.get('val_accuracy', 0))
                    }
                    update_progress("training", progress_pct, 100, 
                                  f"Epoch {epoch + 1}/{config.epochs}", metrics)
            
            early_stopping = keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience=config.early_stopping_patience,
                restore_best_weights=True
            )
            
            update_progress("training", 20, 100, "Starting training...")
            
            history = model.fit(
                X_train, y_train,
                validation_data=(X_test, y_test),
                epochs=config.epochs,
                batch_size=config.batch_size,
                callbacks=[ProgressCallback(), early_stopping],
                verbose=0
            )
            
            # Stage 5: Evaluation (85% - 95%)
            update_progress("evaluating", 85, 100, "Evaluating model...")
            
            y_pred_prob = model.predict(X_test, verbose=0)
            if num_classes == 2:
                y_pred = (y_pred_prob > 0.5).astype(int).flatten()
            else:
                y_pred = np.argmax(y_pred_prob, axis=1)
            
            metrics = {
                "accuracy": float(accuracy_score(y_test, y_pred)),
                "precision": float(precision_score(y_test, y_pred, average='weighted', zero_division=0)),
                "recall": float(recall_score(y_test, y_pred, average='weighted', zero_division=0)),
                "f1": float(f1_score(y_test, y_pred, average='weighted', zero_division=0)),
                "training_time": time.time() - start_time,
                "epochs_trained": len(history.history['loss']),
                "final_loss": float(history.history['loss'][-1]),
                "final_val_loss": float(history.history['val_loss'][-1])
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
            
            # Stage 6: Save Model (95% - 100%)
            update_progress("saving", 95, 100, "Saving model...")
            
            # Save Keras model
            model_path = os.path.join(self.models_dir, f"{model_name}.h5")
            model.save(model_path)
            
            # Save scaler
            import joblib
            scaler_path = os.path.join(self.models_dir, f"{model_name}_scaler.joblib")
            joblib.dump(self.scaler, scaler_path)
            
            # Save metadata
            meta_path = os.path.join(self.models_dir, f"{model_name}_meta.json")
            metadata = {
                "name": model_name,
                "type": model_type,
                "framework": "tensorflow",
                "input_dim": config.input_dim,
                "num_classes": num_classes,
                "config": {
                    "hidden_units": config.hidden_units,
                    "dropout_rate": config.dropout_rate,
                    "learning_rate": config.learning_rate,
                    "batch_size": config.batch_size,
                    "epochs": config.epochs,
                    "random_seed": config.random_seed
                },
                "metrics": metrics,
                "timestamp": time.time()
            }
            
            with open(meta_path, 'w') as f:
                json.dump(metadata, f, indent=4)
            
            update_progress("complete", 100, 100, "Training complete!", metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error during deep learning training: {e}")
            if task_id:
                set_dl_training_progress(task_id, {
                    "stage": "error",
                    "current": 0,
                    "total": 100,
                    "percent": 0,
                    "message": str(e),
                    "elapsed": time.time() - start_time
                })
            raise e


class SequenceModelTrainer:
    """
    Trainer for sequence-based deep learning models.
    Handles sequence data (multiple packets per sample) for 1D-CNN and GRU.
    """
    
    def __init__(self, models_dir: str = None):
        self.models_dir = models_dir or _default_models_dir
        self.scaler = StandardScaler()
        
        if not os.path.exists(self.models_dir):
            os.makedirs(self.models_dir)
        
        self._tf_available = self._check_tensorflow()
    
    def _check_tensorflow(self) -> bool:
        try:
            import tensorflow as tf
            return True
        except ImportError:
            return False
    
    def _build_sequence_cnn(self, sequence_length: int, feature_dim: int, num_classes: int):
        """Build 1D-CNN for sequence data"""
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
        
        model = keras.Sequential([
            layers.Input(shape=(sequence_length, feature_dim)),
            
            # Single Conv block
            layers.Conv1D(128, 3, activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.GlobalAveragePooling1D(),
            layers.Dropout(0.3),
            
            layers.Dense(64, activation='relu'),
            layers.Dropout(0.2),
            layers.Dense(1 if num_classes == 2 else num_classes,
                        activation='sigmoid' if num_classes == 2 else 'softmax')
        ])
        
        model.compile(
            optimizer='adam',
            loss='binary_crossentropy' if num_classes == 2 else 'sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def _build_sequence_gru(self, sequence_length: int, feature_dim: int, num_classes: int):
        """Build GRU for sequence data"""
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
        
        model = keras.Sequential([
            layers.Input(shape=(sequence_length, feature_dim)),
            
            # Bidirectional GRU layers
            layers.Bidirectional(layers.GRU(64, return_sequences=True, dropout=0.3)),
            layers.Bidirectional(layers.GRU(32, return_sequences=False, dropout=0.3)),
            
            layers.Dense(64, activation='relu'),
            layers.Dropout(0.3),
            layers.Dense(32, activation='relu'),
            layers.Dropout(0.2),
            layers.Dense(1 if num_classes == 2 else num_classes,
                        activation='sigmoid' if num_classes == 2 else 'softmax')
        ])
        
        model.compile(
            optimizer='adam',
            loss='binary_crossentropy' if num_classes == 2 else 'sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def train_sequence_model(self,
                            X_sequences: np.ndarray,
                            y_labels: np.ndarray,
                            model_type: str = "cnn",
                            model_name: str = "seq_model",
                            epochs: int = 50,
                            batch_size: int = 32,
                            task_id: str = None) -> Dict[str, Any]:
        """
        Train a sequence model on pre-built sequence samples.
        
        Args:
            X_sequences: Shape (num_samples, sequence_length, feature_dim)
            y_labels: Shape (num_samples,)
            model_type: 'cnn' or 'gru'
            model_name: Name for saving
            epochs: Number of training epochs
            batch_size: Batch size
            task_id: Task ID for progress tracking
            
        Returns:
            Training metrics
        """
        if not self._tf_available:
            raise RuntimeError("TensorFlow not available")
        
        import tensorflow as tf
        from tensorflow import keras
        
        start_time = time.time()
        
        # Get dimensions
        num_samples, sequence_length, feature_dim = X_sequences.shape
        num_classes = len(np.unique(y_labels))
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X_sequences, y_labels, test_size=0.2, random_state=42, stratify=y_labels
        )
        
        # Build model
        if model_type.lower() == "cnn":
            model = self._build_sequence_cnn(sequence_length, feature_dim, num_classes)
        else:
            model = self._build_sequence_gru(sequence_length, feature_dim, num_classes)
        
        # Train
        early_stopping = keras.callbacks.EarlyStopping(
            monitor='val_loss', patience=5, restore_best_weights=True
        )
        
        history = model.fit(
            X_train, y_train,
            validation_data=(X_test, y_test),
            epochs=epochs,
            batch_size=batch_size,
            callbacks=[early_stopping],
            verbose=1
        )
        
        # Evaluate
        y_pred_prob = model.predict(X_test, verbose=0)
        if num_classes == 2:
            y_pred = (y_pred_prob > 0.5).astype(int).flatten()
        else:
            y_pred = np.argmax(y_pred_prob, axis=1)
        
        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, average='weighted', zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, average='weighted', zero_division=0)),
            "f1": float(f1_score(y_test, y_pred, average='weighted', zero_division=0)),
            "training_time": time.time() - start_time
        }
        
        # Save model
        model_path = os.path.join(self.models_dir, f"{model_name}.h5")
        model.save(model_path)
        
        # Save metadata
        meta_path = os.path.join(self.models_dir, f"{model_name}_meta.json")
        with open(meta_path, 'w') as f:
            json.dump({
                "name": model_name,
                "type": model_type,
                "framework": "tensorflow",
                "sequence_length": sequence_length,
                "feature_dim": feature_dim,
                "num_classes": num_classes,
                "metrics": metrics,
                "timestamp": time.time()
            }, f, indent=4)
        
        logger.info(f"Sequence model {model_name} trained. Accuracy: {metrics['accuracy']:.4f}")
        
        return metrics
