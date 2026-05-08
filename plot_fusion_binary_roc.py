#!/usr/bin/env python3
"""
为指定的三个模型绘制 CIC-IDS2017 原始数据上的二分类 ROC 曲线。

使用模型:
- fusion_allkinds_fusion_lightgbm
- fusion_allkinds_fusion_cnn
- fusion_allkinds_fusion

使用数据:
- data/datasets/CIC-IDS2017/ 下周一到周五的 8 个原始 CSV
- 不使用 balanced 数据

运行示例:
python plot_fusion_binary_roc.py
python plot_fusion_binary_roc.py --models-dir C:\path\to\models
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import auc, roc_curve


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from ml.flow_aggregator import FlowFeatureExtractor
from ml.inference_engine import InferenceEngine


RAW_CIC_IDS2017_FILES = [
    "Monday-WorkingHours.pcap_ISCX.csv",
    "Tuesday-WorkingHours.pcap_ISCX.csv",
    "Wednesday-workingHours.pcap_ISCX.csv",
    "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
    "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv",
    "Friday-WorkingHours-Morning.pcap_ISCX.csv",
    "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv",
    "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv",
]

MODEL_SPECS = [
    {
        "name": "fusion_allkinds_fusion_lightgbm",
        "type": "lightgbm",
        "display_name": "Fusion-LightGBM",
        "color": "#1f77b4",
    },
    {
        "name": "fusion_allkinds_fusion_cnn",
        "type": "cnn",
        "display_name": "Fusion-1D-CNN",
        "color": "#ff7f0e",
    },
    {
        "name": "fusion_allkinds_fusion",
        "type": "fusion",
        "display_name": "Fusion Model",
        "color": "#2ca02c",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="为三个指定模型绘制 CIC-IDS2017 原始数据的二分类 ROC 曲线。"
    )
    parser.add_argument(
        "--models-dir",
        default=os.path.join(PROJECT_ROOT, "models"),
        help="模型目录，默认使用项目根目录下的 models。",
    )
    parser.add_argument(
        "--data-dir",
        default=os.path.join(PROJECT_ROOT, "data", "datasets", "CIC-IDS2017"),
        help="CIC-IDS2017 原始 CSV 所在目录。",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(PROJECT_ROOT, "roc_outputs"),
        help="ROC 图片和汇总文件输出目录。",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4096,
        help="分块推理时的批大小。",
    )
    parser.add_argument(
        "--max-rows-per-file",
        type=int,
        default=None,
        help="每个 CSV 最多读取多少行。默认不限制，用于完整评估。",
    )
    return parser.parse_args()


def normalize_label(value: object) -> str:
    text = str(value).strip()
    lowered = text.lower()
    if lowered in {"benign", "normal", "0"}:
        return "Normal"
    return text


def is_normal_label(value: object) -> bool:
    return normalize_label(value) == "Normal"


def detect_label_column(columns: Iterable[str]) -> Optional[str]:
    columns = list(columns)
    for candidate in (" Label", "Label", "label", "class", "Class", "attack_cat"):
        if candidate in columns:
            return candidate

    for col in columns:
        if str(col).strip().lower() in {"label", "class", "attack_cat"}:
            return col

    for col in columns:
        if "label" in str(col).lower():
            return col

    return None


def prepare_feature_frame(df: pd.DataFrame, label_column: str) -> pd.DataFrame:
    X = df.drop(columns=[label_column]).copy()
    expected_features = FlowFeatureExtractor().get_feature_names()

    X.columns = X.columns.str.strip()

    for col in expected_features:
        if col not in X.columns:
            X[col] = 0

    X = X[expected_features]

    for col in X.select_dtypes(include=["object"]).columns:
        X[col] = X[col].astype("category").cat.codes

    X = X.fillna(0)
    X = X.replace([np.inf, -np.inf], 0)
    return X


def load_label_mapping(engine: InferenceEngine, model_name: str) -> Dict[int, str]:
    model_key = f"{model_name}_latest"
    meta = engine.model_metadata.get(model_key, {})
    raw_mapping = meta.get("label_mapping") or {}
    mapping: Dict[int, str] = {}

    for key, value in raw_mapping.items():
        try:
            mapping[int(key)] = normalize_label(value)
        except Exception:
            continue

    if not mapping:
        mapping = {0: "Normal", 1: "Attack"}

    return mapping


def get_normal_class_index(label_mapping: Dict[int, str]) -> int:
    for idx, label in label_mapping.items():
        if normalize_label(label).lower() in {"normal", "benign"}:
            return int(idx)
    return 0


def convert_probs_to_attack_scores(
    probs: np.ndarray,
    label_mapping: Dict[int, str],
) -> np.ndarray:
    probs = np.asarray(probs)

    if probs.ndim == 1:
        return probs.astype(float)

    if probs.ndim == 2 and probs.shape[1] == 1:
        return probs.reshape(-1).astype(float)

    normal_idx = get_normal_class_index(label_mapping)
    if normal_idx >= probs.shape[1]:
        normal_idx = 0

    return (1.0 - probs[:, normal_idx]).astype(float)


def predict_attack_scores(
    engine: InferenceEngine,
    model_name: str,
    model_type: str,
    features: np.ndarray,
) -> np.ndarray:
    if model_type == "fusion":
        result = engine.predict_batch(features, model_names=[model_name])
        if "error" in result:
            raise RuntimeError(f"{model_name} 推理失败: {result['error']}")
        return np.asarray(result["confidences"], dtype=float)

    model_key = f"{model_name}_latest"
    probs = engine._predict_single_model(model_key, features)
    if probs is None:
        raise RuntimeError(f"{model_name} 未返回有效概率输出")

    label_mapping = load_label_mapping(engine, model_name)
    return convert_probs_to_attack_scores(np.asarray(probs), label_mapping)


def resolve_csv_paths(data_dir: str) -> List[str]:
    missing_files = []
    csv_paths = []

    for filename in RAW_CIC_IDS2017_FILES:
        path = os.path.join(data_dir, filename)
        if not os.path.exists(path):
            missing_files.append(path)
        else:
            csv_paths.append(path)

    if missing_files:
        missing_text = "\n".join(missing_files)
        raise FileNotFoundError(f"以下原始数据文件不存在:\n{missing_text}")

    return csv_paths


def maybe_trim_chunk(chunk: pd.DataFrame, remaining_rows: Optional[int]) -> pd.DataFrame:
    if remaining_rows is None:
        return chunk
    if remaining_rows <= 0:
        return chunk.iloc[0:0]
    return chunk.iloc[:remaining_rows]


def evaluate_single_model(
    engine: InferenceEngine,
    model_name: str,
    model_type: str,
    csv_paths: List[str],
    batch_size: int,
    max_rows_per_file: Optional[int],
) -> Tuple[np.ndarray, np.ndarray]:
    y_true_parts: List[np.ndarray] = []
    y_score_parts: List[np.ndarray] = []

    print(f"\n[INFO] 开始评估模型: {model_name} ({model_type})")

    for csv_path in csv_paths:
        filename = os.path.basename(csv_path)
        print(f"[INFO] 读取文件: {filename}")

        rows_remaining = max_rows_per_file
        chunk_iter = pd.read_csv(csv_path, chunksize=batch_size)

        for chunk_index, chunk in enumerate(chunk_iter, start=1):
            chunk = maybe_trim_chunk(chunk, rows_remaining)
            if chunk.empty:
                break

            label_column = detect_label_column(chunk.columns.tolist())
            if not label_column:
                raise ValueError(f"未在 {filename} 中识别到标签列")

            labels_raw = chunk[label_column].apply(normalize_label).tolist()
            y_true = np.asarray(
                [0 if is_normal_label(item) else 1 for item in labels_raw],
                dtype=np.int8,
            )

            feature_frame = prepare_feature_frame(chunk, label_column)
            features = feature_frame.values.astype(np.float32)
            y_score = predict_attack_scores(engine, model_name, model_type, features)

            if y_true.shape[0] != y_score.shape[0]:
                raise RuntimeError(
                    f"{model_name} 在 {filename} 第 {chunk_index} 个分块上输出数量不一致: "
                    f"y_true={y_true.shape[0]}, y_score={y_score.shape[0]}"
                )

            y_true_parts.append(y_true)
            y_score_parts.append(np.clip(y_score.astype(float), 0.0, 1.0))

            if rows_remaining is not None:
                rows_remaining -= len(chunk)
                if rows_remaining <= 0:
                    break

            if chunk_index % 20 == 0:
                total_rows = int(sum(part.shape[0] for part in y_true_parts))
                print(f"[INFO] {model_name} 已累计处理 {total_rows} 行")

    if not y_true_parts or not y_score_parts:
        raise RuntimeError(f"{model_name} 未生成任何可用的评估数据")

    y_true_all = np.concatenate(y_true_parts)
    y_score_all = np.concatenate(y_score_parts)
    return y_true_all, y_score_all


def write_auc_summary(summary_rows: List[Dict[str, object]], output_dir: str) -> Tuple[str, str]:
    csv_path = os.path.join(output_dir, "roc_auc_summary.csv")
    json_path = os.path.join(output_dir, "roc_auc_summary.json")

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=["model_name", "model_type", "display_name", "auc", "samples"],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(summary_rows, json_file, ensure_ascii=False, indent=2)

    return csv_path, json_path


def plot_combined_roc(results: List[Dict[str, object]], output_dir: str) -> str:
    plt.figure(figsize=(9, 7))

    for item in results:
        plt.plot(
            item["fpr"],
            item["tpr"],
            color=item["color"],
            linewidth=2,
            label=f"{item['display_name']} (AUC = {item['auc']:.4f})",
        )

    plt.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1.5, label="Random")
    plt.xlim(0.0, 1.0)
    plt.ylim(0.0, 1.05)
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("Binary ROC Curves on CIC-IDS2017 Raw Data")
    plt.legend(loc="lower right")
    plt.grid(True, linestyle="--", alpha=0.3)
    plt.tight_layout()

    output_path = os.path.join(output_dir, "fusion_binary_roc_comparison.png")
    plt.savefig(output_path, dpi=300)
    plt.close()
    return output_path


def ensure_model_dir_exists(models_dir: str) -> None:
    if not os.path.exists(models_dir):
        raise FileNotFoundError(
            f"模型目录不存在: {models_dir}\n"
            f"如果您的模型不在项目根目录的 models 下，请运行时加上 --models-dir 参数。"
        )


def main() -> int:
    args = parse_args()

    ensure_model_dir_exists(args.models_dir)
    os.makedirs(args.output_dir, exist_ok=True)

    csv_paths = resolve_csv_paths(args.data_dir)
    print("[INFO] 将使用以下原始数据文件:")
    for path in csv_paths:
        print(f"  - {os.path.basename(path)}")

    engine = InferenceEngine(models_dir=args.models_dir)

    results: List[Dict[str, object]] = []
    summary_rows: List[Dict[str, object]] = []

    for spec in MODEL_SPECS:
        print(f"\n[INFO] 正在加载模型: {spec['name']}")
        if not engine.load_model(spec["name"], spec["type"]):
            raise RuntimeError(
                f"模型加载失败: {spec['name']} ({spec['type']})\n"
                f"当前 models_dir 为: {args.models_dir}\n"
                f"如果这些模型实际存放在别的目录，请使用 --models-dir 指向正确位置。"
            )

        y_true, y_score = evaluate_single_model(
            engine=engine,
            model_name=spec["name"],
            model_type=spec["type"],
            csv_paths=csv_paths,
            batch_size=args.batch_size,
            max_rows_per_file=args.max_rows_per_file,
        )

        fpr, tpr, _ = roc_curve(y_true, y_score)
        roc_auc = float(auc(fpr, tpr))

        results.append(
            {
                "model_name": spec["name"],
                "model_type": spec["type"],
                "display_name": spec["display_name"],
                "color": spec["color"],
                "fpr": fpr,
                "tpr": tpr,
                "auc": roc_auc,
                "samples": int(y_true.shape[0]),
            }
        )
        summary_rows.append(
            {
                "model_name": spec["name"],
                "model_type": spec["type"],
                "display_name": spec["display_name"],
                "auc": round(roc_auc, 6),
                "samples": int(y_true.shape[0]),
            }
        )

        print(f"[INFO] {spec['display_name']} AUC = {roc_auc:.6f}")

    image_path = plot_combined_roc(results, args.output_dir)
    csv_summary_path, json_summary_path = write_auc_summary(summary_rows, args.output_dir)

    print("\n[INFO] ROC 曲线绘制完成")
    print(f"[INFO] 图片输出: {image_path}")
    print(f"[INFO] CSV 汇总: {csv_summary_path}")
    print(f"[INFO] JSON 汇总: {json_summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
