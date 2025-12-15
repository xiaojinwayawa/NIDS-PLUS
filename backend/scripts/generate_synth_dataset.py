import os
from pathlib import Path
import pandas as pd
from sklearn.datasets import make_classification

def main():
    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data" / "datasets"
    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / "synthetic_nids.csv"

    X, y = make_classification(
        n_samples=5000,
        n_features=20,
        n_informative=10,
        n_redundant=5,
        n_repeated=0,
        n_classes=2,
        weights=[0.7, 0.3],
        class_sep=1.5,
        flip_y=0.01,
        random_state=42,
    )

    columns = [f"f{i}" for i in range(X.shape[1])]
    df = pd.DataFrame(X, columns=columns)
    df["label"] = y
    df.to_csv(out_path, index=False)
    print(f"Written synthetic dataset to: {out_path}")

if __name__ == "__main__":
    main()

