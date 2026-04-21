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
    FLOW_MIN_PACKETS: int = 3
    MULTICLASS_CONFIDENCE_THRESHOLD: float = 0.80
    ALERT_EVENT_COOLDOWN_SECONDS: int = 15
    ALERT_EVENT_RESOLVE_TIMEOUT_SECONDS: int = 30
    FLOW_AGGREGATION_TIMEOUT: float = 120.0
    FLOW_IDLE_TIMEOUT: float = 5.0
    FLOW_TCP_TIMEOUT: float = 120.0
    FLOW_UDP_TIMEOUT: float = 120.0
    FLOW_ICMP_TIMEOUT: float = 120.0
    FLOW_MAX_PACKETS: int = 500
    FLOW_ENABLE_BIDIRECTIONAL: bool = True
    PCAP_REPLAY_INTERVAL: float = 0.001
    FLOW_CHECK_INTERVAL: float = 0.5
    PIPELINE_IDLE_SLEEP: float = 0.05
    FLOW_CLEANUP_INTERVAL: float = 30.0
    #调参建议：
    #- 静默环境误报多：优先把 multiclass_confidence_threshold 从 0.80 提到 0.85
    #- 背景心跳包多：把 flow_min_packets 从 3 提到 4 或 5
    #- 怕漏掉短流探测：保留 flow_min_packets=3 ，只微调置信度阈值
    # Features
    
    ENABLE_SHAP: bool = True
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
