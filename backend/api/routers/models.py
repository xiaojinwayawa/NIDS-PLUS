from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import os
import json
import uuid
import threading

from auth import get_current_user, TokenData
from db.db_manager import get_db, SessionLocal
from db.models import ModelModel, ModelMetricModel, DatasetModel
from ml.trainer import TrainingManager, get_training_progress, set_training_progress, clear_training_progress, infer_dataset_type_from_paths
from ml.detection_engine import DetectionEngine
from config import settings
from logging_config import app_logger as logger

router = APIRouter()

# Store for async training tasks
_training_tasks: dict = {}


def _get_project_root() -> str:
    current_file = os.path.abspath(__file__)
    routers_dir = os.path.dirname(current_file)
    api_dir = os.path.dirname(routers_dir)
    backend_dir = os.path.dirname(api_dir)
    return os.path.dirname(backend_dir)


def _get_models_dir(project_root: str) -> str:
    return os.path.join(project_root, "models")


def _get_experiment_models_dir(project_root: str) -> str:
    return os.path.join(project_root, "models", "experiments")


def _get_experiment_results_dir(project_root: str) -> str:
    return os.path.join(project_root, "data", "experiments")


def _infer_model_type(model_name: str, meta_file: Optional[str] = None) -> str:
    if meta_file and os.path.exists(meta_file):
        try:
            with open(meta_file, 'r') as f:
                meta = json.load(f)
                if meta.get("type"):
                    return meta["type"]
        except Exception as e:
            logger.warning(f"Failed to load metadata for {model_name}: {e}")

    lower_name = model_name.lower()
    if "lightgbm" in lower_name:
        return "lightgbm"
    if "xgboost" in lower_name or "xgb" in lower_name:
        return "xgboost"
    if "cnn_resattn" in lower_name or "resattn" in lower_name:
        return "cnn_resattn"
    if "cnn" in lower_name:
        return "cnn"
    if "gru" in lower_name:
        return "gru"
    if "transformer" in lower_name:
        return "transformer"
    return "unknown"


def _build_model_name(base_dir: str, root: str, filename: str) -> str:
    base_name = os.path.splitext(filename)[0]
    rel_dir = os.path.relpath(root, base_dir)
    if rel_dir == '.':
        return base_name
    return os.path.join(rel_dir, base_name).replace("\\", "/")


def _resolve_experiment_model_path(project_root: str, experiment_id: str, model_type: str, stored_path: Optional[str] = None) -> Optional[str]:
    candidate_paths = []

    if stored_path:
        if os.path.isabs(stored_path):
            candidate_paths.append(stored_path)
        else:
            candidate_paths.append(os.path.join(project_root, stored_path))

    for ext in [".joblib", ".keras", ".h5"]:
        candidate_paths.append(os.path.join(project_root, "models", "experiments", experiment_id, f"{model_type}{ext}"))
        # Legacy experiment runs stored models directly under models/<experiment_id>/
        candidate_paths.append(os.path.join(project_root, "models", experiment_id, f"{model_type}{ext}"))

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


def _build_experiment_model_entries(project_root: str, experiment_data: dict) -> List[dict]:
    models_dir = _get_models_dir(project_root)
    experiment_id = experiment_data.get("experiment_id")
    experiment_name = experiment_data.get("config", {}).get("experiment_name", "Unnamed")
    model_types = experiment_data.get("config", {}).get("model_types", [])
    model_results = experiment_data.get("model_results", {})
    model_paths = experiment_data.get("model_paths", {})
    performance = experiment_data.get("performance")
    timestamp = experiment_data.get("timestamp")

    entries = []
    for model_type in model_types:
        resolved_path = None
        if experiment_id:
            resolved_path = _resolve_experiment_model_path(
                project_root=project_root,
                experiment_id=experiment_id,
                model_type=model_type,
                stored_path=model_paths.get(model_type)
            )

        model_name = None
        if resolved_path:
            try:
                model_name = os.path.splitext(os.path.relpath(resolved_path, models_dir))[0].replace("\\", "/")
            except ValueError:
                model_name = os.path.splitext(os.path.basename(resolved_path))[0]

        if not model_name and experiment_id:
            model_name = f"experiments/{experiment_id}/{model_type}"

        if not model_name:
            continue

        entries.append({
            "id": f"exp_{experiment_id}_{model_type}",
            "name": model_name,
            "display_name": f"{experiment_name} - {model_type}",
            "file": os.path.basename(resolved_path) if resolved_path else None,
            "path": resolved_path,
            "type": model_type,
            "source": "experiment",
            "group": "experiment",
            "experiment_id": experiment_id,
            "experiment_name": experiment_name,
            "metrics": {
                "accuracy": model_results.get(model_type, {}).get("accuracy"),
                "precision": model_results.get(model_type, {}).get("precision"),
                "recall": model_results.get(model_type, {}).get("recall"),
                "f1": model_results.get(model_type, {}).get("f1"),
                "fpr": model_results.get(model_type, {}).get("fpr"),
                "fnr": model_results.get(model_type, {}).get("fnr")
            },
            "performance": performance,
            "timestamp": timestamp
        })

    return entries

# Request models
class TrainRequest(BaseModel):
    model_type: str
    dataset_id: Optional[int] = None
    dataset_ids: Optional[List[int]] = None
    dataset_path: Optional[str] = None
    dataset_paths: Optional[List[str]] = None
    model_name: Optional[str] = None
    epochs: Optional[int] = None
    use_smote: bool = False

def get_engine(request: Request) -> DetectionEngine:
    return request.app.state.engine


@router.get("/available")
async def get_available_models(
    current_user: TokenData = Depends(get_current_user)
):
    """Get available model files from the models directory and experiments"""
    project_root = _get_project_root()
    available_models = []
    
    # 1. Load normal models from project root models directory, excluding experiment output
    root_models_dir = _get_models_dir(project_root)
    experiment_models_dir = os.path.abspath(_get_experiment_models_dir(project_root))
    if os.path.exists(root_models_dir):
        for root, dirs, files in os.walk(root_models_dir):
            dirs[:] = [
                d for d in dirs
                if os.path.abspath(os.path.join(root, d)) != experiment_models_dir
            ]
            for filename in files:
                if filename.endswith(('.joblib', '.h5', '.keras')):
                    model_name = _build_model_name(root_models_dir, root, filename)
                    if model_name.endswith('_scaler'):
                        continue
                    base_name = os.path.splitext(filename)[0]
                    meta_file = os.path.join(root, f"{base_name}_meta.json")
                    model_type = _infer_model_type(model_name, meta_file)
                    
                    model_info = {
                        "id": f"model_{len(available_models)}",
                        "name": model_name,
                        "display_name": model_name,
                        "file": filename,
                        "path": os.path.join(root, filename),
                        "type": model_type,
                        "source": "models",
                        "group": "single"
                    }
                    
                    if os.path.exists(meta_file):
                        try:
                            with open(meta_file, 'r') as f:
                                meta = json.load(f)
                                model_info["metrics"] = meta.get("metrics")
                                model_info["timestamp"] = meta.get("timestamp")
                        except Exception as e:
                            logger.warning(f"Failed to load metadata for {model_name}: {e}")
                    
                    available_models.append(model_info)
    
    # 2. Load models from experiment results
    experiments_dir = _get_experiment_results_dir(project_root)
    if os.path.exists(experiments_dir):
        for filename in os.listdir(experiments_dir):
            if filename.endswith('.json') and not filename.startswith('comparison') and not filename.startswith('export'):
                try:
                    with open(os.path.join(experiments_dir, filename), 'r') as f:
                        data = json.load(f)
                        available_models.extend(_build_experiment_model_entries(project_root, data))
                except Exception as e:
                    logger.error(f"Error reading experiment file {filename}: {e}")
    
    return {
        "models": available_models
    }

def get_engine(request: Request) -> DetectionEngine:
    return request.app.state.engine

@router.get("/", response_model=List[dict])
async def list_models(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    result = []
    db_model_names = set()
    
    # 1. Get models from database (trained via frontend)
    project_root = _get_project_root()
    models_dir = _get_models_dir(project_root)
    experiment_models_dir = os.path.abspath(_get_experiment_models_dir(project_root))

    models = db.query(ModelModel).order_by(ModelModel.created_at.desc()).all()
    for m in models:
        db_model_names.add(m.name)
        metric = (
            db.query(ModelMetricModel)
            .filter(ModelMetricModel.model_id == m.id)
            .order_by(ModelMetricModel.timestamp.desc())
            .first()
        )
        
        model_info = {
            "id": m.id,
            "name": m.name,
            "type": m.type,
            "version": m.version,
            "file_path": m.file_path,
            "dataset_type": m.dataset_type,
            "is_active": m.is_active,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "trained_at": m.trained_at.isoformat() if m.trained_at else None,
            "source": "database",
            "metrics": {
                "accuracy": getattr(metric, "accuracy", None),
                "precision": getattr(metric, "precision_score", None),
                "recall": getattr(metric, "recall", None),
                "f1": getattr(metric, "f1_score", None),
                "fpr": getattr(metric, "false_positive_rate", None),
                "fnr": getattr(metric, "false_negative_rate", None)
            } if metric else None
        }
        
        # Load metadata from disk if available
        try:
            full_path = m.file_path
            if not os.path.isabs(full_path):
                full_path = os.path.join(project_root, full_path)
            
            dir_name = os.path.dirname(full_path)
            base_name = os.path.splitext(os.path.basename(full_path))[0]
            meta_path = os.path.join(dir_name, f"{base_name}_meta.json")
            
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
                    model_info["metadata"] = meta
                    # If label_mapping exists, expose it directly or via metadata
                    if "label_mapping" in meta:
                        model_info["label_mapping"] = meta["label_mapping"]
        except Exception as e:
            # Don't fail listing if metadata load fails
            pass
            
        result.append(model_info)
    
    # 2. Scan preset models from models directory (not in database)
    # paths already calculated above
    
    preset_id = -1
    if os.path.exists(models_dir):
        for root, dirs, files in os.walk(models_dir):
            dirs[:] = [
                d for d in dirs
                if os.path.abspath(os.path.join(root, d)) != experiment_models_dir
            ]
            for filename in files:
                if filename.endswith(('.joblib', '.h5', '.keras')):
                    # Skip scaler files (ending with _scaler)
                    model_name = _build_model_name(models_dir, root, filename)
                    if model_name.endswith('_scaler'):
                        continue
                    
                    # Skip if already in database
                    if model_name in db_model_names:
                        continue
                    
                    # Try to load metadata first to get type
                    base_name = os.path.splitext(filename)[0]
                    meta_file = os.path.join(root, f"{base_name}_meta.json")
                    model_type = _infer_model_type(model_name, meta_file)
                    
                    model_info = {
                        "id": preset_id,
                        "name": model_name,
                        "type": model_type,
                        "version": "v1",
                        "file_path": os.path.join(root, filename),
                        "dataset_type": "CIC-IDS2017", # Default assumption for experiments
                        "is_active": False,
                        "created_at": None,
                        "trained_at": None,
                        "source": "preset",
                        "metrics": None
                    }
                    
                    # Load remaining metadata
                    if os.path.exists(meta_file):
                        try:
                            with open(meta_file, 'r') as f:
                                meta = json.load(f)
                                model_info["metrics"] = meta.get("metrics")
                                if meta.get("timestamp"):
                                    model_info["trained_at"] = datetime.fromtimestamp(meta["timestamp"]).isoformat()
                        except:
                            pass
                    
                    result.append(model_info)
                    preset_id -= 1
    
    return result

@router.post("/train")
async def train_model(
    request: TrainRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    model_type = request.model_type
    dataset_id = request.dataset_id
    dataset_ids = request.dataset_ids
    dataset_path = request.dataset_path
    dataset_paths = request.dataset_paths
    model_name = request.model_name
    epochs = request.epochs
    use_smote = request.use_smote
    
    if not model_type:
        raise HTTPException(status_code=400, detail="model_type is required")
    
    # Collect all dataset file paths
    dataset_files = []
    dataset_type = None
    dataset_types_seen = set()
    
    # Get project root for resolving paths
    current_file = os.path.abspath(__file__)
    routers_dir = os.path.dirname(current_file)
    api_dir = os.path.dirname(routers_dir)
    backend_dir = os.path.dirname(api_dir)
    project_root = os.path.dirname(backend_dir)
    
    # Handle single dataset_id (backward compatibility)
    if dataset_id is not None:
        if dataset_id > 0:
            # Uploaded dataset from database
            d = db.query(DatasetModel).filter(DatasetModel.id == dataset_id).first()
            if not d:
                raise HTTPException(status_code=404, detail="Dataset not found")
            dataset_files.append(d.file_path)
            dataset_type = d.type
            if d.type:
                dataset_types_seen.add(str(d.type))
        else:
            # Preset dataset - dataset_path should be provided by frontend
            if not dataset_path:
                raise HTTPException(status_code=400, detail="dataset_path is required for preset datasets")
            dataset_files.append(dataset_path)
    
    # Handle multiple dataset_ids
    if dataset_ids and len(dataset_ids) > 0:
        for ds_id in dataset_ids:
            if ds_id > 0:
                # Uploaded dataset from database
                d = db.query(DatasetModel).filter(DatasetModel.id == ds_id).first()
                if not d:
                    raise HTTPException(status_code=404, detail=f"Dataset {ds_id} not found")
                dataset_files.append(d.file_path)
                if dataset_type is None:
                    dataset_type = d.type
                if d.type:
                    dataset_types_seen.add(str(d.type))
            else:
                # Preset dataset - try to find it in dataset_paths or scan
                if dataset_paths and len(dataset_paths) > len(dataset_files):
                    dataset_files.append(dataset_paths[len(dataset_files)])
                else:
                    # Need to find preset dataset by scanning
                    datasets_base = os.path.join(project_root, "data", "datasets")
                    found = False
                    preset_id_counter = -1
                    for root, dirs, files in os.walk(datasets_base):
                        if 'uploads' in root:
                            continue
                        for filename in files:
                            if filename.endswith(('.csv', '.txt', '.arff')):
                                if preset_id_counter == ds_id:
                                    dataset_files.append(os.path.join(root, filename))
                                    found = True
                                    break
                                preset_id_counter -= 1
                        if found:
                            break
                    if not found:
                        raise HTTPException(status_code=404, detail=f"Preset dataset {ds_id} not found")
    
    # Handle single dataset_path (backward compatibility)
    if dataset_path and len(dataset_files) == 0:
        dataset_files.append(dataset_path)
    
    # Handle multiple dataset_paths
    if dataset_paths and len(dataset_paths) > 0:
        for path in dataset_paths:
            if path not in dataset_files:
                dataset_files.append(path)
    
    if len(dataset_files) == 0:
        raise HTTPException(status_code=400, detail="No dataset files found")

    normalized_dataset_types = {value.strip().lower() for value in dataset_types_seen if str(value).strip()}
    if normalized_dataset_types:
        if all("cic" in value for value in normalized_dataset_types):
            dataset_type = "CIC-IDS2017"
        elif all("kdd" in value for value in normalized_dataset_types):
            dataset_type = "NSL-KDD"
        else:
            dataset_type = "Mixed"
    elif dataset_type is None:
        dataset_type = infer_dataset_type_from_paths(dataset_files)

    if not model_name:
        model_name = f"{model_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Generate task ID for progress tracking
    task_id = str(uuid.uuid4())
    
    # Initialize progress
    set_training_progress(task_id, {
        "stage": "initializing",
        "current": 0,
        "total": 100,
        "percent": 0,
        "message": "Starting training...",
        "elapsed": 0
    })
    
    # Run training in background thread
    def run_training():
        nonlocal dataset_type
        try:
            tm = TrainingManager()
            params = {"use_smote": use_smote, "dataset_type": dataset_type}
            metrics = tm.train_model(model_type, dataset_files, params=params, model_name=model_name, task_id=task_id, epochs=epochs)
            
            # Save to database using a new session
            db_session = SessionLocal()
            try:
                # 根据模型类型选择正确的文件后缀
                if model_type in ["cnn", "cnn_resattn", "gru", "transformer"]:
                    file_path = os.path.join("models", f"{model_name}.h5")
                else:
                    file_path = os.path.join("models", f"{model_name}.joblib")
                
                # Determine dataset type if not set
                if dataset_type is None:
                    first_path = dataset_files[0].lower()
                    if 'nsl-kdd' in first_path or 'kdd' in first_path:
                        dataset_type = 'NSL-KDD'
                    elif 'cic-ids2017' in first_path or 'cic' in first_path or 'balanced' in first_path:
                        dataset_type = 'CIC-IDS2017'
                    else:
                        dataset_type = 'Mixed'

                meta_path = os.path.join(project_root, "models", f"{model_name}_meta.json")
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as meta_file:
                            meta = json.load(meta_file)
                        meta["dataset_type"] = dataset_type
                        with open(meta_path, "w", encoding="utf-8") as meta_file:
                            json.dump(meta, meta_file, indent=4, ensure_ascii=False)
                    except Exception:
                        logger.warning("Failed to backfill dataset_type into metadata for %s", model_name, exc_info=True)
                
                model = ModelModel(
                    name=model_name,
                    type=model_type,
                    version="v1",
                    file_path=file_path,
                    dataset_type=dataset_type,
                    is_active=False,
                    trained_at=datetime.utcnow()
                )
                db_session.add(model)
                db_session.commit()
                db_session.refresh(model)
                
                mm = ModelMetricModel(
                    model_id=model.id,
                    accuracy=metrics.get("accuracy"),
                    precision_score=metrics.get("precision"),
                    recall=metrics.get("recall"),
                    f1_score=metrics.get("f1"),
                    false_positive_rate=metrics.get("fpr"),
                    false_negative_rate=metrics.get("fnr"),
                    inference_time_ms=None
                )
                db_session.add(mm)
                db_session.commit()
                
                # Update progress with result
                set_training_progress(task_id, {
                    "stage": "complete",
                    "current": 100,
                    "total": 100,
                    "percent": 100,
                    "message": "Training complete!",
                    "elapsed": metrics.get("training_time", 0),
                    "model_id": model.id,
                    "metrics": metrics
                })
            finally:
                db_session.close()
                
        except Exception as e:
            set_training_progress(task_id, {
                "stage": "error",
                "current": 0,
                "total": 100,
                "percent": 0,
                "message": str(e),
                "elapsed": 0
            })
    
    # Start training in background
    thread = threading.Thread(target=run_training, daemon=True)
    thread.start()
    _training_tasks[task_id] = thread
    
    return {
        "message": "Training started",
        "task_id": task_id
    }

@router.get("/train/progress/{task_id}")
async def get_train_progress(
    task_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get training progress for a task"""
    progress = get_training_progress(task_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Task not found")
    return progress


@router.post("/train/stop/{task_id}")
async def stop_training(
    task_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Stop a training task and delete incomplete model"""
    from ml.trainer import stop_training_task
    
    # Mark task as stopped
    stop_training_task(task_id)
    
    # Update progress to show stopped
    set_training_progress(task_id, {
        "stage": "stopped",
        "current": 0,
        "total": 100,
        "percent": 0,
        "message": "Training stopped by user",
        "elapsed": 0
    })
    
    # Remove from active tasks
    if task_id in _training_tasks:
        del _training_tasks[task_id]
    
    return {"message": "Training stopped"}


@router.delete("/{model_id}")
async def delete_model(
    model_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
    engine: DetectionEngine = Depends(get_engine)
):
    """
    Admin only: Delete a model from database and optionally from disk
    """
    from auth import require_admin
    await require_admin(current_user)
    
    if model_id > 0:
        # Database model
        m = db.query(ModelModel).filter(ModelModel.id == model_id).first()
        if not m:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Check if model is currently loaded in engine
        if engine.current_model_name == m.name:
            raise HTTPException(status_code=400, detail="Cannot delete the model currently loaded in the detection engine")
        
        # Delete metrics first
        db.query(ModelMetricModel).filter(ModelMetricModel.model_id == model_id).delete()
        
        # Delete model file from disk
        try:
            current_file = os.path.abspath(__file__)
            routers_dir = os.path.dirname(current_file)
            api_dir = os.path.dirname(routers_dir)
            backend_dir = os.path.dirname(api_dir)
            project_root = os.path.dirname(backend_dir)
            
            file_path = m.file_path
            if not os.path.isabs(file_path):
                file_path = os.path.join(project_root, file_path)
            
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Also delete meta file if exists
            dir_name = os.path.dirname(file_path)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            meta_path = os.path.join(dir_name, f"{base_name}_meta.json")
            if os.path.exists(meta_path):
                os.remove(meta_path)
            
            # Also delete scaler file if exists
            scaler_path = os.path.join(dir_name, f"{base_name}_scaler.joblib")
            if os.path.exists(scaler_path):
                os.remove(scaler_path)
                
        except Exception as e:
            logger.warning(f"Failed to delete model file: {e}")
        
        # Delete from database
        db.delete(m)
        db.commit()
        
        return {"message": "Model deleted successfully"}
    else:
        # Preset model (negative ID) - delete from disk only
        # Need to find the model file
        current_file = os.path.abspath(__file__)
        routers_dir = os.path.dirname(current_file)
        api_dir = os.path.dirname(routers_dir)
        backend_dir = os.path.dirname(api_dir)
        project_root = os.path.dirname(backend_dir)
        models_dir = os.path.join(project_root, "models")
        
        # Find the model by scanning
        target_model = None
        models_list = await list_models(current_user=current_user, db=db)
        for model in models_list:
            if model["id"] == model_id:
                target_model = model
                break
        
        if not target_model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        file_path = target_model["file_path"]
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Model file not found")
        
        # Delete the model file
        try:
            os.remove(file_path)
            
            # Also delete meta file if exists
            dir_name = os.path.dirname(file_path)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            meta_path = os.path.join(dir_name, f"{base_name}_meta.json")
            if os.path.exists(meta_path):
                os.remove(meta_path)
            
            # Also delete scaler file if exists
            scaler_path = os.path.join(dir_name, f"{base_name}_scaler.joblib")
            if os.path.exists(scaler_path):
                os.remove(scaler_path)
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete model file: {str(e)}")
        
        return {"message": "Preset model deleted successfully"}


class UploadModelRequest(BaseModel):
    model_name: str
    model_type: str
    dataset_type: Optional[str] = None


@router.post("/upload")
async def upload_model(
    file: UploadFile = File(...),
    model_name: str = None,
    model_type: str = None,
    dataset_type: str = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload an external model file (.joblib or .h5)
    """
    # Validate file type
    filename = file.filename
    if not filename.endswith(('.joblib', '.h5', '.keras')):
        raise HTTPException(
            status_code=400, 
            detail="Invalid file type. Only .joblib, .h5, .keras files are supported."
        )
    
    # Determine model type if not provided
    if not model_type:
        lower_name = filename.lower()
        if "lightgbm" in lower_name:
            model_type = "lightgbm"
        elif "xgboost" in lower_name or "xgb" in lower_name:
            model_type = "xgboost"
        elif "cnn_resattn" in lower_name or "resattn" in lower_name:
            model_type = "cnn_resattn"
        elif "cnn" in lower_name:
            model_type = "cnn"
        elif "gru" in lower_name:
            model_type = "gru"
        elif "transformer" in lower_name:
            model_type = "transformer"
        else:
            model_type = "unknown"
    
    # Generate model name if not provided
    if not model_name:
        base_name = os.path.splitext(filename)[0]
        model_name = f"imported_{base_name}"
    
    # Get models directory
    current_file = os.path.abspath(__file__)
    routers_dir = os.path.dirname(current_file)
    api_dir = os.path.dirname(routers_dir)
    backend_dir = os.path.dirname(api_dir)
    project_root = os.path.dirname(backend_dir)
    models_dir = os.path.join(project_root, "models")
    
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)
    
    # Save file
    file_path = os.path.join(models_dir, filename)
    counter = 1
    while os.path.exists(file_path):
        base, ext = os.path.splitext(filename)
        file_path = os.path.join(models_dir, f"{base}_{counter}{ext}")
        counter += 1
    
    # Write file
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Create database record
    try:
        model = ModelModel(
            name=model_name,
            type=model_type,
            version="1.0",
            file_path=os.path.relpath(file_path, project_root),
            dataset_type=dataset_type,
            is_active=False,
            created_at=datetime.utcnow(),
            trained_at=datetime.utcnow()
        )
        
        db.add(model)
        db.commit()
        db.refresh(model)
        
        logger.info(f"Model uploaded successfully: {model_name} (ID: {model.id})")
        
        return {
            "message": "Model uploaded successfully",
            "model_id": model.id,
            "model_name": model_name,
            "model_type": model_type,
            "file_path": file_path
        }
        
    except Exception as e:
        db.rollback()
        # Clean up file if DB failed
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to save model to database: {str(e)}")



@router.post("/import/{model_name}")
async def import_local_model(
    model_name: str,
    model_type: str = None,
    dataset_type: str = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Import an existing model from the local models directory
    """
    # Get models directory
    current_file = os.path.abspath(__file__)
    routers_dir = os.path.dirname(current_file)
    api_dir = os.path.dirname(routers_dir)
    backend_dir = os.path.dirname(api_dir)
    project_root = os.path.dirname(backend_dir)
    models_dir = os.path.join(project_root, "models")
    
    # Find the model file
    model_file = None
    model_file_path = None
    
    # Search for the model in models directory
    if os.path.exists(models_dir):
        for root, dirs, files in os.walk(models_dir):
            for filename in files:
                if filename.endswith(('.joblib', '.h5', '.keras')):
                    base_name = os.path.splitext(filename)[0]
                    if base_name.endswith('_scaler'):
                        continue
                    
                    # Get relative model name
                    rel_dir = os.path.relpath(root, models_dir)
                    if rel_dir == '.':
                        current_model_name = base_name
                    else:
                        current_model_name = f"{rel_dir}/{base_name}"
                    
                    if current_model_name == model_name:
                        model_file = filename
                        model_file_path = os.path.join(root, filename)
                        break
            if model_file:
                break
    
    if not model_file or not model_file_path:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found in models directory")
    
    # Check if model already exists in database
    existing = db.query(ModelModel).filter(ModelModel.name == model_name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Model '{model_name}' already exists in database")
    
    # Determine model type if not provided
    if not model_type:
        lower_name = model_name.lower()
        if "lightgbm" in lower_name:
            model_type = "lightgbm"
        elif "xgboost" in lower_name or "xgb" in lower_name:
            model_type = "xgboost"
        elif "cnn_resattn" in lower_name or "resattn" in lower_name:
            model_type = "cnn_resattn"
        elif "cnn" in lower_name:
            model_type = "cnn"
        elif "gru" in lower_name:
            model_type = "gru"
        elif "transformer" in lower_name:
            model_type = "transformer"
        else:
            model_type = "unknown"
    
    # Create database record
    try:
        model = ModelModel(
            name=model_name,
            type=model_type,
            version="1.0",
            file_path=os.path.relpath(model_file_path, project_root),
            dataset_type=dataset_type,
            is_active=False,
            created_at=datetime.utcnow(),
            trained_at=datetime.utcnow()
        )
        
        db.add(model)
        db.commit()
        db.refresh(model)
        
        logger.info(f"Model imported successfully: {model_name} (ID: {model.id})")
        
        return {
            "message": "Model imported successfully",
            "model_id": model.id,
            "model_name": model_name,
            "model_type": model_type,
            "file_path": model_file_path
        }
        
    except Exception as e:
        logger.error(f"Error saving imported model to DB: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save model to database: {str(e)}")

@router.delete("/import/{model_name}")
async def delete_imported_model(
    model_name: str,
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Admin only: Delete an imported model from disk"""
    from auth import require_admin
    await require_admin(current_user)
    
    try:
        from config import settings
        import os
        model_dir = os.path.join(settings.MODELS_DIR, "imported")
        model_path = os.path.join(model_dir, model_name)
        if os.path.exists(model_path):
            os.remove(model_path)
            return {"message": "Model deleted"}
        return {"message": "Model not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


