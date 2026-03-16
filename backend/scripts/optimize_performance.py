
import os
import sys
import argparse
import logging
from typing import List

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.experiment_runner import ExperimentRunner, ExperimentConfig
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("OptimizePerformance")

def find_dataset(dataset_name: str, base_dir: str) -> str:
    """Search for dataset in common locations"""
    search_paths = [
        os.path.join(base_dir, "data", "datasets", dataset_name),
        os.path.join(base_dir, "data", "datasets", dataset_name.lower()),
        os.path.join(base_dir, "data", "datasets", f"{dataset_name}.csv"),
        os.path.join(base_dir, "data", "datasets", f"{dataset_name.lower()}.csv"),
    ]
    
    # Add variations for NSL-KDD
    if "nsl" in dataset_name.lower():
        search_paths.extend([
            os.path.join(base_dir, "data", "datasets", "NSL-KDD", "KDDTrain+.txt"),
            os.path.join(base_dir, "data", "datasets", "KDDTrain+.txt"),
        ])
        
    for path in search_paths:
        if os.path.exists(path):
            return path
            
    return None

def main():
    parser = argparse.ArgumentParser(description="Run optimized training for best performance")
    parser.add_argument("--dataset", type=str, choices=["nsl-kdd", "cic-ids2017"], required=True, help="Dataset to use")
    parser.add_argument("--epochs", type=int, default=100, help="Number of epochs for DL models")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    args = parser.parse_args()

    # Determine paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(script_dir)
    project_root = os.path.dirname(backend_dir)
    
    # Check if dataset exists
    dataset_path = find_dataset(args.dataset, project_root)
    if not dataset_path:
        logger.error(f"Dataset {args.dataset} not found in {project_root}/data/datasets/")
        logger.info(f"Please ensure you have placed the dataset files in {project_root}/data/datasets/")
        logger.info("For NSL-KDD: KDDTrain+.txt and KDDTest+.txt")
        logger.info("For CIC-IDS2017: A merged CSV file named cicids2017.csv")
        return

    logger.info(f"Found dataset at {dataset_path}")
    
    # Initialize Runner
    runner = ExperimentRunner(data_dir=os.path.join(project_root, "data"))
    
    # Configuration for Maximum Performance
    config = ExperimentConfig(
        experiment_name=f"best_performance_{args.dataset}",
        dataset_type=args.dataset,
        model_types=["lightgbm", "xgboost", "cnn", "transformer"], # Skip GRU as it's slow
        random_seed=42,
        
        # DL Optimization
        dl_epochs=args.epochs,
        dl_batch_size=args.batch_size,
        dl_learning_rate=0.0005, # Lower LR for stability
        
        # Transformer Optimization
        transformer_num_heads=8, # Increase heads
        transformer_ff_dim=256,  # Increase capacity
        transformer_num_blocks=3, # Deeper model
        
        # Advanced Features
        use_focal_loss=True,
        use_class_weights=True,
        use_one_hot=True,
        
        # Ensemble
        fusion_strategy="weighted"
    )
    
    logger.info("Starting optimized training run...")
    logger.info(f"Configuration: {config}")
    
    try:
        result = runner.run_experiment(config)
        
        print("\n" + "="*50)
        print(f"OPTIMIZATION RESULTS FOR {args.dataset.upper()}")
        print("="*50)
        print(f"Accuracy:  {result.accuracy:.4f}")
        print(f"Precision: {result.precision:.4f}")
        print(f"Recall:    {result.recall:.4f}")
        print(f"F1 Score:  {result.f1_score:.4f}")
        print("-" * 30)
        print("Model Breakdown:")
        for model, res in result.model_results.items():
            if "accuracy" in res:
                print(f"{model}: {res['accuracy']:.4f} (acc)")
            elif "error" in res:
                print(f"{model}: Error - {res['error']}")
        print("="*50)
        
        logger.info(f"Results saved to {runner.results_dir}")
        
    except Exception as e:
        logger.error(f"Experiment failed: {e}", exc_info=True)

if __name__ == "__main__":
    main()
