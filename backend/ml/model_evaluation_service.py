import json
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)

from db.db_manager import SessionLocal
from db.models import DatasetModel
from logging_config import app_logger as logger
from ml.flow_aggregator import FlowFeatureExtractor
from ml.inference_engine import InferenceEngine


def _project_root() -> str:
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.dirname(backend_dir)


PROJECT_ROOT = _project_root()
EVAL_BASE_DIR = os.path.join(PROJECT_ROOT, "data", "model_evaluations")
RESULTS_DIR = os.path.join(EVAL_BASE_DIR, "results")
EXPORTS_DIR = os.path.join(EVAL_BASE_DIR, "exports")

for _path in (EVAL_BASE_DIR, RESULTS_DIR, EXPORTS_DIR):
    os.makedirs(_path, exist_ok=True)


_TASKS: Dict[str, Dict[str, Any]] = {}
_TASKS_LOCK = threading.RLock()


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _sanitize_filename(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name)
    return safe.strip("_") or "evaluation"


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_label(value: Any) -> str:
    text = str(value).strip()
    lowered = text.lower()
    if lowered in {"benign", "normal", "0"}:
        return "Normal"
    return text


def _is_normal_label(value: Any) -> bool:
    return _normalize_label(value) == "Normal"


def _detect_label_column(columns: List[str]) -> Optional[str]:
    # Exact match first (most common in CIC-IDS2017)
    for candidate in (" Label", "Label", "label", "class", "Class", "attack_cat"):
        if candidate in columns:
            return candidate
            
    # Fallback: case-insensitive match and aggressive stripping
    for col in columns:
        cleaned_col = str(col).strip().lower()
        if cleaned_col in ("label", "class", "attack_cat"):
            return col
            
    # Absolute fallback: if any column contains "label" ignoring case
    for col in columns:
        if "label" in str(col).lower():
            return col
            
    return None


def _normalize_dataset_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "cic" in text:
        return "cic-ids2017"
    if "nsl" in text or "kdd" in text:
        return "nsl-kdd"
    if "mixed" in text:
        return "mixed"
    return text


def _load_model_metadata(model_name: str) -> Dict[str, Any]:
    models_dir = os.path.join(PROJECT_ROOT, "models")
    meta_path = os.path.join(models_dir, f"{model_name}_meta.json")
    if not os.path.exists(meta_path):
        return {}
    try:
        return _read_json(meta_path)
    except Exception as exc:
        logger.warning("Failed to load evaluation model metadata for %s: %s", model_name, exc)
        return {}


def _resolve_csv_source(source_kind: str, source_value: str) -> Tuple[str, str, int]:
    if source_kind == "preset":
        if source_value.startswith("balanced/"):
            filename = source_value.split("balanced/")[1]
            path = os.path.join(PROJECT_ROOT, "data", "datasets", "balanced", filename)
        else:
            path = os.path.join(PROJECT_ROOT, "data", "datasets", "CIC-IDS2017", source_value)
        
        if not os.path.exists(path):
            raise FileNotFoundError(f"Preset CSV file not found: {path}")
        return path, source_value, _count_rows(path)

    if source_kind == "dataset":
        dataset_id = int(source_value)
        db = SessionLocal()
        try:
            dataset = db.query(DatasetModel).filter(DatasetModel.id == dataset_id).first()
            if not dataset:
                raise FileNotFoundError("Uploaded dataset not found")
            dataset_path = dataset.file_path
            if not os.path.isabs(dataset_path):
                dataset_path = os.path.join(PROJECT_ROOT, dataset_path)
            if not os.path.exists(dataset_path):
                raise FileNotFoundError("Uploaded dataset file missing on disk")
            return dataset_path, dataset.name, int(dataset.sample_count or _count_rows(dataset_path))
        finally:
            db.close()

    raise ValueError("Unsupported CSV source kind")


def _count_rows(csv_path: str) -> int:
    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        count = sum(1 for _ in f) - 1
    return max(count, 0)


def _task_public_view(task: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "result_id": task.get("result_id"),
        "status": task["status"],
        "progress": task["progress"],
        "stage": task["stage"],
        "message": task["message"],
        "created_at": task["created_at"],
        "started_at": task.get("started_at"),
        "finished_at": task.get("finished_at"),
        "processed_rows": task.get("processed_rows", 0),
        "total_rows": task.get("total_rows", 0),
        "evaluation_name": task.get("evaluation_name"),
        "model_name": task.get("model_name"),
        "model_type": task.get("model_type"),
        "csv_display_name": task.get("csv_display_name"),
        "source_keys": task.get("source_keys"),
        "logs": task.get("logs", [])[-20:],
    }


def _update_task(task_id: str, **kwargs: Any) -> None:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        task.update(kwargs)
        if "log" in kwargs and kwargs["log"]:
            task.setdefault("logs", []).append(f"{datetime.now().strftime('%H:%M:%S')} {kwargs['log']}")
            if len(task["logs"]) > 200:
                task["logs"] = task["logs"][-200:]


def _prepare_feature_frame(df: pd.DataFrame, label_column: str) -> pd.DataFrame:
    X = df.drop(columns=[label_column]).copy()
    expected_features = FlowFeatureExtractor().get_feature_names()
    
    # 清理列名前后的空格，防止脏数据列名导致对齐失败
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


def _label_mapping_from_metadata(meta: Dict[str, Any]) -> Dict[int, str]:
    raw_mapping = meta.get("label_mapping") or {}
    mapping: Dict[int, str] = {}
    for key, value in raw_mapping.items():
        try:
            mapping[int(key)] = _normalize_label(value)
        except Exception:
            continue
    if not mapping:
        mapping = {0: "Normal", 1: "Attack"}
    return mapping


def _predict_labels(
    inference_engine: InferenceEngine,
    model_name: str,
    features: np.ndarray,
    label_mapping: Dict[int, str],
) -> Tuple[List[str], List[float], List[int]]:
    model_key = f"{model_name}_latest"
    model_type = inference_engine.model_metadata.get(model_key, {}).get("type")
    
    if model_type == "fusion":
        target_models = inference_engine._get_target_models([model_name])
        model_results = {}
        model_class_preds = {}
        for sub_key in target_models:
            sub_probs = inference_engine._predict_single_model(sub_key, features)
            if sub_probs is not None:
                model_results[sub_key] = sub_probs
                if sub_probs.ndim > 1 and sub_probs.shape[1] > 1:
                    model_class_preds[sub_key] = np.argmax(sub_probs, axis=1)
                else:
                    model_class_preds[sub_key] = (sub_probs > 0.5).astype(int)
                    
        predictions, confidences, attack_types = inference_engine._apply_fusion(model_results, model_class_preds, features)
        return attack_types, confidences, predictions
        
    probs = inference_engine._predict_single_model(model_key, features)  # Reuse current model loading/preprocess path.
    if probs is None:
        raise RuntimeError("Model inference returned no probability output")

    if probs.ndim > 1 and probs.shape[1] > 1:
        class_indices = np.argmax(probs, axis=1).astype(int)
        confidences = np.max(probs, axis=1).astype(float).tolist()
        pred_labels = [_normalize_label(label_mapping.get(int(idx), str(idx))) for idx in class_indices]
        return pred_labels, confidences, class_indices.tolist()

    attack_probs = probs.flatten().astype(float)
    class_indices = (attack_probs > 0.5).astype(int)
    pred_labels = [_normalize_label(label_mapping.get(int(idx), "Attack" if idx else "Normal")) for idx in class_indices]
    confidences = attack_probs.tolist()
    return pred_labels, confidences, class_indices.tolist()


def _sorted_labels(labels: List[str]) -> List[str]:
    unique = sorted(set(labels))
    if "Normal" in unique:
        unique.remove("Normal")
        return ["Normal"] + unique
    return unique


def _calculate_metrics(
    true_labels: List[str],
    pred_labels: List[str],
    binary_true: List[int],
    binary_pred: List[int],
    duration_seconds: float,
    total_samples: int,
    is_binary_model: bool = False,
) -> Dict[str, Any]:
    # 方案 B: 降维逻辑已经挪到了上游数据收集阶段，这里只需要直接算分
    labels = _sorted_labels(true_labels + pred_labels)
    accuracy = float(accuracy_score(true_labels, pred_labels))

    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        true_labels, pred_labels, average="macro", zero_division=0
    )
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        true_labels, pred_labels, average="weighted", zero_division=0
    )

    cm_binary = confusion_matrix(binary_true, binary_pred, labels=[0, 1])
    if cm_binary.size == 4:
        tn, fp, fn, tp = cm_binary.ravel()
    else:
        tn = fp = fn = tp = 0
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0

    per_class_metrics = []
    p_scores, r_scores, f1_scores, supports = precision_recall_fscore_support(
        true_labels, pred_labels, labels=labels, zero_division=0
    )
    for idx, label in enumerate(labels):
        per_class_metrics.append(
            {
                "label": label,
                "precision": float(p_scores[idx]),
                "recall": float(r_scores[idx]),
                "f1": float(f1_scores[idx]),
                "support": int(supports[idx]),
            }
        )

    full_cm = confusion_matrix(true_labels, pred_labels, labels=labels)
    prediction_distribution = {
        label: int(sum(1 for item in pred_labels if item == label))
        for label in labels
    }
    benign_false_positive_counts: Dict[str, int] = {}
    for true_label, pred_label in zip(true_labels, pred_labels):
        if true_label == "Normal" and pred_label != "Normal":
            benign_false_positive_counts[pred_label] = benign_false_positive_counts.get(pred_label, 0) + 1

    return {
        "summary": {
            "accuracy": accuracy,
            "precision": float(weighted_p),
            "recall": float(weighted_r),
            "f1": float(weighted_f1),
            "macro_f1": float(macro_f1),
            "macro_precision": float(macro_p),
            "macro_recall": float(macro_r),
            "fpr": fpr,
            "fnr": fnr,
            "samples": int(total_samples),
            "duration_seconds": float(duration_seconds),
            "throughput_rows_per_second": float(total_samples / duration_seconds) if duration_seconds > 0 else 0.0,
        },
        "class_metrics": per_class_metrics,
        "confusion_matrix": {
            "labels": labels,
            "matrix": full_cm.astype(int).tolist(),
        },
        "binary_confusion_matrix": {
            "labels": ["Normal", "Attack"],
            "matrix": cm_binary.astype(int).tolist(),
        },
        "prediction_distribution": prediction_distribution,
        "benign_false_positive_analysis": [
            {"predicted_label": label, "count": int(count)}
            for label, count in sorted(benign_false_positive_counts.items(), key=lambda item: item[1], reverse=True)
        ],
    }


def _write_excel_report(result: Dict[str, Any]) -> str:
    try:
        import xlsxwriter  # noqa: F401
    except Exception as exc:
        raise RuntimeError("xlsxwriter dependency is required for Excel export") from exc

    file_name = f"{_sanitize_filename(result['evaluation_name'])}_{result['result_id']}.xlsx"
    export_path = os.path.join(EXPORTS_DIR, file_name)

    summary = result["summary"]
    class_metrics = result["class_metrics"]
    confusion = result["confusion_matrix"]

    with pd.ExcelWriter(export_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        title_fmt = workbook.add_format({"bold": True, "font_size": 14})
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#D9E2F3", "border": 1})
        percent_fmt = workbook.add_format({"num_format": "0.00%", "border": 1})
        summary_rows = [
            ("评估名称", result["evaluation_name"]),
            ("模型名称", result["model_name"]),
            ("模型类型", result["model_type"]),
            ("数据文件", result["csv_display_name"]),
            ("样本数", summary["samples"]),
            ("Accuracy", summary["accuracy"]),
            ("Precision", summary["precision"]),
            ("Recall", summary["recall"]),
            ("F1", summary["f1"]),
            ("Macro-F1", summary["macro_f1"]),
            ("FPR", summary["fpr"]),
            ("FNR", summary["fnr"]),
            ("耗时(秒)", summary["duration_seconds"]),
            ("吞吐量(条/秒)", summary["throughput_rows_per_second"]),
        ]
        summary_df = pd.DataFrame(summary_rows, columns=["指标", "数值"])
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        summary_ws = writer.sheets["Summary"]
        summary_ws.write(0, 0, "指标", header_fmt)
        summary_ws.write(0, 1, "数值", header_fmt)
        summary_ws.set_column("A:A", 22)
        summary_ws.set_column("B:B", 22)
        summary_ws.write("D1", "总体模型评估报告", title_fmt)

        percent_metric_names = {"Accuracy", "Precision", "Recall", "F1", "Macro-F1", "FPR", "FNR"}
        for row_idx, (metric_name, _) in enumerate(summary_rows, start=1):
            if metric_name in percent_metric_names:
                summary_ws.write_number(row_idx, 1, float(summary_df.iloc[row_idx - 1, 1]), percent_fmt)

        class_df = pd.DataFrame(class_metrics)
        class_df.to_excel(writer, sheet_name="Class Metrics", index=False)
        class_ws = writer.sheets["Class Metrics"]
        for col_idx, column in enumerate(class_df.columns):
            class_ws.write(0, col_idx, column, header_fmt)
        class_ws.set_column("A:A", 24)
        class_ws.set_column("B:D", 14)
        class_ws.set_column("E:E", 12)
        if not class_df.empty:
            for row_idx in range(1, len(class_df) + 1):
                for col_idx in (1, 2, 3):
                    class_ws.write_number(row_idx, col_idx, float(class_df.iloc[row_idx - 1, col_idx]), percent_fmt)

        cm_df = pd.DataFrame(confusion["matrix"], columns=confusion["labels"], index=confusion["labels"])
        cm_df.to_excel(writer, sheet_name="Confusion Matrix")
        cm_ws = writer.sheets["Confusion Matrix"]
        cm_ws.write(0, 0, "True/Pred", header_fmt)
        for idx, label in enumerate([""] + confusion["labels"]):
            if idx == 0:
                continue
            cm_ws.write(0, idx, label, header_fmt)
            cm_ws.write(idx, 0, confusion["labels"][idx - 1], header_fmt)
        cm_ws.set_column(0, len(confusion["labels"]), 16)

        charts_ws = workbook.add_worksheet("Charts")
        charts_ws.write("A1", "可视化图表", title_fmt)

        row_count = max(len(class_df), 1)
        bar_chart = workbook.add_chart({"type": "column"})
        bar_chart.add_series(
            {
                "name": "各类别 F1",
                "categories": ["Class Metrics", 1, 0, row_count, 0],
                "values": ["Class Metrics", 1, 3, row_count, 3],
                "fill": {"color": "#5B9BD5"},
                "border": {"color": "#2F5597"},
            }
        )
        bar_chart.set_title({"name": "各类别 F1 对比"})
        bar_chart.set_y_axis({"min": 0, "max": 1, "num_format": "0%"})
        bar_chart.set_size({"width": 720, "height": 360})
        charts_ws.insert_chart("A3", bar_chart)

        pie_chart = workbook.add_chart({"type": "pie"})
        labels = list(result["prediction_distribution"].keys())
        counts = list(result["prediction_distribution"].values())
        dist_df = pd.DataFrame({"Label": labels, "Count": counts})
        dist_df.to_excel(writer, sheet_name="Prediction Distribution", index=False)
        dist_ws = writer.sheets["Prediction Distribution"]
        for col_idx, column in enumerate(dist_df.columns):
            dist_ws.write(0, col_idx, column, header_fmt)
        pie_chart.add_series(
            {
                "name": "预测类别分布",
                "categories": ["Prediction Distribution", 1, 0, len(dist_df), 0],
                "values": ["Prediction Distribution", 1, 1, len(dist_df), 1],
                "data_labels": {"percentage": True, "category": True},
            }
        )
        pie_chart.set_title({"name": "预测类别分布"})
        pie_chart.set_size({"width": 520, "height": 320})
        charts_ws.insert_chart("A22", pie_chart)

    return export_path


def list_csv_sources() -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []

    # Preset dir
    preset_dirs = [
        os.path.join(PROJECT_ROOT, "data", "datasets", "CIC-IDS2017"),
        os.path.join(PROJECT_ROOT, "data", "datasets", "balanced")
    ]
    
    for p_dir in preset_dirs:
        if os.path.exists(p_dir):
            for filename in sorted(os.listdir(p_dir)):
                if filename.endswith(".csv") and not filename.startswith("processed_"):
                    csv_path = os.path.join(p_dir, filename)
                    try:
                        row_count = _count_rows(csv_path)
                    except Exception:
                        row_count = 0
                    
                    # For preset dir we prefix balanced files
                    source_value = filename
                    if "balanced" in p_dir:
                        source_value = f"balanced/{filename}"
                    
                    sources.append(
                        {
                            "source_kind": "preset",
                            "source_value": source_value,
                            "display_name": source_value,
                            "dataset_type": "CIC-IDS2017",
                            "sample_count": row_count,
                        }
                    )

    db = SessionLocal()
    try:
        datasets = db.query(DatasetModel).filter(DatasetModel.file_path.like("%.csv")).order_by(DatasetModel.created_at.desc()).all()
        for dataset in datasets:
            if str(dataset.type).lower() not in {"cic-ids2017", "cic-ids", "custom"}:
                continue
            sources.append(
                {
                    "source_kind": "dataset",
                    "source_value": str(dataset.id),
                    "display_name": dataset.name,
                    "dataset_type": dataset.type,
                    "sample_count": int(dataset.sample_count or 0),
                }
            )
    finally:
        db.close()

    return sources


def create_evaluation_task(config: Dict[str, Any]) -> Dict[str, Any]:
    task_id = uuid.uuid4().hex
    result_id = uuid.uuid4().hex
    task = {
        "task_id": task_id,
        "result_id": result_id,
        "status": "pending",
        "progress": 0,
        "stage": "pending",
        "message": "任务已创建，等待执行",
        "created_at": _now_iso(),
        "started_at": None,
        "finished_at": None,
        "processed_rows": 0,
        "total_rows": 0,
        "logs": [],
        "stop_requested": False,
        **config,
    }
    with _TASKS_LOCK:
        _TASKS[task_id] = task

    worker = threading.Thread(target=_run_evaluation_task, args=(task_id,), daemon=True)
    worker.start()
    return _task_public_view(task)


def get_evaluation_task(task_id: str) -> Dict[str, Any]:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if not task:
            raise KeyError("Task not found")
        return _task_public_view(task)


def stop_evaluation_task(task_id: str) -> Dict[str, Any]:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if not task:
            raise KeyError("Task not found")
        task["stop_requested"] = True
        task["message"] = "已请求停止，等待当前批次结束"
        task.setdefault("logs", []).append(f"{datetime.now().strftime('%H:%M:%S')} 收到停止请求")
        return _task_public_view(task)


def list_evaluation_results() -> List[Dict[str, Any]]:
    results = []
    for filename in sorted(os.listdir(RESULTS_DIR), reverse=True):
        if not filename.endswith(".json"):
            continue
        try:
            payload = _read_json(os.path.join(RESULTS_DIR, filename))
            results.append(payload)
        except Exception as exc:
            logger.warning("Failed to read evaluation result %s: %s", filename, exc)
    results.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return results


def get_evaluation_result(result_id: str) -> Dict[str, Any]:
    result_path = os.path.join(RESULTS_DIR, f"{result_id}.json")
    if not os.path.exists(result_path):
        raise FileNotFoundError("Evaluation result not found")
    return _read_json(result_path)


def delete_evaluation_result(result_id: str) -> None:
    result = get_evaluation_result(result_id)
    result_path = os.path.join(RESULTS_DIR, f"{result_id}.json")
    if os.path.exists(result_path):
        os.remove(result_path)

    export_path = result.get("export_path")
    if export_path and os.path.exists(export_path):
        os.remove(export_path)


def export_evaluation_result_excel(result_id: str) -> str:
    result = get_evaluation_result(result_id)
    export_path = _write_excel_report(result)
    result["export_path"] = export_path
    _write_json(os.path.join(RESULTS_DIR, f"{result_id}.json"), result)
    return export_path


def _run_evaluation_task(task_id: str) -> None:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return

    start_time = time.time()
    _update_task(
        task_id,
        status="running",
        progress=2,
        stage="initializing",
        message="正在初始化评估任务",
        started_at=_now_iso(),
        log="开始初始化评估任务",
    )

    try:
        source_keys = task.get("source_keys", [])
        if not source_keys:
            raise ValueError("至少需要选择一个 CSV 文件")
            
        csv_files = []
        total_rows = 0
        for sk in source_keys:
            s_kind, s_value = sk.split(":", 1)
            csv_path, csv_display_name, rows = _resolve_csv_source(s_kind, s_value)
            csv_files.append({
                "path": csv_path,
                "display_name": csv_display_name,
                "rows": rows
            })
            total_rows += rows
            
        display_names_str = ", ".join([f["display_name"] for f in csv_files])
        _update_task(
            task_id,
            progress=8,
            stage="loading_file",
            message="正在初始化评估任务",
            csv_display_name=display_names_str,
            total_rows=total_rows,
            log=f"已加载 {len(csv_files)} 个评估文件，总行数 {total_rows}",
        )

        meta = _load_model_metadata(task["model_name"])
        dataset_type = _normalize_dataset_type(task.get("dataset_type") or meta.get("dataset_type"))
        if dataset_type == "nsl-kdd":
            raise ValueError("当前总体模型评估页面仅支持 CIC-IDS2017 体系模型")
        if dataset_type not in {"", "cic-ids2017", "mixed"}:
            raise ValueError("当前模型的数据集体系无法确认，暂不支持在总体模型评估中运行")

        inference_engine = InferenceEngine()
        if not inference_engine.load_model(task["model_name"], task["model_type"]):
            raise RuntimeError("模型加载失败，无法开始总体模型评估")

        label_mapping = _label_mapping_from_metadata(inference_engine.model_metadata.get(f"{task['model_name']}_latest", meta))
        is_binary_model = len(label_mapping) <= 2
        _update_task(
            task_id,
            progress=15,
            stage="loading_model",
            message="正在初始化评估任务",
            log=f"模型加载完成: {task['model_name']} ({task['model_type']})",
        )

        label_column = task.get("label_column")
        true_labels_eval: List[str] = []
        pred_labels_eval: List[str] = []
        binary_true: List[int] = []
        binary_pred: List[int] = []
        processed_rows = 0
        batch_size = int(task.get("batch_size", 2048))

        global_chunk_index = 0
        for csv_file_info in csv_files:
            chunks = pd.read_csv(csv_file_info["path"], chunksize=batch_size)
            for chunk in chunks:
                global_chunk_index += 1
                with _TASKS_LOCK:
                    current_task = _TASKS.get(task_id)
                    if current_task and current_task.get("stop_requested"):
                        _update_task(
                            task_id,
                            status="stopped",
                            progress=min(current_task.get("progress", 0), 99),
                            stage="stopped",
                            message="评估任务已停止",
                            finished_at=_now_iso(),
                            log="任务在处理中被用户停止",
                        )
                        return

                if not label_column:
                    label_column = _detect_label_column(chunk.columns.tolist())
                    
                # If label_column is a number (string representation of an integer), treat it as an index
                if label_column and str(label_column).isdigit():
                    col_idx = int(label_column)
                    if col_idx < 0 or col_idx >= len(chunk.columns):
                        raise ValueError(f"标签列索引 {col_idx} 超出范围 (0-{len(chunk.columns)-1})")
                    label_column = chunk.columns[col_idx]
                # Support Excel column letters like "CA"
                elif label_column and str(label_column).isalpha() and len(str(label_column)) <= 3 and str(label_column).isupper():
                    def col2num(col):
                        num = 0
                        for c in col:
                            num = num * 26 + (ord(c.upper()) - ord('A')) + 1
                        return num - 1
                    col_idx = col2num(str(label_column))
                    if col_idx < 0 or col_idx >= len(chunk.columns):
                        raise ValueError(f"标签列索引 {label_column} ({col_idx}) 超出范围 (0-{len(chunk.columns)-1})")
                    label_column = chunk.columns[col_idx]
                    
                if not label_column or label_column not in chunk.columns:
                    raise ValueError(f"CSV 中未找到可用标签列。列名: {chunk.columns.tolist()}")

                labels_raw = chunk[label_column].apply(_normalize_label).tolist()
                feature_frame = _prepare_feature_frame(chunk, label_column)
                pred_labels_chunk, _, pred_indices = _predict_labels(
                    inference_engine=inference_engine,
                    model_name=task["model_name"],
                    features=feature_frame.values.astype(np.float32),
                    label_mapping=label_mapping,
                )

                if is_binary_model:
                    # 对于二分类模型，直接使用二元转换，不要试图找回原始攻击标签
                    true_eval_chunk = ["Normal" if _is_normal_label(item) else "Attack" for item in labels_raw]
                    # 我们之前在 _predict_labels 里把二分类预测强行转换成了 attack_types，它可能包含 "Generic Attack (Fusion)"
                    # 这里我们统一将其降维回 "Attack" 以保证匹配，注意：预测的可能也是 'Normal'
                    pred_eval_chunk = ["Normal" if _is_normal_label(p) else "Attack" for p in pred_labels_chunk]
                else:
                    true_eval_chunk = labels_raw
                    pred_eval_chunk = pred_labels_chunk

                true_labels_eval.extend(true_eval_chunk)
                pred_labels_eval.extend(pred_eval_chunk)
                binary_true.extend([0 if _is_normal_label(item) else 1 for item in labels_raw])
                binary_pred.extend([0 if label == "Normal" else 1 for label in pred_eval_chunk])

                processed_rows += len(chunk)
                progress = 20 + int(70 * (processed_rows / max(total_rows, 1)))
                _update_task(
                    task_id,
                    progress=min(progress, 92),
                    stage="running",
                    message=f"正在处理 {csv_file_info['display_name']} 第 {global_chunk_index} 个批次",
                    processed_rows=processed_rows,
                    log=f"已完成 {processed_rows}/{total_rows} 行",
                )

        _update_task(
            task_id,
            progress=95,
            stage="calculating",
            message="正在统计总体评估指标",
            processed_rows=processed_rows,
            log="数据推理完成，开始计算指标",
        )

        duration_seconds = time.time() - start_time
        metrics = _calculate_metrics(
            true_labels=true_labels_eval,
            pred_labels=pred_labels_eval,
            binary_true=binary_true,
            binary_pred=binary_pred,
            duration_seconds=duration_seconds,
            total_samples=len(true_labels_eval),
            is_binary_model=is_binary_model,
        )

        result = {
            "result_id": task["result_id"],
            "task_id": task_id,
            "evaluation_name": task["evaluation_name"],
            "model_name": task["model_name"],
            "model_type": task["model_type"],
            "dataset_type": "CIC-IDS2017",
            "csv_display_name": display_names_str,
            "source_keys": task.get("source_keys"),
            "label_column": label_column,
            "created_at": _now_iso(),
            "summary": metrics["summary"],
            "class_metrics": metrics["class_metrics"],
            "confusion_matrix": metrics["confusion_matrix"],
            "binary_confusion_matrix": metrics["binary_confusion_matrix"],
            "prediction_distribution": metrics["prediction_distribution"],
            "benign_false_positive_analysis": metrics["benign_false_positive_analysis"],
            "export_path": None,
        }

        result_path = os.path.join(RESULTS_DIR, f"{task['result_id']}.json")
        _write_json(result_path, result)

        _update_task(
            task_id,
            status="completed",
            progress=100,
            stage="completed",
            message="总体模型评估已完成",
            finished_at=_now_iso(),
            result_id=task["result_id"],
            processed_rows=processed_rows,
            log="评估结果已保存",
        )
    except Exception as exc:
        import traceback
        error_details = traceback.format_exc()
        logger.error("Model evaluation task %s failed: %s\n%s", task_id, exc, error_details)
        _update_task(
            task_id,
            status="failed",
            progress=100,
            stage="failed",
            message=f"{exc} | 详细错误: {error_details[:500]}",
            finished_at=_now_iso(),
            log=f"任务失败: {exc}",
        )

