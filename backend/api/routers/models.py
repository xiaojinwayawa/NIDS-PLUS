from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
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
from ml.trainer import TrainingManager, get_training_progress, set_training_progress, clear_training_progress
from ml.detection_engine import DetectionEngine
from config import settings
from logging_config import app_logger as logger

router = APIRouter()

# Store for async training tasks
_training_tasks: dict = {}

# Request models
class TrainRequest(BaseModel):
    model_type: str
    dataset_id: Optional[int] = None
    dataset_ids: Optional[List[int]] = None
    dataset_path: Optional[str] = None
    dataset_paths: Optional[List[str]] = None
    model_name: Optional[str] = None
    epochs: Optional[int] = None

def get_engine(request: Request) -> DetectionEngine:
    return request.app.state.engine


@router.get("/available")
async def get_available_models(
    current_user: TokenData = Depends(get_current_user)
):
    """Get available model files from the models directory"""
    # Get project root models directory
    # __file__ is backend/api/routers/models.py
    # Go up 3 levels: routers -> api -> backend -> project_root
    current_file = os.path.abspath(__file__)
    routers_dir = os.path.dirname(current_file)      # backend/api/routers
    api_dir = os.path.dirname(routers_dir)           # backend/api
    backend_dir = os.path.dirname(api_dir)           # backend
    project_root = os.path.dirname(backend_dir)      # project_root
    models_dir = os.path.join(project_root, "models")
    
    available_models = []
    
    if os.path.exists(models_dir):
        for root, dirs, files in os.walk(models_dir):
            for filename in files:
                if filename.endswith(('.joblib', '.h5', '.keras')):
                    # Skip scaler files (ending with _scaler)
                    base_name = os.path.splitext(filename)[0]
                    if base_name.endswith('_scaler'):
                        continue
                    
                    # Determine model name relative to models_dir
                    rel_dir = os.path.relpath(root, models_dir)
                    
                    if rel_dir == '.':
                        model_name = base_name
                    else:
                        model_name = f"{rel_dir}/{base_name}"
                    
                    meta_file = os.path.join(root, f"{base_name}_meta.json")
                    
                    # Determine type
                    lower_name = model_name.lower()
                    if "lightgbm" in lower_name:
                        model_type = "lightgbm"
                    elif "xgboost" in lower_name or "xgb" in lower_name:
                        model_type = "xgboost"
                    elif "cnn" in lower_name:
                        model_type = "cnn"
                    elif "gru" in lower_name:
                        model_type = "gru"
                    elif "transformer" in lower_name:
                        model_type = "transformer"
                    else:
                        model_type = "unknown"
                    
                    model_info = {
                        "name": model_name,
                        "file": filename,
                        "path": os.path.join(root, filename),
                        "type": model_type
                    }
                    
                    # Try to load metadata
                    if os.path.exists(meta_file):
                        try:
                            with open(meta_file, 'r') as f:
                                meta = json.load(f)
                                model_info["metadata"] = meta
                        except:
                            pass
                    
                    available_models.append(model_info)
    
    return {
        "models": available_models,
        "directory": models_dir
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
    # Calculate project root for resolving paths
    current_file = os.path.abspath(__file__)
    routers_dir = os.path.dirname(current_file)
    api_dir = os.path.dirname(routers_dir)
    backend_dir = os.path.dirname(api_dir)
    project_root = os.path.dirname(backend_dir)
    models_dir = os.path.join(project_root, "models")

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
            "created_at": m.created_at,
            "trained_at": m.trained_at,
            "source": "database",
            "metrics": {
                "accuracy": getattr(metric, "accuracy", None),
                "precision": getattr(metric, "precision_score", None),
                "recall": getattr(metric, "recall", None),
                "f1": getattr(metric, "f1_score", None)
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
            for filename in files:
                if filename.endswith(('.joblib', '.h5', '.keras')):
                    # Skip scaler files (ending with _scaler)
                    base_name = os.path.splitext(filename)[0]
                    if base_name.endswith('_scaler'):
                        continue
                    
                    # Determine model name relative to models_dir to handle subdirectories
                    rel_dir = os.path.relpath(root, models_dir)
                    
                    if rel_dir == '.':
                        model_name = base_name
                    else:
                        # e.g. experiment_123/lightgbm
                        model_name = f"{rel_dir}/{base_name}"
                    
                    # Skip if already in database
                    if model_name in db_model_names:
                        continue
                    
                    # Determine type
                    lower_name = model_name.lower()
                    if "lightgbm" in lower_name:
                        model_type = "lightgbm"
                    elif "xgboost" in lower_name or "xgb" in lower_name:
                        model_type = "xgboost"
                    elif "cnn" in lower_name:
                        model_type = "cnn"
                    elif "gru" in lower_name:
                        model_type = "gru"
                    elif "transformer" in lower_name:
                        model_type = "transformer"
                    else:
                        model_type = "unknown"
                    
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
                    
                    # Try to load metadata (filename_meta.json)
                    meta_file = os.path.join(root, f"{base_name}_meta.json")
                    if os.path.exists(meta_file):
                        try:
                            with open(meta_file, 'r') as f:
                                meta = json.load(f)
                                model_info["metrics"] = meta.get("metrics")
                                if meta.get("timestamp"):
                                    model_info["trained_at"] = datetime.fromtimestamp(meta["timestamp"]).isoformat()
                                if meta.get("type"):
                                    model_info["type"] = meta.get("type")
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
    
    if not model_type:
        raise HTTPException(status_code=400, detail="model_type is required")
    
    # Collect all dataset file paths
    dataset_files = []
    dataset_type = None
    
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
            metrics = tm.train_model(model_type, dataset_files, params=None, model_name=model_name, task_id=task_id, epochs=epochs)
            
            # Save to database using a new session
            db_session = SessionLocal()
            try:
                file_path = os.path.join("models", f"{model_name}.joblib")
                
                # Determine dataset type if not set
                if dataset_type is None:
                    first_path = dataset_files[0]
                    if 'NSL-KDD' in first_path or 'KDD' in first_path:
                        dataset_type = 'NSL-KDD'
                    elif 'CIC-IDS2017' in first_path or 'CIC' in first_path:
                        dataset_type = 'CIC-IDS2017'
                    else:
                        dataset_type = 'Mixed'
                
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

@router.post("/activate/{model_id}")
async def activate_model(
    model_id: int,
    model_name: Optional[str] = None,
    model_type: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
    engine: DetectionEngine = Depends(get_engine)
):
    if model_id > 0:
        # Database model
        m = db.query(ModelModel).filter(ModelModel.id == model_id).first()
        if not m:
            raise HTTPException(status_code=404, detail="Model not found")

        db.query(ModelModel).update({ModelModel.is_active: False})
        m.is_active = True
        db.commit()

        engine.current_model_name = m.name
        success = engine.inference_engine.load_model(m.name, m.type)
    else:
        # Preset model (negative ID) - need model_name and model_type from request
        if not model_name or not model_type:
            raise HTTPException(status_code=400, detail="model_name and model_type required for preset models")
        
        # Deactivate all database models
        db.query(ModelModel).update({ModelModel.is_active: False})
        db.commit()
        
        engine.current_model_name = model_name
        success = engine.inference_engine.load_model(model_name, model_type)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to load model into engine")

    return {"message": "Model activated", "name": engine.current_model_name}

@router.get("/metrics", response_model=List[dict])
async def list_model_metrics(
    model_id: Optional[int] = None,
    hours: int = 24,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List model metrics time series for charts
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    q = db.query(ModelMetricModel).filter(ModelMetricModel.timestamp >= since)
    if model_id:
        q = q.filter(ModelMetricModel.model_id == model_id)
    q = q.order_by(ModelMetricModel.timestamp.asc())
    rows = q.all()
    return [
        {
            "model_id": r.model_id,
            "timestamp": r.timestamp,
            "accuracy": r.accuracy,
            "precision": r.precision_score,
            "recall": r.recall,
            "f1": r.f1_score,
            "fpr": r.false_positive_rate,
            "fnr": r.false_negative_rate,
            "inference_time_ms": r.inference_time_ms
        } for r in rows
    ]


@router.delete("/{model_id}")
async def delete_model(
    model_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
    engine: DetectionEngine = Depends(get_engine)
):
    """
    Delete a model from database and optionally from disk
    """
    if model_id > 0:
        # Database model
        m = db.query(ModelModel).filter(ModelModel.id == model_id).first()
        if not m:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Check if model is currently active
        if m.is_active:
            raise HTTPException(status_code=400, detail="Cannot delete active model, please deactivate first")
        
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
