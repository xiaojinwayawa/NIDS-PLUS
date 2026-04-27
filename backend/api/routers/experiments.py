"""
Experiments API Router
Provides endpoints for running and managing ML/DL experiments.
"""
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from auth import get_current_user, TokenData
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from datetime import datetime
import os
import json
import uuid
import threading
import shutil
import re

from ml.experiment_runner import ExperimentRunner, ExperimentConfig, DatasetPreprocessor
from logging_config import app_logger as logger
from db.db_manager import SessionLocal
from db.models import ModelModel, ModelMetricModel

router = APIRouter()

# Get project directories
_current_file = os.path.abspath(__file__)
_routers_dir = os.path.dirname(_current_file)
_api_dir = os.path.dirname(_routers_dir)
_backend_dir = os.path.dirname(_api_dir)
_project_root = os.path.dirname(_backend_dir)
_results_dir = os.path.join(_project_root, "data", "experiments")
_models_root_dir = os.path.join(_project_root, "models")
_experiment_models_dir = os.path.join(_models_root_dir, "experiments")

# Store for async experiment tasks
_experiment_tasks: Dict[str, Dict[str, Any]] = {}


def _resolve_experiment_model_path(experiment_id: str, model_type: str, stored_path: Optional[str] = None) -> Optional[str]:
    candidate_paths = []

    if stored_path:
        if os.path.isabs(stored_path):
            candidate_paths.append(stored_path)
        else:
            candidate_paths.append(os.path.join(_project_root, stored_path))

    for ext in [".joblib", ".keras", ".h5"]:
        candidate_paths.append(os.path.join(_experiment_models_dir, experiment_id, f"{model_type}{ext}"))
        candidate_paths.append(os.path.join(_models_root_dir, experiment_id, f"{model_type}{ext}"))  # legacy

    seen = set()
    for path in candidate_paths:
        if not path:
            continue
        normalized = os.path.normpath(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.path.exists(normalized):
            return normalized

    return candidate_paths[0] if candidate_paths else None


def _resolve_formal_model_meta_path(file_path: str) -> Optional[str]:
    if not file_path:
        return None

    full_path = file_path if os.path.isabs(file_path) else os.path.join(_project_root, file_path)
    dir_name = os.path.dirname(full_path)
    base_name = os.path.splitext(os.path.basename(full_path))[0]
    meta_path = os.path.join(dir_name, f"{base_name}_meta.json")
    return meta_path if os.path.exists(meta_path) else None


def _build_promoted_models_index() -> Dict[str, Dict[str, Dict[str, Any]]]:
    promoted_index: Dict[str, Dict[str, Dict[str, Any]]] = {}
    db_session = SessionLocal()
    try:
        models = db_session.query(ModelModel).all()
        for model in models:
            meta_path = _resolve_formal_model_meta_path(model.file_path)
            if not meta_path:
                continue

            try:
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read model metadata for promoted lookup: {e}")
                continue

            if meta.get("source") != "promoted_experiment":
                continue

            experiment_id = meta.get("experiment_id")
            model_type = meta.get("type") or model.type
            if not experiment_id or not model_type:
                continue

            promoted_index.setdefault(experiment_id, {})[model_type] = {
                "model_id": model.id,
                "model_name": model.name,
                "file_path": model.file_path
            }
    finally:
        db_session.close()

    return promoted_index


def _build_fusion_result(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fusion_metrics = data.get("model_results", {}).get("fusion")
    model_types = data.get("config", {}).get("model_types", [])
    if not fusion_metrics or len(model_types) <= 1:
        return None

    return {
        "display_name": "融合结果",
        "strategy": data.get("config", {}).get("fusion_strategy", "weighted"),
        "source_models": model_types,
        "metrics": fusion_metrics
    }


def _build_experiment_models(data: Dict[str, Any], promoted_index: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None) -> List[Dict[str, Any]]:
    experiment_id = data.get("experiment_id")
    experiment_name = data.get("config", {}).get("experiment_name", "Unnamed")
    model_types = data.get("config", {}).get("model_types", [])
    stored_paths = data.get("model_paths", {})
    experiment_promoted = (promoted_index or {}).get(experiment_id, {})
    model_results = data.get("model_results", {})

    experiment_models = []
    
    # Include fusion as a model type if it exists in the results
    types_to_process = list(model_types)
    if "fusion" in model_results and "fusion" not in types_to_process:
        types_to_process.append("fusion")
        
    for model_type in types_to_process:
        resolved_path = None
        if experiment_id:
            resolved_path = _resolve_experiment_model_path(
                experiment_id=experiment_id,
                model_type=model_type,
                stored_path=stored_paths.get(model_type)
            )

        relative_model_name = None
        if resolved_path:
            try:
                relative_model_name = os.path.splitext(os.path.relpath(resolved_path, _models_root_dir))[0].replace("\\", "/")
            except ValueError:
                relative_model_name = os.path.splitext(os.path.basename(resolved_path))[0]

        if not relative_model_name and experiment_id:
            relative_model_name = f"experiments/{experiment_id}/{model_type}"

        experiment_models.append({
            "name": relative_model_name,
            "display_name": f"{experiment_name} - {model_type}",
            "type": model_type,
            "file_path": os.path.relpath(resolved_path, _project_root).replace("\\", "/") if resolved_path else None,
            "promoted": model_type in experiment_promoted,
            "promoted_model_id": experiment_promoted.get(model_type, {}).get("model_id"),
            "promoted_model_name": experiment_promoted.get(model_type, {}).get("model_name"),
            "status": "已转正式" if model_type in experiment_promoted else "实验模型"
        })

    return experiment_models


def _enrich_experiment_data(data: Dict[str, Any], promoted_index: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None) -> Dict[str, Any]:
    if "experiment_models" not in data:
        data["experiment_models"] = _build_experiment_models(data, promoted_index=promoted_index)
    if "fusion_result" not in data:
        data["fusion_result"] = _build_fusion_result(data)
    return data


def _find_experiment_record(experiment_id: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(_results_dir):
        return None

    promoted_index = _build_promoted_models_index()

    for filename in os.listdir(_results_dir):
        if experiment_id in filename and filename.endswith('.json'):
            file_path = os.path.join(_results_dir, filename)
            with open(file_path, 'r') as f:
                return {
                    "file_path": file_path,
                    "data": _enrich_experiment_data(json.load(f), promoted_index=promoted_index)
                }
    return None


def _sanitize_model_name(model_name: str) -> str:
    sanitized = re.sub(r'[^A-Za-z0-9_-]+', '_', model_name.strip())
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    return sanitized or "promoted_model"


def _build_promoted_model_name(experiment_data: Dict[str, Any], model_type: str, requested_name: Optional[str] = None) -> str:
    if requested_name:
        return _sanitize_model_name(requested_name)

    experiment_name = experiment_data.get("config", {}).get("experiment_name", "experiment")
    base_name = f"{experiment_name}_{model_type}"
    return _sanitize_model_name(base_name)


def _ensure_unique_model_name(model_name: str, extension: str, db_session) -> str:
    base_name = _sanitize_model_name(model_name)
    candidate = base_name
    counter = 1

    while True:
        db_exists = db_session.query(ModelModel).filter(ModelModel.name == candidate).first() is not None
        file_exists = os.path.exists(os.path.join(_models_root_dir, f"{candidate}{extension}"))
        if not db_exists and not file_exists:
            return candidate
        candidate = f"{base_name}_{counter}"
        counter += 1


def _promote_experiment_model(experiment_data: Dict[str, Any], model_type: str, model_name: Optional[str], db_session) -> Dict[str, Any]:
    experiment_id = experiment_data.get("experiment_id")
    if not experiment_id:
        raise HTTPException(status_code=400, detail="Experiment ID missing from result")

    stored_model_paths = experiment_data.get("model_paths", {})
    source_model_path = _resolve_experiment_model_path(
        experiment_id=experiment_id,
        model_type=model_type,
        stored_path=stored_model_paths.get(model_type)
    )
    if not source_model_path or not os.path.exists(source_model_path):
        raise HTTPException(status_code=404, detail="Experiment model file not found")

    extension = os.path.splitext(source_model_path)[1]
    formal_model_name = _ensure_unique_model_name(
        _build_promoted_model_name(experiment_data, model_type, model_name),
        extension,
        db_session
    )

    os.makedirs(_models_root_dir, exist_ok=True)
    target_model_path = os.path.join(_models_root_dir, f"{formal_model_name}{extension}")
    meta_dst = os.path.join(_models_root_dir, f"{formal_model_name}_meta.json")
    scaler_dst = os.path.join(_models_root_dir, f"{formal_model_name}_scaler.joblib")

    source_dir = os.path.dirname(source_model_path)
    meta_src = os.path.join(source_dir, f"{model_type}_meta.json")

    try:
        shutil.copy2(source_model_path, target_model_path)
        
        # If it's a fusion model, we must also copy its sub-models
        if model_type == "fusion":
            import joblib
            from ml.fusion_wrapper import FusionModelWrapper
            fusion_model = joblib.load(source_model_path)
            for sub_config in fusion_model.sub_models:
                sub_type = sub_config["type"]
                sub_src_path = _resolve_experiment_model_path(
                    experiment_id=experiment_id,
                    model_type=sub_type,
                    stored_path=stored_model_paths.get(sub_type)
                )
                if sub_src_path and os.path.exists(sub_src_path):
                    sub_ext = os.path.splitext(sub_src_path)[1]
                    sub_target_name = f"{formal_model_name}_{sub_type}"
                    sub_target_path = os.path.join(_models_root_dir, f"{sub_target_name}{sub_ext}")
                    shutil.copy2(sub_src_path, sub_target_path)
                    
                    # Also copy sub-model meta and scaler if they exist
                    sub_meta_src = os.path.join(source_dir, f"{sub_type}_meta.json")
                    if os.path.exists(sub_meta_src):
                        shutil.copy2(sub_meta_src, os.path.join(_models_root_dir, f"{sub_target_name}_meta.json"))
                    sub_scaler_src = os.path.join(source_dir, f"{sub_type}_scaler.joblib")
                    if os.path.exists(sub_scaler_src):
                        shutil.copy2(sub_scaler_src, os.path.join(_models_root_dir, f"{sub_target_name}_scaler.joblib"))

        meta_content = {
            "type": model_type,
            "dataset": experiment_data.get("config", {}).get("dataset_type"),
            "timestamp": int(datetime.utcnow().timestamp()),
            "source": "promoted_experiment",
            "experiment_id": experiment_id,
            "experiment_name": experiment_data.get("config", {}).get("experiment_name"),
            "metrics": experiment_data.get("model_results", {}).get(model_type)
        }
        if os.path.exists(meta_src):
            try:
                with open(meta_src, 'r') as f:
                    loaded_meta = json.load(f)
                    loaded_meta.update(meta_content)
                    meta_content = loaded_meta
            except Exception as e:
                logger.warning(f"Failed to read experiment model metadata: {e}")

        with open(meta_dst, 'w') as f:
            json.dump(meta_content, f, indent=2)

        scaler_src = os.path.join(source_dir, f"{model_type}_scaler.joblib")
        if os.path.exists(scaler_src):
            shutil.copy2(scaler_src, scaler_dst)

        dataset_type = experiment_data.get("config", {}).get("dataset_type")
        dataset_display = dataset_type.upper() if isinstance(dataset_type, str) else dataset_type

        model = ModelModel(
            name=formal_model_name,
            type=model_type,
            version="v1",
            file_path=os.path.relpath(target_model_path, _project_root).replace("\\", "/"),
            dataset_type=dataset_display,
            is_active=False,
            trained_at=datetime.utcnow()
        )
        db_session.add(model)
        db_session.commit()
        db_session.refresh(model)

        model_metrics = experiment_data.get("model_results", {}).get(model_type, {})
        metric_row = ModelMetricModel(
            model_id=model.id,
            accuracy=model_metrics.get("accuracy"),
            precision_score=model_metrics.get("precision"),
            recall=model_metrics.get("recall"),
            f1_score=model_metrics.get("f1"),
            false_positive_rate=model_metrics.get("fpr"),
            false_negative_rate=model_metrics.get("fnr"),
            inference_time_ms=experiment_data.get("performance", {}).get("inference_time_ms")
        )
        db_session.add(metric_row)
        db_session.commit()
    except Exception:
        for cleanup_path in [target_model_path, meta_dst, scaler_dst]:
            if os.path.exists(cleanup_path):
                try:
                    os.remove(cleanup_path)
                except OSError:
                    pass
        raise

    return {
        "model_id": model.id,
        "model_name": formal_model_name,
        "file_path": model.file_path
    }


class ExperimentRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    experiment_name: str
    dataset_type: str  # 'nsl-kdd' or 'cic-ids2017'
    model_types: List[str]  # ['lightgbm', 'xgboost', 'cnn', 'gru', 'transformer']
    cicids2017_files: Optional[List[str]] = None  # Selected CIC-IDS2017 files (optional)
    random_seed: int = 42
    test_size: float = 0.2
    ml_num_boost_round: int = 100
    dl_epochs: int = 50
    dl_batch_size: int = 64
    dl_learning_rate: float = 0.001
    transformer_num_heads: int = 4
    transformer_ff_dim: int = 128
    transformer_num_blocks: int = 2
    fusion_strategy: str = "weighted"
    use_smote: bool = False
    use_multiclass: bool = False  # Whether to use multiclass mode (default: binary)


class DatasetFileInfo(BaseModel):
    """Dataset file information"""
    model_config = ConfigDict(protected_namespaces=())
    
    filename: str
    size_mb: float
    estimated_rows: int
    attack_types: List[str]


class PromoteExperimentModelRequest(BaseModel):
    model_type: str
    model_name: Optional[str] = None


@router.get("/")
async def list_experiments(
    limit: int = Query(50, ge=1, le=200),
    current_user: TokenData = Depends(get_current_user)
):
    """List all experiment results"""
    results = []
    
    if not os.path.exists(_results_dir):
        return results

    promoted_index = _build_promoted_models_index()
    
    for filename in os.listdir(_results_dir):
        if filename.endswith('.json') and not filename.startswith('comparison') and not filename.startswith('export'):
            try:
                with open(os.path.join(_results_dir, filename), 'r') as f:
                    data = _enrich_experiment_data(json.load(f), promoted_index=promoted_index)
                    results.append({
                        "experiment_id": data.get("experiment_id"),
                        "name": data.get("config", {}).get("experiment_name"),
                        "dataset_type": data.get("config", {}).get("dataset_type"),
                        "model_types": data.get("config", {}).get("model_types", []),
                        "experiment_models": data.get("experiment_models", []),
                        "fusion_result": data.get("fusion_result"),
                        "timestamp": data.get("timestamp"),
                        "accuracy": data.get("metrics", {}).get("accuracy"),
                        "f1_score": data.get("metrics", {}).get("f1_score"),
                        "training_time": data.get("performance", {}).get("training_time_sec")
                    })
            except Exception as e:
                logger.error(f"Error reading experiment file {filename}: {e}")
    
    # Sort by timestamp descending
    results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return results[:limit]


@router.get("/{experiment_id}")
async def get_experiment_detail(
    experiment_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get detailed experiment result"""
    if not os.path.exists(_results_dir):
        raise HTTPException(status_code=404, detail="Experiment not found")

    promoted_index = _build_promoted_models_index()
    
    for filename in os.listdir(_results_dir):
        if experiment_id in filename and filename.endswith('.json'):
            try:
                with open(os.path.join(_results_dir, filename), 'r') as f:
                    return _enrich_experiment_data(json.load(f), promoted_index=promoted_index)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(status_code=404, detail="Experiment not found")


@router.post("/run")
async def run_experiment(
    request: ExperimentRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """Start a new experiment (async)"""
    task_id = str(uuid.uuid4())
    
    # Initialize task status
    _experiment_tasks[task_id] = {
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "experiment_name": request.experiment_name,
        "progress": 0,
        "message": "Initializing experiment..."
    }
    
    def run_in_background():
        try:
            _experiment_tasks[task_id]["message"] = "Loading dataset..."
            _experiment_tasks[task_id]["progress"] = 10
            
            config = ExperimentConfig(
                experiment_name=request.experiment_name,
                dataset_type=request.dataset_type,
                model_types=request.model_types,
                random_seed=request.random_seed,
                test_size=request.test_size,
                ml_num_boost_round=request.ml_num_boost_round,
                dl_epochs=request.dl_epochs,
                dl_batch_size=request.dl_batch_size,
                dl_learning_rate=request.dl_learning_rate,
                transformer_num_heads=request.transformer_num_heads,
                transformer_ff_dim=request.transformer_ff_dim,
                transformer_num_blocks=request.transformer_num_blocks,
                fusion_strategy=request.fusion_strategy,
                is_multiclass=request.use_multiclass
            )
            
            # Map use_smote explicitly if added to ExperimentConfig in the future
            # Currently ExperimentConfig uses use_class_weights, but we can set it
            if hasattr(config, 'use_smote'):
                config.use_smote = request.use_smote
            elif request.use_smote:
                # If experiment config doesn't have use_smote, fallback to use_class_weights
                config.use_class_weights = True
            
            runner = ExperimentRunner()
            
            _experiment_tasks[task_id]["message"] = "Training models..."
            _experiment_tasks[task_id]["progress"] = 30
            
            # Pass CIC-IDS2017 file selection if provided
            if request.dataset_type == "cic-ids2017" and request.cicids2017_files:
                result = runner.run_experiment(config, cicids2017_files=request.cicids2017_files, task_id=task_id)
            else:
                result = runner.run_experiment(config, task_id=task_id)
            
            _experiment_tasks[task_id]["status"] = "completed"
            _experiment_tasks[task_id]["progress"] = 100
            _experiment_tasks[task_id]["message"] = "Experiment completed"
            _experiment_tasks[task_id]["result"] = {
                "experiment_id": result.experiment_id,
                "accuracy": result.accuracy,
                "f1_score": result.f1_score,
                "training_time": result.training_time_sec
            }
            
        except InterruptedError as e:
            logger.warning(f"Experiment stopped: {e}")
            _experiment_tasks[task_id]["status"] = "stopped"
            _experiment_tasks[task_id]["message"] = "Experiment stopped by user"
            _experiment_tasks[task_id]["progress"] = 0
        except Exception as e:
            logger.error(f"Experiment failed: {e}")
            _experiment_tasks[task_id]["status"] = "failed"
            _experiment_tasks[task_id]["message"] = str(e)
            _experiment_tasks[task_id]["progress"] = 0
    
    thread = threading.Thread(target=run_in_background, daemon=True)
    thread.start()
    
    return {"task_id": task_id, "message": "Experiment started"}


@router.get("/task/{task_id}")
async def get_experiment_task_status(
    task_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get experiment task status"""
    if task_id not in _experiment_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _experiment_tasks[task_id]


@router.post("/task/{task_id}/stop")
async def stop_experiment_task(
    task_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Stop a running experiment task"""
    if task_id not in _experiment_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
        
    task = _experiment_tasks[task_id]
    if task["status"] in ["completed", "failed", "stopped"]:
        return {"message": "Task already finished"}
        
    task["stop_requested"] = True
    task["message"] = "Stopping experiment..."
    task["status"] = "stopped"
    
    return {"message": "Experiment stop requested"}

@router.post("/{experiment_id}/promote")
async def promote_experiment_model(
    experiment_id: str,
    request: PromoteExperimentModelRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """Promote an experiment model into the formal model registry."""
    experiment_record = _find_experiment_record(experiment_id)
    if not experiment_record:
        raise HTTPException(status_code=404, detail="Experiment not found")

    experiment_data = experiment_record["data"]
    model_types = experiment_data.get("config", {}).get("model_types", [])
    
    # "fusion" is a valid model type to promote even if not explicitly in config.model_types
    valid_types = list(model_types)
    if "fusion" in experiment_data.get("model_results", {}):
        valid_types.append("fusion")
        
    if request.model_type not in valid_types:
        raise HTTPException(status_code=404, detail="Experiment model not found")

    db_session = SessionLocal()
    try:
        result = _promote_experiment_model(
            experiment_data=experiment_data,
            model_type=request.model_type,
            model_name=request.model_name,
            db_session=db_session
        )
        return {
            "message": "Experiment model promoted successfully",
            **result
        }
    except HTTPException:
        db_session.rollback()
        raise
    except Exception as e:
        db_session.rollback()
        logger.error(f"Failed to promote experiment model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to promote experiment model")
    finally:
        db_session.close()


@router.delete("/{experiment_id}")
async def delete_experiment(
    experiment_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Delete an experiment result"""
    if not os.path.exists(_results_dir):
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    for filename in os.listdir(_results_dir):
        if experiment_id in filename and filename.endswith('.json'):
            try:
                experiment_models_dir = os.path.join(_experiment_models_dir, experiment_id)
                legacy_models_dir = os.path.join(_models_root_dir, experiment_id)

                if os.path.isdir(experiment_models_dir):
                    shutil.rmtree(experiment_models_dir, ignore_errors=True)
                if os.path.isdir(legacy_models_dir):
                    shutil.rmtree(legacy_models_dir, ignore_errors=True)

                os.remove(os.path.join(_results_dir, filename))
                return {"message": "Experiment deleted"}
            except Exception as e:
                logger.error(f"Error deleting experiment: {e}")
                raise HTTPException(status_code=500, detail="Failed to delete experiment")
    
    raise HTTPException(status_code=404, detail="Experiment not found")


@router.get("/datasets/cicids2017/files")
async def get_cicids2017_files(
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get list of available CIC-IDS2017 dataset files.
    
    Returns information about each file including size and estimated row count.
    """
    base_dir = os.path.join(_project_root, "data", "datasets", "CIC-IDS2017")
    
    if not os.path.exists(base_dir):
        raise HTTPException(status_code=404, detail="CIC-IDS2017 dataset directory not found")
    
    files_info = []
    
    # Estimate row counts and attack types for known files
    file_estimates = {
        "Monday-WorkingHours.pcap_ISCX.csv": {"rows": 529918, "attacks": ["Normal"]},
        "Tuesday-WorkingHours.pcap_ISCX.csv": {"rows": 445909, "attacks": ["DDoS", "DoS", "PortScan", "WebAttack"]},
        "Wednesday-workingHours.pcap_ISCX.csv": {"rows": 692703, "attacks": ["DDoS", "DoS", "PortScan"]},
        "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv": {"rows": 170366, "attacks": ["WebAttack"]},
        "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv": {"rows": 288602, "attacks": ["Infiltration"]},
        "Friday-WorkingHours-Morning.pcap_ISCX.csv": {"rows": 191033, "attacks": ["DDoS", "DoS", "Bot"]},
        "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv": {"rows": 286467, "attacks": ["PortScan"]},
        "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv": {"rows": 225745, "attacks": ["DDoS", "DoS"]},
    }
    
    # Scan directory for all CSV files (except processed_*)
    for filename in os.listdir(base_dir):
        if filename.endswith('.csv') and not filename.startswith('processed_'):
            file_path = os.path.join(base_dir, filename)
            try:
                size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
                estimate = file_estimates.get(filename, {"rows": 0, "attacks": []})
                
                files_info.append({
                    "filename": filename,
                    "size_mb": size_mb,
                    "estimated_rows": estimate["rows"],
                    "attack_types": estimate["attacks"]
                })
            except Exception as e:
                logger.warning(f"Error getting info for {filename}: {e}")

    # Scan balanced directory for CSV files
    balanced_dir = os.path.join(_project_root, "data", "datasets", "balanced")
    if os.path.exists(balanced_dir):
        for filename in os.listdir(balanced_dir):
            if filename.endswith('.csv'):
                file_path = os.path.join(balanced_dir, filename)
                try:
                    size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
                    
                    # Try to get row count from DB if available, else estimate from file size (assuming ~200 bytes/row)
                    estimated_rows = int(os.path.getsize(file_path) / 200)
                    
                    files_info.append({
                        "filename": f"balanced/{filename}",
                        "size_mb": size_mb,
                        "estimated_rows": estimated_rows,
                        "attack_types": ["Balanced"]
                    })
                except Exception as e:
                    logger.warning(f"Error getting info for balanced/{filename}: {e}")

    # Sort files alphabetically
    files_info.sort(key=lambda x: x["filename"])
    
    return {"files": files_info, "total_files": len(files_info)}
