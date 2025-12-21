"""
Baseline Model Training Script
Trains LightGBM and XGBoost models on CIC-IDS2017 dataset
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from ml.trainer import TrainingManager
from logging_config import app_logger as logger

def prepare_cicids_data():
    """Prepare CIC-IDS2017 dataset for training"""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                           "data", "datasets", "CIC-IDS2017")
    
    # Use Tuesday data which contains attacks (FTP-Patator, SSH-Patator)
    csv_file = os.path.join(data_dir, "Tuesday-WorkingHours.pcap_ISCX.csv")
    
    if not os.path.exists(csv_file):
        logger.error(f"Dataset not found: {csv_file}")
        return None
        
    logger.info(f"Loading CIC-IDS2017 data from {csv_file}")
    
    try:
        df = pd.read_csv(csv_file)
        
        # Clean column names (remove spaces)
        df.columns = df.columns.str.strip()
        
        # Handle Label column
        if 'Label' in df.columns:
            # Convert to binary: BENIGN=0, Attack=1
            df['label'] = (df['Label'] != 'BENIGN').astype(int)
            df = df.drop(columns=['Label'])
        
        # Remove infinite values and NaN
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.dropna()
        
        # Save processed data
        output_path = os.path.join(data_dir, "processed_tuesday.csv")
        df.to_csv(output_path, index=False)
        logger.info(f"Processed data saved to {output_path}")
        logger.info(f"Dataset shape: {df.shape}, Attack ratio: {df['label'].mean():.4f}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error preparing data: {e}")
        return None

def main():
    """Main training function"""
    logger.info("=" * 60)
    logger.info("Starting Baseline Model Training")
    logger.info("=" * 60)
    
    # Prepare data
    dataset_path = prepare_cicids_data()
    if not dataset_path:
        logger.error("Failed to prepare dataset")
        return
    
    # Initialize trainer
    models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models")
    trainer = TrainingManager(models_dir=models_dir)
    
    # Train LightGBM
    logger.info("\n" + "=" * 40)
    logger.info("Training LightGBM model...")
    logger.info("=" * 40)
    
    lgb_params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'verbosity': -1,
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.9
    }
    
    try:
        lgb_metrics = trainer.train_model(
            model_type="lightgbm",
            dataset_path=dataset_path,
            params=lgb_params,
            model_name="lightgbm_cicids"
        )
        logger.info(f"LightGBM Results: {lgb_metrics}")
    except Exception as e:
        logger.error(f"LightGBM training failed: {e}")
    
    # Train XGBoost
    logger.info("\n" + "=" * 40)
    logger.info("Training XGBoost model...")
    logger.info("=" * 40)
    
    xgb_params = {
        'objective': 'binary:logistic',
        'eval_metric': 'logloss',
        'max_depth': 6,
        'learning_rate': 0.1,
        'subsample': 0.8
    }
    
    try:
        xgb_metrics = trainer.train_model(
            model_type="xgboost",
            dataset_path=dataset_path,
            params=xgb_params,
            model_name="xgboost_cicids"
        )
        logger.info(f"XGBoost Results: {xgb_metrics}")
    except Exception as e:
        logger.error(f"XGBoost training failed: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("Baseline Model Training Complete!")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
