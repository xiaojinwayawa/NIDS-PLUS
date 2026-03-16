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

# Use project root data directory
# __file__ is backend/api/routers/datasets.py
current_file = os.path.abspath(__file__)
routers_dir = os.path.dirname(current_file)      # backend/api/routers
api_dir = os.path.dirname(routers_dir)           # backend/api
backend_dir = os.path.dirname(api_dir)           # backend
project_root = os.path.dirname(backend_dir)      # project_root
DATA_DIR = os.path.join(project_root, "data", "datasets", "uploads")

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
    """List available datasets (from database + pre-existing files)"""
    result = []
    
    # 1. Get datasets from database (uploaded ones)
    datasets = db.query(DatasetModel).offset(skip).limit(limit).all()
    for d in datasets:
        result.append({
            "id": d.id,
            "name": d.name,
            "type": d.type,
            "sample_count": d.sample_count,
            "created_at": d.created_at,
            "description": d.description,
            "source": "uploaded"
        })
    
    # 2. Scan pre-existing dataset directories (CIC-IDS2017, NSL-KDD, etc.)
    datasets_base = os.path.join(project_root, "data", "datasets")
    preset_id = -1  # Use negative IDs for preset datasets
    
    for folder_name in os.listdir(datasets_base):
        folder_path = os.path.join(datasets_base, folder_name)
        # Skip uploads folder and non-directories
        if folder_name == "uploads" or not os.path.isdir(folder_path):
            continue
        
        # Find CSV, TXT, and ARFF files in this folder
        dataset_files = [f for f in os.listdir(folder_path) if f.endswith(('.csv', '.txt', '.arff'))]
        for csv_file in dataset_files:
            csv_path = os.path.join(folder_path, csv_file)
            # Get file info
            try:
                file_stat = os.stat(csv_path)
                # Quick row count estimate (read first few lines)
                with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
                    # Count lines (approximate)
                    sample_count = sum(1 for _ in f) - 1  # Subtract header
            except:
                sample_count = 0
            
            name = csv_file
            if csv_file.endswith('.csv'):
                name = csv_file[:-4]
            elif csv_file.endswith('.txt'):
                name = csv_file[:-4]
            elif csv_file.endswith('.arff'):
                name = csv_file[:-5]
            
            result.append({
                "id": preset_id,
                "name": name,
                "type": folder_name,
                "sample_count": sample_count,
                "created_at": datetime.fromtimestamp(file_stat.st_mtime).isoformat() if file_stat else None,
                "description": f"Pre-existing {folder_name} dataset ({csv_file.split('.')[-1].upper()})",
                "source": "preset",
                "file_path": csv_path
            })
            preset_id -= 1
    
    return result

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


@router.get("/pcaps")
async def list_pcap_files(
    current_user: TokenData = Depends(get_current_user)
):
    """List available PCAP files in data/pcaps directory"""
    pcap_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "pcaps")
    
    # Fallback paths
    possible_paths = [
        pcap_dir,
        "../data/pcaps",
        "data/pcaps",
        "./data/pcaps"
    ]
    
    pcap_files = []
    used_path = None
    
    for path in possible_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path) and os.path.isdir(abs_path):
            used_path = abs_path
            break
    
    if used_path:
        for f in os.listdir(used_path):
            if f.endswith('.pcap') or f.endswith('.pcapng'):
                file_path = os.path.join(used_path, f)
                file_size = os.path.getsize(file_path)
                pcap_files.append({
                    "name": f,
                    "path": file_path,
                    "size": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2)
                })
    
    return {
        "directory": used_path,
        "files": sorted(pcap_files, key=lambda x: x["name"])
    }
