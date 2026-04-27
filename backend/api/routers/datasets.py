from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import shutil
import os
import pandas as pd
from datetime import datetime
from pydantic import BaseModel

from auth import get_current_user, TokenData
from db.db_manager import get_db
from db.models import DatasetModel
from config import settings
from logging_config import app_logger as logger

# Import the new data balancer
from ml.data_balancer import start_balance_task, get_balance_progress

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

class BalanceRequest(BaseModel):
    dataset_ids: List[int]
    output_name: str
    max_samples: int = 100000
    min_samples: int = 10000

@router.post("/balance")
async def balance_datasets(
    request: BalanceRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a background task to balance selected datasets
    using the Two-Pass Streaming Sequential Balancer
    """
    if not request.dataset_ids:
        raise HTTPException(status_code=400, detail="No datasets selected")
        
    if not request.output_name:
        raise HTTPException(status_code=400, detail="Output name is required")
        
    # Gather file paths
    input_files = []
    
    # 1. Check DB for uploaded/balanced datasets
    db_datasets = db.query(DatasetModel).filter(DatasetModel.id.in_(request.dataset_ids)).all()
    db_datasets_dict = {d.id: d.file_path for d in db_datasets}
    
    # 2. Check preset datasets
    datasets_base = os.path.join(project_root, "data", "datasets")
    preset_files = {}
    preset_id_counter = -1
    
    for root, dirs, files in os.walk(datasets_base):
        if 'uploads' in root or 'balanced' in root:
            continue
        for filename in files:
            if filename.endswith(('.csv', '.txt', '.arff')):
                preset_files[preset_id_counter] = os.path.join(root, filename)
                preset_id_counter -= 1
                
    for ds_id in request.dataset_ids:
        if ds_id > 0:
            if ds_id in db_datasets_dict:
                input_files.append(db_datasets_dict[ds_id])
            else:
                raise HTTPException(status_code=404, detail=f"Dataset {ds_id} not found")
        else:
            if ds_id in preset_files:
                input_files.append(preset_files[ds_id])
            else:
                raise HTTPException(status_code=404, detail=f"Preset dataset {ds_id} not found")
                
    if not input_files:
        raise HTTPException(status_code=400, detail="No valid input files resolved")
        
    # Define a callback to save the result to the database
    def db_callback(output_file_path):
        from db.db_manager import SessionLocal
        db_session = SessionLocal()
        try:
            # Determine dataset type based on inputs
            dataset_type = "Mixed"
            if all("CIC" in f or "IDS2017" in f for f in input_files):
                dataset_type = "CIC-IDS2017"
            elif all("KDD" in f for f in input_files):
                dataset_type = "NSL-KDD"
                
            # Create a relative path for the database
            rel_path = os.path.relpath(output_file_path, project_root)
            
            new_dataset = DatasetModel(
                name=f"{request.output_name} (Balanced)",
                type=dataset_type,
                file_path=rel_path,
                file_size=os.path.getsize(output_file_path),
                uploaded_at=datetime.utcnow()
            )
            db_session.add(new_dataset)
            db_session.commit()
        except Exception as e:
            logger.error(f"Failed to save balanced dataset to DB: {e}")
        finally:
            db_session.close()
            
    # Start the task
    try:
        task_id = start_balance_task(
            input_files=input_files,
            output_name=request.output_name,
            max_samples=request.max_samples,
            min_samples=request.min_samples,
            db_callback=db_callback
        )
        return {"message": "Data balancing started", "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/balance/progress/{task_id}")
async def get_balance_task_progress(
    task_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get the progress of a data balancing task"""
    progress = get_balance_progress(task_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Task not found")
    return progress

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
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "description": d.description,
            "source": "uploaded",
            "file_path": d.file_path
        })
    
    # 2. Scan pre-existing dataset directories (CIC-IDS2017, NSL-KDD, etc.)
    datasets_base = os.path.join(project_root, "data", "datasets")
    preset_id = -1  # Use negative IDs for preset datasets
    
    for root, dirs, files in os.walk(datasets_base):
        # Only skip uploads directory, INCLUDE balanced directory
        if 'uploads' in root:
            continue
            
        for filename in files:
            if filename.endswith(('.csv', '.txt', '.arff')):
                file_path = os.path.join(root, filename)
                
                # Get file info
                try:
                    file_stat = os.stat(file_path)
                    sample_count = None  # 不统计行数避免超时
                except:
                    file_stat = None
                    sample_count = 0
                
                name = filename
                if filename.endswith('.csv'):
                    name = filename[:-4]
                elif filename.endswith('.txt'):
                    name = filename[:-4]
                elif filename.endswith('.arff'):
                    name = filename[:-5]
                
                folder_name = os.path.basename(root)
                dataset_type = folder_name
                if "CIC-IDS2017" in file_path or "CIC-IDS-2017" in file_path or "ids2017" in file_path.lower():
                    dataset_type = "CIC-IDS2017"
                elif "KDD" in file_path:
                    dataset_type = "NSL-KDD"
                
                # Check if it's a balanced file
                display_name = name
                if 'balanced' in root:
                    display_name = f"[Balanced] {name}"
                
                result.append({
                    "id": preset_id,
                    "name": display_name,
                    "type": dataset_type,
                    "sample_count": sample_count,
                    "created_at": datetime.fromtimestamp(file_stat.st_mtime).isoformat() if file_stat else None,
                    "description": f"Pre-existing {dataset_type} dataset ({filename.split('.')[-1].upper()})",
                    "source": "preset",
                    "file_path": file_path
                })
                preset_id -= 1
    
    return result

@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Admin only: Delete a dataset"""
    from auth import require_admin
    await require_admin(current_user)
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
