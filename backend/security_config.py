"""
Security Configuration Module
Handles production security settings including CORS, secrets, and audit logging.

补充需求 F：生产安全强化（WebSocket/跨域/密钥）
"""
import os
import secrets
from typing import List, Optional
from datetime import datetime
from pydantic import BaseSettings
from logging_config import app_logger as logger


class SecuritySettings(BaseSettings):
    """
    Security-related settings loaded from environment variables.
    Follows the principle of least privilege and secure defaults.
    """
    
    # JWT Settings
    JWT_SECRET_KEY: str = ""  # Must be set in production
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # CORS Settings
    CORS_ORIGINS: str = ""  # Comma-separated list of allowed origins
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "GET,POST,PUT,DELETE,OPTIONS"
    CORS_ALLOW_HEADERS: str = "Authorization,Content-Type"
    
    # WebSocket Settings
    WS_REQUIRE_AUTH: bool = True
    WS_MAX_CONNECTIONS: int = 100
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    
    # Audit Logging
    AUDIT_LOG_ENABLED: bool = True
    AUDIT_LOG_FILE: str = "logs/audit.log"
    
    # Production Mode
    PRODUCTION_MODE: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_security_settings() -> SecuritySettings:
    """Get security settings instance"""
    return SecuritySettings()


def validate_security_config() -> List[str]:
    """
    Validate security configuration and return list of warnings/errors.
    Should be called at startup.
    """
    settings = get_security_settings()
    issues = []
    
    # Check JWT secret
    if not settings.JWT_SECRET_KEY:
        if settings.PRODUCTION_MODE:
            issues.append("CRITICAL: JWT_SECRET_KEY not set in production mode!")
        else:
            issues.append("WARNING: JWT_SECRET_KEY not set. Using generated key (not suitable for production)")
    elif len(settings.JWT_SECRET_KEY) < 32:
        issues.append("WARNING: JWT_SECRET_KEY is too short. Recommend at least 32 characters")
    
    # Check CORS
    if not settings.CORS_ORIGINS and settings.PRODUCTION_MODE:
        issues.append("WARNING: CORS_ORIGINS not configured. API may be inaccessible")
    elif settings.CORS_ORIGINS == "*":
        issues.append("WARNING: CORS allows all origins. Not recommended for production")
    
    # Check WebSocket auth
    if not settings.WS_REQUIRE_AUTH and settings.PRODUCTION_MODE:
        issues.append("WARNING: WebSocket authentication disabled in production")
    
    # Log issues
    for issue in issues:
        if issue.startswith("CRITICAL"):
            logger.error(issue)
        else:
            logger.warning(issue)
    
    return issues


def get_cors_origins() -> List[str]:
    """Get list of allowed CORS origins"""
    settings = get_security_settings()
    
    if not settings.CORS_ORIGINS:
        # Default for development
        return ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"]
    
    if settings.CORS_ORIGINS == "*":
        return ["*"]
    
    return [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]


def get_jwt_secret() -> str:
    """
    Get JWT secret key.
    Generates a random key if not configured (development only).
    """
    settings = get_security_settings()
    
    if settings.JWT_SECRET_KEY:
        return settings.JWT_SECRET_KEY
    
    # Generate random key for development
    if not settings.PRODUCTION_MODE:
        generated_key = secrets.token_hex(32)
        logger.warning(f"Generated temporary JWT secret (development only)")
        return generated_key
    
    raise ValueError("JWT_SECRET_KEY must be set in production mode")


class AuditLogger:
    """
    Audit logger for security-related events.
    Records authentication, authorization, and configuration changes.
    """
    
    def __init__(self):
        self.settings = get_security_settings()
        self._setup_audit_log()
    
    def _setup_audit_log(self):
        """Setup audit log file"""
        if not self.settings.AUDIT_LOG_ENABLED:
            return
        
        log_dir = os.path.dirname(self.settings.AUDIT_LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
    
    def log_event(self, 
                  event_type: str, 
                  user_id: Optional[int] = None,
                  username: Optional[str] = None,
                  ip_address: Optional[str] = None,
                  details: dict = None,
                  success: bool = True):
        """
        Log a security audit event.
        
        Args:
            event_type: Type of event (login, logout, config_change, etc.)
            user_id: User ID if applicable
            username: Username if applicable
            ip_address: Client IP address
            details: Additional event details
            success: Whether the action was successful
        """
        if not self.settings.AUDIT_LOG_ENABLED:
            return
        
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "username": username,
            "ip_address": ip_address,
            "success": success,
            "details": details or {}
        }
        
        # Log to file
        try:
            import json
            with open(self.settings.AUDIT_LOG_FILE, 'a') as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
        
        # Also log to application logger
        log_msg = f"AUDIT [{event_type}] user={username or user_id} success={success}"
        if success:
            logger.info(log_msg)
        else:
            logger.warning(log_msg)
    
    def log_login(self, username: str, ip_address: str, success: bool, reason: str = None):
        """Log login attempt"""
        self.log_event(
            event_type="login",
            username=username,
            ip_address=ip_address,
            success=success,
            details={"reason": reason} if reason else None
        )
    
    def log_logout(self, user_id: int, username: str):
        """Log logout"""
        self.log_event(
            event_type="logout",
            user_id=user_id,
            username=username,
            success=True
        )
    
    def log_config_change(self, user_id: int, config_key: str, old_value: str, new_value: str):
        """Log configuration change"""
        self.log_event(
            event_type="config_change",
            user_id=user_id,
            success=True,
            details={
                "config_key": config_key,
                "old_value": old_value,
                "new_value": new_value
            }
        )
    
    def log_access_denied(self, user_id: int, resource: str, reason: str):
        """Log access denied event"""
        self.log_event(
            event_type="access_denied",
            user_id=user_id,
            success=False,
            details={
                "resource": resource,
                "reason": reason
            }
        )


# Global audit logger instance
audit_logger = AuditLogger()


def configure_cors_middleware(app):
    """
    Configure CORS middleware for FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    from fastapi.middleware.cors import CORSMiddleware
    
    origins = get_cors_origins()
    settings = get_security_settings()
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS.split(","),
        allow_headers=settings.CORS_ALLOW_HEADERS.split(","),
    )
    
    logger.info(f"CORS configured with origins: {origins}")


def get_client_ip(request) -> str:
    """
    Get client IP address from request, handling proxies.
    
    Args:
        request: FastAPI/Starlette request object
        
    Returns:
        Client IP address
    """
    # Check for forwarded headers (behind proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Direct connection
    return request.client.host if request.client else "unknown"
