"""
Database connection manager
Supports MySQL (primary) and SQLite (fallback)
Handles connection pooling and session management
"""
import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from config import settings
from logging_config import app_logger as logger

# Determine database type
USE_SQLITE = os.environ.get("USE_SQLITE", "false").lower() == "true"

if USE_SQLITE:
    # SQLite for development/testing
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(backend_dir, "data", "nids.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    DATABASE_URL = f"sqlite:///{db_path}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    logger.info(f"Using SQLite database: {db_path}")
else:
    # MySQL for production
    DATABASE_URL = f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    try:
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600
        )
        logger.info(f"Database engine created for MySQL host: {settings.MYSQL_HOST}")
    except Exception as e:
        logger.warning(f"MySQL connection failed: {e}, falling back to SQLite")
        # Fallback to SQLite
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(backend_dir, "data", "nids.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        DATABASE_URL = f"sqlite:///{db_path}"
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False}
        )
        logger.info(f"Fallback to SQLite database: {db_path}")

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session
    
    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
