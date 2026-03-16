"""
User model definition
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, JSON, ForeignKey
from sqlalchemy.sql import func
from db.db_manager import Base

class UserModel(Base):
    """User database model"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<User(username='{self.username}', role='{self.role}')>"

class AlertModel(Base):
    """Alert database model"""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    src_ip = Column(String(45), nullable=False, index=True)
    dst_ip = Column(String(45), nullable=False)
    src_port = Column(Integer, nullable=True)
    dst_port = Column(Integer, nullable=True)
    protocol = Column(String(10), nullable=True)
    attack_type = Column(String(50), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=True) # Foreign key to models table (nullable)
    is_false_positive = Column(Boolean, default=False)
    marked_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    marked_at = Column(DateTime(timezone=True), nullable=True)
    raw_features = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<Alert(type='{self.attack_type}', src='{self.src_ip}')>"

class ModelModel(Base):
    """Trained model metadata"""
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)
    version = Column(String(20), nullable=False)
    file_path = Column(String(255), nullable=False)
    dataset_type = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    trained_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Model(name='{self.name}', type='{self.type}', version='{self.version}')>"

class ModelMetricModel(Base):
    """Model metrics records"""
    __tablename__ = "model_metrics"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    accuracy = Column(Float, nullable=True)
    precision_score = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
    false_positive_rate = Column(Float, nullable=True)
    false_negative_rate = Column(Float, nullable=True)
    inference_time_ms = Column(Float, nullable=True)

    def __repr__(self):
        return f"<ModelMetric(model_id={self.model_id}, f1={self.f1_score})>"

class DatasetModel(Base):
    """Dataset metadata model"""
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    type = Column(String(50), nullable=False) # nsl-kdd, cic-ids, custom
    file_path = Column(String(255), nullable=False)
    sample_count = Column(Integer, default=0)
    feature_count = Column(Integer, default=0)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    description = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<Dataset(name='{self.name}', type='{self.type}')>"
