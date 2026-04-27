from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from auth import get_current_user, require_admin, TokenData
from db.db_manager import SessionLocal
from db.models import UserModel
from pydantic import BaseModel

router = APIRouter()

class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None
    role: str
    is_active: bool

    class Config:
        from_attributes = True

class UserCreateRequest(BaseModel):
    username: str
    password: str
    email: str | None = None
    role: str = "user"

@router.post("/", response_model=UserResponse)
async def create_user(request: UserCreateRequest, current_user: TokenData = Depends(require_admin)):
    """Admin only: create a new user"""
    from auth import get_password_hash
    db = SessionLocal()
    try:
        existing_user = db.query(UserModel).filter(UserModel.username == request.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
            
        if request.role not in ["admin", "user"]:
            raise HTTPException(status_code=400, detail="Invalid role specified")
            
        hashed_password = get_password_hash(request.password)
        new_user = UserModel(
            username=request.username,
            password_hash=hashed_password,
            email=request.email,
            role=request.role
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

@router.get("/", response_model=List[UserResponse])
async def get_all_users(current_user: TokenData = Depends(require_admin)):
    """Admin only: get all registered users"""
    db = SessionLocal()
    try:
        # Get all users except the original built-in admin
        # Using a convention: ID 1 is usually the original admin, or filter by name
        users = db.query(UserModel).filter(UserModel.username != "admin").all()
        return users
    finally:
        db.close()

@router.put("/{user_id}/role")
async def update_user_role(
    user_id: int, 
    role: str, # "admin" or "user"
    current_user: TokenData = Depends(require_admin)
):
    """Admin only: grant or revoke superadmin privileges"""
    if role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Invalid role specified")
        
    db = SessionLocal()
    try:
        if user_id == current_user.user_id:
            raise HTTPException(status_code=400, detail="Cannot modify your own role")
            
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.username == "admin":
            raise HTTPException(status_code=400, detail="Cannot modify the original admin account")
            
        user.role = role
        db.commit()
        return {"message": f"User '{user.username}' role updated to {role}"}
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

@router.delete("/{user_id}")
async def delete_user(
    user_id: int, 
    current_user: TokenData = Depends(require_admin)
):
    """Admin only: delete a user"""
    db = SessionLocal()
    try:
        if user_id == current_user.user_id:
            raise HTTPException(status_code=400, detail="Cannot delete your own account")
            
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.username == "admin":
            raise HTTPException(status_code=400, detail="Cannot delete the original admin account")
            
        db.delete(user)
        db.commit()
        return {"message": f"User '{user.username}' deleted successfully"}
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()