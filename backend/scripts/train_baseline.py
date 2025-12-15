from pathlib import Path
import sys

def main():
    project_root = Path(__file__).resolve().parents[1]
    # Ensure backend root is on path to import ml.*
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    from ml.trainer import TrainingManager
    dataset_path = project_root / "data" / "datasets" / "synthetic_nids.csv"
    models_dir = project_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    tm = TrainingManager(models_dir=str(models_dir))
    params = {'objective': 'binary', 'verbosity': -1, 'seed': 42}
    metrics = tm.train_model("lightgbm", str(dataset_path), params, "lightgbm_baseline")
    print("Training completed.")
    print(metrics)
    print(f"Model saved to: {models_dir / 'lightgbm_baseline.joblib'}")

if __name__ == "__main__":
    main()
