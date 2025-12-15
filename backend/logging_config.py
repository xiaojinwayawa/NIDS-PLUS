"""
Logging configuration for NIDS backend
Uses loguru for structured logging with rotation and retention
"""
import sys
from pathlib import Path
from loguru import logger
from config import settings


def setup_logging():
    """Configure logging for the application"""
    
    # Remove default handler
    logger.remove()
    
    # Console handler with color
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True,
    )
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # File handler with rotation
    logger.add(
        "logs/nids_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.LOG_LEVEL,
        rotation="00:00",  # Rotate at midnight
        retention="30 days",  # Keep logs for 30 days
        compression="zip",  # Compress old logs
        encoding="utf-8",
    )
    
    # Error file handler
    logger.add(
        "logs/nids_error_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="00:00",
        retention="90 days",  # Keep error logs longer
        compression="zip",
        encoding="utf-8",
    )
    
    logger.info("Logging system initialized")
    return logger


# Initialize logger
app_logger = setup_logging()
