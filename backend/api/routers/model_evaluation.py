import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from auth import get_current_user, require_admin, TokenData
from ml.model_evaluation_service import (
    create_evaluation_task,
    delete_evaluation_result,
    export_evaluation_result_excel,
    get_evaluation_result,
    get_evaluation_task,
    list_csv_sources,
    list_evaluation_results,
    stop_evaluation_task,
)

router = APIRouter()


class EvaluationTaskCreateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    evaluation_name: str = Field(..., min_length=1, max_length=120)
    model_name: str
    model_type: str
    dataset_type: Optional[str] = None
    source_keys: list[str] = Field(..., min_length=1)
    label_column: Optional[str] = None
    batch_size: int = Field(2048, ge=128, le=20000)


@router.get("/sources")
async def get_evaluation_sources(current_user: TokenData = Depends(get_current_user)):
    return {"sources": list_csv_sources()}


@router.post("/tasks")
async def create_task(
    request: EvaluationTaskCreateRequest,
    current_user: TokenData = Depends(get_current_user),
):
    try:
        task = create_evaluation_task(
            {
                "evaluation_name": request.evaluation_name.strip(),
                "model_name": request.model_name,
                "model_type": request.model_type,
                "dataset_type": request.dataset_type,
                "source_keys": request.source_keys,
                "label_column": request.label_column,
                "batch_size": request.batch_size,
                "created_by": current_user.user_id,
                "created_by_name": current_user.username,
            }
        )
        return {"message": "总体模型评估任务已创建", "task": task}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    try:
        return get_evaluation_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Evaluation task not found")


@router.post("/tasks/{task_id}/stop")
async def stop_task(
    task_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    try:
        return stop_evaluation_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Evaluation task not found")


@router.get("/results")
async def get_results(current_user: TokenData = Depends(get_current_user)):
    return {"results": list_evaluation_results()}


@router.get("/results/{result_id}")
async def get_result(
    result_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    try:
        return get_evaluation_result(result_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation result not found")


@router.get("/results/{result_id}/export/excel")
async def export_result_excel(
    result_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    try:
        export_path = export_evaluation_result_excel(result_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation result not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not os.path.exists(export_path):
        raise HTTPException(status_code=404, detail="Export file not found")

    return FileResponse(
        export_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=os.path.basename(export_path),
    )


@router.delete("/results/{result_id}")
async def delete_result(
    result_id: str,
    current_user: TokenData = Depends(require_admin),
):
    try:
        delete_evaluation_result(result_id)
        return {"message": "Evaluation result deleted"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation result not found")
