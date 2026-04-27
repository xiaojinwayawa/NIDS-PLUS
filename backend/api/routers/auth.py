from datetime import timedelta
from fastapi import APIRouter, HTTPException, Depends, status, Request
from auth import (
    Token, UserLogin, User, TokenData,
    authenticate_user, create_access_token, get_current_user,
    get_password_hash
)
from config import settings
from logging_config import app_logger as logger
from pydantic import BaseModel
from db.db_manager import SessionLocal
from db.models import UserModel
import time
import uuid
import base64
from io import BytesIO

try:
    from captcha.image import ImageCaptcha
except ImportError:
    # Handle environment where captcha isn't installed yet
    ImageCaptcha = None

router = APIRouter()

# Simple in-memory store for captchas (in production, use Redis)
_CAPTCHA_STORE = {}
CAPTCHA_EXPIRE_SECONDS = 60

class CaptchaResponse(BaseModel):
    captcha_id: str
    captcha_image_base64: str

class UserRegister(BaseModel):
    username: str
    password: str
    email: str = None
    captcha_id: str
    captcha_code: str

class UserLoginWithCaptcha(UserLogin):
    captcha_id: str
    captcha_code: str

def _clean_expired_captchas():
    """Remove expired captchas from memory"""
    now = time.time()
    expired_keys = [k for k, v in _CAPTCHA_STORE.items() if now - v["created_at"] > CAPTCHA_EXPIRE_SECONDS]
    for k in expired_keys:
        del _CAPTCHA_STORE[k]

@router.get("/captcha", response_model=CaptchaResponse)
async def generate_captcha():
    """Generate a new random 4-digit captcha"""
    if ImageCaptcha is None:
        raise HTTPException(status_code=500, detail="Captcha library not installed.")
        
    _clean_expired_captchas()
    
    import random
    code = "".join([str(random.randint(0, 9)) for _ in range(4)])
    captcha_id = str(uuid.uuid4())
    
    image = ImageCaptcha(width=120, height=40)
    data = image.generate(code)
    img_base64 = base64.b64encode(data.getvalue()).decode('utf-8')
    
    _CAPTCHA_STORE[captcha_id] = {
        "code": code,
        "created_at": time.time()
    }
    
    return CaptchaResponse(
        captcha_id=captcha_id,
        captcha_image_base64=f"data:image/png;base64,{img_base64}"
    )

@router.post("/register")
async def register_user(user_data: UserRegister):
    """Register a new normal user"""
    _clean_expired_captchas()
    
    # 1. Verify Captcha
    captcha_info = _CAPTCHA_STORE.get(user_data.captcha_id)
    if not captcha_info:
        raise HTTPException(status_code=400, detail="验证码已过期，请刷新图片。")
    if captcha_info["code"] != user_data.captcha_code:
        raise HTTPException(status_code=400, detail="验证码错误。")
        
    # Remove used captcha
    del _CAPTCHA_STORE[user_data.captcha_id]
    
    # 2. Database validation & creation
    db = SessionLocal()
    try:
        existing_user = db.query(UserModel).filter(UserModel.username == user_data.username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="用户名已存在。")
            
        new_user = UserModel(
            username=user_data.username,
            password_hash=get_password_hash(user_data.password),
            email=user_data.email,
            role="user", # Hardcode to normal user
            is_active=True
        )
        db.add(new_user)
        db.commit()
        
        logger.info(f"New user registered: {user_data.username}")
        return {"message": "注册成功，请登录。"}
    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="注册失败，内部错误。")
    finally:
        db.close()

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLoginWithCaptcha):
    """
    User login endpoint with captcha verification
    """
    _clean_expired_captchas()
    
    # 1. Verify Captcha first
    captcha_info = _CAPTCHA_STORE.get(user_credentials.captcha_id)
    if not captcha_info:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="验证码已过期，请刷新图片。")
    if captcha_info["code"] != user_credentials.captcha_code:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="验证码错误。")
        
    del _CAPTCHA_STORE[user_credentials.captcha_id]
    
    # 2. Verify Credentials
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
        "user_id": current_user.user_id,
        "role": current_user.role
    }
