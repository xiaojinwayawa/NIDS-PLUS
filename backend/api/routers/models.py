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

router = APIRouter()

# Store for async training tasks
_training_tasks: dict = {}

# Request models
class TrainRequest(BaseModel):
    model_type: str
    dataset_id: Optional[int] = None
    dataset_path: Optional[str] = None
    model_name: Optional[str] = None

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
        for filename in os.listdir(models_dir):
            if filename.endswith('.joblib'):
                model_name = filename.replace('.joblib', '')
                meta_file = os.path.join(models_dir, f"{model_name}_meta.json")
                
                model_info = {
                    "name": model_name,
                    "file": filename,
                    "path": os.path.join(models_dir, filename),
                    "type": "lightgbm" if "lightgbm" in model_name.lower() else "xgboost" if "xgboost" in model_name.lower() or "xgb" in model_name.lower() else "unknown"
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
    models = db.query(ModelModel).order_by(ModelModel.created_at.desc()).all()
    for m in models:
        db_model_names.add(m.name)
        metric = (
            db.query(ModelMetricModel)
            .filter(ModelMetricModel.model_id == m.id)
            .order_by(ModelMetricModel.timestamp.desc())
            .first()
        )
        result.append({
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
        })
    
    # 2. Scan preset models from models directory (not in database)
    current_file = os.path.abspath(__file__)
    routers_dir = os.path.dirname(current_file)
    api_dir = os.path.dirname(routers_dir)
    backend_dir = os.path.dirname(api_dir)
    project_root = os.path.dirname(backend_dir)
    models_dir = os.path.join(project_root, "models")
    
    preset_id = -1
    if os.path.exists(models_dir):
        for filename in os.listdir(models_dir):
            if filename.endswith('.joblib'):
                model_name = filename.replace('.joblib', '')
                
                # Skip if already in database
                if model_name in db_model_names:
                    continue
                
                meta_file = os.path.join(models_dir, f"{model_name}_meta.json")
                model_type = "lightgbm" if "lightgbm" in model_name.lower() else "xgboost" if "xgboost" in model_name.lower() or "xgb" in model_name.lower() else "unknown"
                
                model_info = {
                    "id": preset_id,
                    "name": model_name,
                    "type": model_type,
                    "version": "v1",
                    "file_path": os.path.join(models_dir, filename),
                    "dataset_type": "CIC-IDS2017",
                    "is_active": False,
                    "created_at": None,
                    "trained_at": None,
                    "source": "preset",
                    "metrics": None
                }
                
                # Try to load metadata
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
    dataset_path = request.dataset_path
    model_name = request.model_name
    
    if not model_type:
        raise HTTPException(status_code=400, detail="model_type is required")
    if not (dataset_id or dataset_path):
        raise HTTPException(status_code=400, detail="dataset_id or dataset_path is required")

    dataset_type = None
    
    if dataset_id:
        if dataset_id > 0:
            # Uploaded dataset from database
            d = db.query(DatasetModel).filter(DatasetModel.id == dataset_id).first()
            if not d:
                raise HTTPException(status_code=404, detail="Dataset not found")
            dataset_path = d.file_path
            dataset_type = d.type
        else:
            # Preset dataset - dataset_path should be provided by frontend
            if not dataset_path:
                raise HTTPException(status_code=400, detail="dataset_path is required for preset datasets")
    
    if not dataset_path:
        raise HTTPException(status_code=400, detail="Could not determine dataset path")

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
        try:
            tm = TrainingManager()
            metrics = tm.train_model(model_type, dataset_path, params=None, model_name=model_name, task_id=task_id)
            
            # Save to database using a new session
            db_session = SessionLocal()
            try:
                file_path = os.path.join("models", f"{model_name}.joblib")
                
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
