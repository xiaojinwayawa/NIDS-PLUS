"""
Experiments API Router
Provides endpoints for running and managing ML/DL experiments.
"""
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from auth import get_current_user, TokenData
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import os
import json
import uuid
import threading

from ml.experiment_runner import ExperimentRunner, ExperimentConfig, DatasetPreprocessor
from logging_config import app_logger as logger

router = APIRouter()

# Get project directories
_current_file = os.path.abspath(__file__)
_routers_dir = os.path.dirname(_current_file)
_api_dir = os.path.dirname(_routers_dir)
_backend_dir = os.path.dirname(_api_dir)
_project_root = os.path.dirname(_backend_dir)
_results_dir = os.path.join(_project_root, "data", "experiments")

# Store for async experiment tasks
_experiment_tasks: Dict[str, Dict[str, Any]] = {}


class ExperimentRequest(BaseModel):
    experiment_name: str
    dataset_type: str  # 'nsl-kdd' or 'cic-ids2017'
    model_types: List[str]  # ['lightgbm', 'xgboost', 'cnn', 'gru']
    random_seed: int = 42
    test_size: float = 0.2
    ml_num_boost_round: int = 100
    dl_epochs: int = 50
    dl_batch_size: int = 64
    fusion_strategy: str = "weighted"


class CompareRequest(BaseModel):
    dataset_type: str = "nsl-kdd"


@router.get("/")
async def list_experiments(
    limit: int = Query(50, ge=1, le=200),
    current_user: TokenData = Depends(get_current_user)
):
    """List all experiment results"""
    results = []
    
    if not os.path.exists(_results_dir):
        return results
    
    for filename in os.listdir(_results_dir):
        if filename.endswith('.json') and not filename.startswith('comparison') and not filename.startswith('export'):
            try:
                with open(os.path.join(_results_dir, filename), 'r') as f:
                    data = json.load(f)
                    results.append({
                        "experiment_id": data.get("experiment_id"),
                        "name": data.get("config", {}).get("experiment_name"),
                        "dataset_type": data.get("config", {}).get("dataset_type"),
                        "model_types": data.get("config", {}).get("model_types", []),
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
    
    for filename in os.listdir(_results_dir):
        if experiment_id in filename and filename.endswith('.json'):
            try:
                with open(os.path.join(_results_dir, filename), 'r') as f:
                    return json.load(f)
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
                fusion_strategy=request.fusion_strategy
            )
            
            runner = ExperimentRunner()
            
            _experiment_tasks[task_id]["message"] = "Training models..."
            _experiment_tasks[task_id]["progress"] = 30
            
            result = runner.run_experiment(config)
            
            _experiment_tasks[task_id]["status"] = "completed"
            _experiment_tasks[task_id]["progress"] = 100
            _experiment_tasks[task_id]["message"] = "Experiment completed"
            _experiment_tasks[task_id]["result"] = {
                "experiment_id": result.experiment_id,
                "accuracy": result.accuracy,
                "f1_score": result.f1_score,
                "training_time": result.training_time_sec
            }
            
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


@router.post("/compare")
async def run_comparative_experiments(
    request: CompareRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """Run comparative experiments (ML-only, DL-only, Hybrid)"""
    task_id = str(uuid.uuid4())
    
    _experiment_tasks[task_id] = {
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "experiment_name": f"Comparative_{request.dataset_type}",
        "progress": 0,
        "message": "Starting comparative experiments..."
    }
    
    def run_in_background():
        try:
            runner = ExperimentRunner()
            
            _experiment_tasks[task_id]["message"] = "Running ML-only experiment..."
            _experiment_tasks[task_id]["progress"] = 20
            
            results = runner.run_comparative_experiments(request.dataset_type)
            
            _experiment_tasks[task_id]["status"] = "completed"
            _experiment_tasks[task_id]["progress"] = 100
            _experiment_tasks[task_id]["message"] = "Comparative experiments completed"
            _experiment_tasks[task_id]["result"] = {
                "ml_only": {
                    "accuracy": results["ml_only"].accuracy,
                    "f1_score": results["ml_only"].f1_score
                },
                "dl_only": {
                    "accuracy": results["dl_only"].accuracy,
                    "f1_score": results["dl_only"].f1_score
                },
                "hybrid": {
                    "accuracy": results["hybrid"].accuracy,
                    "f1_score": results["hybrid"].f1_score
                }
            }
            
        except Exception as e:
            logger.error(f"Comparative experiments failed: {e}")
            _experiment_tasks[task_id]["status"] = "failed"
            _experiment_tasks[task_id]["message"] = str(e)
    
    thread = threading.Thread(target=run_in_background, daemon=True)
    thread.start()
    
    return {"task_id": task_id, "message": "Comparative experiments started"}


@router.get("/comparisons/")
async def list_comparison_reports(
    current_user: TokenData = Depends(get_current_user)
):
    """List comparison reports"""
    results = []
    
    if not os.path.exists(_results_dir):
        return results
    
    for filename in os.listdir(_results_dir):
        if filename.startswith('comparison') and filename.endswith('.json'):
            try:
                with open(os.path.join(_results_dir, filename), 'r') as f:
                    data = json.load(f)
                    results.append({
                        "filename": filename,
                        "dataset": data.get("dataset"),
                        "timestamp": data.get("timestamp"),
                        "comparison": data.get("comparison")
                    })
            except Exception as e:
                logger.error(f"Error reading comparison file {filename}: {e}")
    
    results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return results


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
                os.remove(os.path.join(_results_dir, filename))
                return {"message": "Experiment deleted"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(status_code=404, detail="Experiment not found")
