from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
import os
from pathlib import Path
from auth import get_current_user, TokenData

router = APIRouter()
LOGS_DIR = Path("logs")

@router.get("/", response_model=List[str])
async def list_log_files(
    current_user: TokenData = Depends(get_current_user)
):
    """List available log files"""
    if not LOGS_DIR.exists():
        return []
        
    # List .log files
    files = [f.name for f in LOGS_DIR.glob("*.log")]
    # Also .zip files if any
    files.extend([f.name for f in LOGS_DIR.glob("*.zip")])
    
    # Sort by modification time desc
    files.sort(key=lambda x: (LOGS_DIR / x).stat().st_mtime, reverse=True)
    return files

@router.get("/{filename}")
async def get_log_content(
    filename: str,
    lines: int = Query(100, ge=1, le=1000),
    current_user: TokenData = Depends(get_current_user)
):
    """Get content of a log file (tail)"""
    file_path = LOGS_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")
        
    # Basic path traversal protection
    if not file_path.resolve().is_relative_to(LOGS_DIR.resolve()):
         raise HTTPException(status_code=403, detail="Access denied")
         
    try:
        # Simple tail implementation
        with open(file_path, "r", encoding="utf-8") as f:
            # Read all lines is inefficient for large files, but for prototype ok
            # Better: seek from end
            all_lines = f.readlines()
            return {"content": all_lines[-lines:]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{filename}")
async def delete_log_file(
    filename: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Delete a log file"""
    file_path = LOGS_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")
        
    # Basic path traversal protection
    if not file_path.resolve().is_relative_to(LOGS_DIR.resolve()):
         raise HTTPException(status_code=403, detail="Access denied")
         
    try:
        file_path.unlink()
        return {"message": f"Log file {filename} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
