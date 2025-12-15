from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import shutil
import os
import pandas as pd
from datetime import datetime

from auth import get_current_user, TokenData
from db.db_manager import get_db
from db.models import DatasetModel
from config import settings
from logging_config import app_logger as logger

router = APIRouter()

DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    type: str = Form(...),
    description: str = Form(None),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a new dataset (CSV)
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
    # Check if name exists
    existing = db.query(DatasetModel).filter(DatasetModel.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Dataset name already exists")
        
    try:
        # Save file
        file_path = os.path.join(DATA_DIR, f"{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Analyze file (get counts)
        df = pd.read_csv(file_path)
        sample_count = len(df)
        feature_count = len(df.columns) - 1 # Assume 1 target
        
        # Save metadata
        dataset = DatasetModel(
            name=name,
            type=type,
            file_path=file_path,
            sample_count=sample_count,
            feature_count=feature_count,
            uploaded_by=current_user.user_id,
            description=description
        )
        
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        
        logger.info(f"Dataset {name} uploaded by user {current_user.username}")
        
        return {
            "message": "Dataset uploaded successfully",
            "id": dataset.id,
            "sample_count": sample_count
        }
        
    except Exception as e:
        logger.error(f"Error uploading dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[dict])
async def list_datasets(
    skip: int = 0,
    limit: int = 100,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List available datasets"""
    datasets = db.query(DatasetModel).offset(skip).limit(limit).all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "type": d.type,
            "sample_count": d.sample_count,
            "created_at": d.created_at,
            "description": d.description
        }
        for d in datasets
    ]

@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a dataset"""
    dataset = db.query(DatasetModel).filter(DatasetModel.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    try:
        # Delete file
        if os.path.exists(dataset.file_path):
            os.remove(dataset.file_path)
            
        db.delete(dataset)
        db.commit()
        
        return {"message": "Dataset deleted successfully"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))
