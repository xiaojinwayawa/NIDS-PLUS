from datetime import timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from auth import (
    Token, UserLogin, User, TokenData,
    authenticate_user, create_access_token, get_current_user
)
from config import settings
from logging_config import app_logger as logger

router = APIRouter()

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin):
    """
    User login endpoint
    """
    logger.info(f"Login attempt for user: {user_credentials.username}")
    
    user = authenticate_user(user_credentials.username, user_credentials.password)
    
    if not user:
        logger.warning(f"Login failed for user: {user_credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "role": user.role},
        expires_delta=access_token_expires
    )
    
    logger.info(f"User '{user.username}' logged in successfully")
    return Token(access_token=access_token, token_type="bearer")

@router.post("/logout")
async def logout(current_user: TokenData = Depends(get_current_user)):
    """User logout endpoint"""
    logger.info(f"User '{current_user.username}' logged out")
    return {
        "message": "Logged out successfully",
        "username": current_user.username
    }

@router.get("/verify")
async def verify_token(current_user: TokenData = Depends(get_current_user)):
    """Verify JWT token endpoint"""
    return {
        "valid": True,
        "username": current_user.username,
        "user_id": current_user.user_id
    }

@router.get("/me")
async def get_current_user_info(current_user: TokenData = Depends(get_current_user)):
    """Get current user information"""
    return {
        "username": current_user.username,
        "user_id": current_user.user_id
    }
