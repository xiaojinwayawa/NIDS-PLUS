"""
Feature Extraction Module
Extracts features from network traffic data for ML models
"""
import abc
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Union, Optional
import joblib
import os
from logging_config import app_logger as logger

class FeatureExtractor(abc.ABC):
    """Base class for feature extraction"""
    
    def __init__(self):
        self.scaler = None
        self.encoders = {}
        
    @abc.abstractmethod
    def extract_features(self, packet_data: Dict[str, Any]) -> np.ndarray:
        """
        Extract features from a single packet dictionary
        
        Args:
            packet_data: Dictionary containing packet info (timestamp, src_ip, etc.)
            
        Returns:
            Numpy array of features
        """
        pass
        
    @abc.abstractmethod
    def get_feature_names(self) -> List[str]:
        """Get list of feature names"""
        pass

    def load_preprocessors(self, model_dir: str):
        """Load scaler and encoders from disk"""
        try:
            scaler_path = os.path.join(model_dir, "scaler.joblib")
            if os.path.exists(scaler_path):
                self.scaler = joblib.load(scaler_path)
                logger.info(f"Loaded scaler from {scaler_path}")
            else:
                logger.warning(f"Scaler not found at {scaler_path}")
                
            # Load encoders if needed (implementation depends on specific encoder storage)
        except Exception as e:
            logger.error(f"Error loading preprocessors: {e}")

    def preprocess(self, features: np.ndarray) -> np.ndarray:
        """Apply standardization/normalization"""
        if self.scaler:
            try:
                # Reshape for single sample if needed
                if features.ndim == 1:
                    features = features.reshape(1, -1)
                return self.scaler.transform(features)
            except Exception as e:
                logger.error(f"Error during preprocessing: {e}")
                return features
        return features

class NSLKDDFeatureExtractor(FeatureExtractor):
    """
    Feature extractor for NSL-KDD dataset (41 features)
    Note: Real-time extraction of all 41 KDD features from raw packets is complex 
    and requires flow-level state tracking (duration, counts, etc.).
    This is a simplified implementation for the prototype.
    """
    
    def __init__(self):
        super().__init__()
        # 41 features of NSL-KDD
        self.feature_names = [
            "duration", "protocol_type", "service", "flag", "src_bytes", "dst_bytes", 
            "land", "wrong_fragment", "urgent", "hot", "num_failed_logins", 
            "logged_in", "num_compromised", "root_shell", "su_attempted", 
            "num_root", "num_file_creations", "num_shells", "num_access_files", 
            "num_outbound_cmds", "is_host_login", "is_guest_login", "count", 
            "srv_count", "serror_rate", "srv_serror_rate", "rerror_rate", 
            "srv_rerror_rate", "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate", 
            "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate", 
            "dst_host_diff_srv_rate", "dst_host_same_src_port_rate", 
            "dst_host_srv_diff_host_rate", "dst_host_serror_rate", 
            "dst_host_srv_serror_rate", "dst_host_rerror_rate", "dst_host_srv_rerror_rate"
        ]
        
        # Mappings for categorical features (simplified)
        self.protocol_map = {"TCP": 1, "UDP": 2, "ICMP": 3}
        self.service_map = {"http": 1, "ftp": 2, "smtp": 3, "ssh": 4, "dns": 5, "other": 0}
        self.flag_map = {"SF": 1, "S0": 2, "REJ": 3, "other": 0}

    def get_feature_names(self) -> List[str]:
        return self.feature_names

    def extract_features(self, packet_data: Dict[str, Any]) -> np.ndarray:
        """
        Extract 41 features.
        NOTE: Many KDD features are flow-based (e.g., count, srv_count). 
        For this prototype, we will approximate or zero-out flow features 
        if state is not available, or use a simplified state tracker.
        """
        features = np.zeros(41)
        
        try:
            # 1. Basic features
            features[0] = 0 # duration (placeholder, requires flow tracking)
            
            # Protocol
            proto = packet_data.get("protocol", "OTHER").upper()
            features[1] = self.protocol_map.get(proto, 0)
            
            # Service (Simplistic port mapping)
            dst_port = packet_data.get("dst_port", 0)
            if dst_port == 80 or dst_port == 443:
                features[2] = self.service_map["http"]
            elif dst_port == 21:
                features[2] = self.service_map["ftp"]
            elif dst_port == 25:
                features[2] = self.service_map["smtp"]
            elif dst_port == 22:
                features[2] = self.service_map["ssh"]
            elif dst_port == 53:
                features[2] = self.service_map["dns"]
            else:
                features[2] = self.service_map["other"]
                
            # Flag (Simplistic, usually derived from TCP flags)
            # For now, assume normal (SF)
            features[3] = self.flag_map["SF"] 
            
            # Bytes
            features[4] = packet_data.get("length", 0) # src_bytes
            features[5] = 0 # dst_bytes (unknown in single packet direction)
            
            # ... (Fill other features with defaults or calculations)
            # For prototype, we ensure dimension consistency
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting NSL-KDD features: {e}")
            return np.zeros(41)

class CICIDS2017FeatureExtractor(FeatureExtractor):
    """
    Feature extractor for CIC-IDS2017 dataset (78 features)
    """
    
    def __init__(self):
        super().__init__()
        # 78 features (approximate list)
        self.feature_names = [f"f_{i}" for i in range(78)] 

    def get_feature_names(self) -> List[str]:
        return self.feature_names

    def extract_features(self, packet_data: Dict[str, Any]) -> np.ndarray:
        # Placeholder for CIC-IDS2017 extraction
        return np.zeros(78)

def get_extractor(dataset_type: str) -> FeatureExtractor:
    """Factory method to get extractor"""
    if dataset_type.lower() == "nsl-kdd":
        return NSLKDDFeatureExtractor()
    elif dataset_type.lower() == "cic-ids2017":
        return CICIDS2017FeatureExtractor()
    else:
        raise ValueError(f"Unknown dataset type: {dataset_type}")
