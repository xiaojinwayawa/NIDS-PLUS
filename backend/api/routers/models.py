from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import os

from auth import get_current_user, TokenData
from db.db_manager import get_db
from db.models import ModelModel, ModelMetricModel, DatasetModel
from ml.trainer import TrainingManager
from ml.detection_engine import DetectionEngine
from config import settings

router = APIRouter()

def get_engine(request: Request) -> DetectionEngine:
    return request.app.state.engine

@router.get("/", response_model=List[dict])
async def list_models(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    models = db.query(ModelModel).order_by(ModelModel.created_at.desc()).all()
    result = []
    for m in models:
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
            "metrics": {
                "accuracy": getattr(metric, "accuracy", None),
                "precision": getattr(metric, "precision_score", None),
                "recall": getattr(metric, "recall", None),
                "f1": getattr(metric, "f1_score", None)
            } if metric else None
        })
    return result

@router.post("/train")
async def train_model(
    model_type: str,
    dataset_id: Optional[int] = None,
    dataset_path: Optional[str] = None,
    model_name: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not model_type:
        raise HTTPException(status_code=400, detail="model_type is required")
    if not (dataset_id or dataset_path):
        raise HTTPException(status_code=400, detail="dataset_id or dataset_path is required")

    if dataset_id:
        d = db.query(DatasetModel).filter(DatasetModel.id == dataset_id).first()
        if not d:
            raise HTTPException(status_code=404, detail="Dataset not found")
        dataset_path = d.file_path
        dataset_type = d.type
    else:
        dataset_type = None

    if not model_name:
        model_name = f"{model_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    tm = TrainingManager(models_dir="models")
    metrics = tm.train_model(model_type, dataset_path, params=None, model_name=model_name)

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
    db.add(model)
    db.commit()
    db.refresh(model)

    mm = ModelMetricModel(
        model_id=model.id,
        accuracy=metrics.get("accuracy"),
        precision_score=metrics.get("precision"),
        recall=metrics.get("recall"),
        f1_score=metrics.get("f1"),
        inference_time_ms=None
    )
    db.add(mm)
    db.commit()

    return {
        "message": "Training completed",
        "model_id": model.id,
        "metrics": metrics
    }

@router.post("/activate/{model_id}")
async def activate_model(
    model_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
    engine: DetectionEngine = Depends(get_engine)
):
    m = db.query(ModelModel).filter(ModelModel.id == model_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Model not found")

    db.query(ModelModel).update({ModelModel.is_active: False})
    m.is_active = True
    db.commit()

    engine.current_model_name = m.name
    success = engine.inference_engine.load_model(m.name, m.type)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to load model into engine")

    return {"message": "Model activated", "name": m.name}

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
