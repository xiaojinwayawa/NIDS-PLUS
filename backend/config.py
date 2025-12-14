"""Configuration management for NIDS backend"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # API Settings
    API_V1_PREFIX: str = "/api"
    PROJECT_NAME: str = "NIDS System"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # Database
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "nids"
    MYSQL_PASSWORD: str = "nids_password"
    MYSQL_DATABASE: str = "nids_db"
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # Traffic Capture
    TRAFFIC_SOURCE_MODE: str = "pcap"  # 'pcap' or 'live'
    PCAP_FILE_PATH: str = "./data/pcaps/sample.pcap"
    NETWORK_INTERFACE: str = "eth0"
    
    # Detection Engine
    BATCH_SIZE: int = 100
    INFERENCE_INTERVAL_MS: int = 50
    ALERT_THRESHOLD: float = 0.8
    MAX_QUEUE_SIZE: int = 10000
    
    # Features
    ENABLE_SHAP: bool = True
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
