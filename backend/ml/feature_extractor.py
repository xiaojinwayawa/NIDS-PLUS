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


WEB_SERVICE_PORTS = {80, 443, 8080, 8000, 8443}
FTP_SERVICE_PORTS = {20, 21, 989, 990}
SSH_SERVICE_PORTS = {22}
DNS_SERVICE_PORTS = {53}
MAIL_SERVICE_PORTS = {25, 110, 143, 465, 587, 993, 995}
DATABASE_SERVICE_PORTS = {1433, 1521, 3306, 5432, 6379, 27017}





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
        # 78 features based on CIC-IDS2017 dataset
        self.feature_names = [
            'Destination Port', 'Flow Duration', 'Total Fwd Packets', 'Total Backward Packets',
            'Total Length of Fwd Packets', 'Total Length of Bwd Packets', 'Fwd Packet Length Max',
            'Fwd Packet Length Min', 'Fwd Packet Length Mean', 'Fwd Packet Length Std',
            'Bwd Packet Length Max', 'Bwd Packet Length Min', 'Bwd Packet Length Mean',
            'Bwd Packet Length Std', 'Flow Bytes/s', 'Flow Packets/s', 'Flow IAT Mean',
            'Flow IAT Std', 'Flow IAT Max', 'Flow IAT Min', 'Fwd IAT Total', 'Fwd IAT Mean',
            'Fwd IAT Std', 'Fwd IAT Max', 'Fwd IAT Min', 'Bwd IAT Total', 'Bwd IAT Mean',
            'Bwd IAT Std', 'Bwd IAT Max', 'Bwd IAT Min', 'Fwd PSH Flags', 'Bwd PSH Flags',
            'Fwd URG Flags', 'Bwd URG Flags', 'Fwd Header Length', 'Bwd Header Length',
            'Fwd Packets/s', 'Bwd Packets/s', 'Min Packet Length', 'Max Packet Length',
            'Packet Length Mean', 'Packet Length Std', 'Packet Length Variance',
            'FIN Flag Count', 'SYN Flag Count', 'RST Flag Count', 'PSH Flag Count',
            'ACK Flag Count', 'URG Flag Count', 'CWE Flag Count', 'ECE Flag Count',
            'Down/Up Ratio', 'Average Packet Size', 'Avg Fwd Segment Size',
            'Avg Bwd Segment Size', 'Fwd Header Length.1', 'Fwd Avg Bytes/Bulk',
            'Fwd Avg Packets/Bulk', 'Fwd Avg Bulk Rate', 'Bwd Avg Bytes/Bulk',
            'Bwd Avg Packets/Bulk', 'Bwd Avg Bulk Rate', 'Subflow Fwd Packets',
            'Subflow Fwd Bytes', 'Subflow Bwd Packets', 'Subflow Bwd Bytes',
            'Init_Win_bytes_forward', 'Init_Win_bytes_backward', 'act_data_pkt_fwd',
            'min_seg_size_forward', 'Active Mean', 'Active Std', 'Active Max', 'Active Min',
            'Idle Mean', 'Idle Std', 'Idle Max', 'Idle Min'
        ]

    def get_feature_names(self) -> List[str]:
        return self.feature_names

    def extract_features(self, packet_data: Dict[str, Any]) -> np.ndarray:
        """
        Extract 78 features from packet data.
        For single packet analysis, many flow-based features are approximated.
        """
        features = np.zeros(78)
        
        try:
            # Basic packet info
            pkt_len = packet_data.get("length", 0)
            dst_port = packet_data.get("dst_port", 0)
            src_port = packet_data.get("src_port", 0)
            protocol = packet_data.get("protocol", "").upper()
            
            # TCP flags (if available)
            tcp_flags = packet_data.get("tcp_flags", {})
            
            # Feature extraction
            features[0] = dst_port  # Destination Port
            features[1] = 0  # Flow Duration (single packet = 0)
            features[2] = 1  # Total Fwd Packets
            features[3] = 0  # Total Backward Packets
            features[4] = pkt_len  # Total Length of Fwd Packets
            features[5] = 0  # Total Length of Bwd Packets
            features[6] = pkt_len  # Fwd Packet Length Max
            features[7] = pkt_len  # Fwd Packet Length Min
            features[8] = pkt_len  # Fwd Packet Length Mean
            features[9] = 0  # Fwd Packet Length Std
            features[10] = 0  # Bwd Packet Length Max
            features[11] = 0  # Bwd Packet Length Min
            features[12] = 0  # Bwd Packet Length Mean
            features[13] = 0  # Bwd Packet Length Std
            features[14] = pkt_len * 1000 if pkt_len > 0 else 0  # Flow Bytes/s (approximation)
            features[15] = 1000  # Flow Packets/s (approximation)
            features[16] = 0  # Flow IAT Mean
            features[17] = 0  # Flow IAT Std
            features[18] = 0  # Flow IAT Max
            features[19] = 0  # Flow IAT Min
            features[20] = 0  # Fwd IAT Total
            features[21] = 0  # Fwd IAT Mean
            features[22] = 0  # Fwd IAT Std
            features[23] = 0  # Fwd IAT Max
            features[24] = 0  # Fwd IAT Min
            features[25] = 0  # Bwd IAT Total
            features[26] = 0  # Bwd IAT Mean
            features[27] = 0  # Bwd IAT Std
            features[28] = 0  # Bwd IAT Max
            features[29] = 0  # Bwd IAT Min
            
            # TCP Flags
            features[30] = 1 if tcp_flags.get("PSH", False) else 0  # Fwd PSH Flags
            features[31] = 0  # Bwd PSH Flags
            features[32] = 1 if tcp_flags.get("URG", False) else 0  # Fwd URG Flags
            features[33] = 0  # Bwd URG Flags
            features[34] = 20 if protocol == "TCP" else 8  # Fwd Header Length
            features[35] = 0  # Bwd Header Length
            features[36] = 1000  # Fwd Packets/s
            features[37] = 0  # Bwd Packets/s
            features[38] = pkt_len  # Min Packet Length
            features[39] = pkt_len  # Max Packet Length
            features[40] = pkt_len  # Packet Length Mean
            features[41] = 0  # Packet Length Std
            features[42] = 0  # Packet Length Variance
            
            # Flag counts
            features[43] = 1 if tcp_flags.get("FIN", False) else 0  # FIN Flag Count
            features[44] = 1 if tcp_flags.get("SYN", False) else 0  # SYN Flag Count
            features[45] = 1 if tcp_flags.get("RST", False) else 0  # RST Flag Count
            features[46] = 1 if tcp_flags.get("PSH", False) else 0  # PSH Flag Count
            features[47] = 1 if tcp_flags.get("ACK", False) else 0  # ACK Flag Count
            features[48] = 1 if tcp_flags.get("URG", False) else 0  # URG Flag Count
            features[49] = 1 if tcp_flags.get("CWR", False) else 0  # CWE Flag Count
            features[50] = 1 if tcp_flags.get("ECE", False) else 0  # ECE Flag Count
            
            features[51] = 0  # Down/Up Ratio
            features[52] = pkt_len  # Average Packet Size
            features[53] = pkt_len  # Avg Fwd Segment Size
            features[54] = 0  # Avg Bwd Segment Size
            features[55] = 20 if protocol == "TCP" else 8  # Fwd Header Length.1
            features[56] = 0  # Fwd Avg Bytes/Bulk
            features[57] = 0  # Fwd Avg Packets/Bulk
            features[58] = 0  # Fwd Avg Bulk Rate
            features[59] = 0  # Bwd Avg Bytes/Bulk
            features[60] = 0  # Bwd Avg Packets/Bulk
            features[61] = 0  # Bwd Avg Bulk Rate
            features[62] = 1  # Subflow Fwd Packets
            features[63] = pkt_len  # Subflow Fwd Bytes
            features[64] = 0  # Subflow Bwd Packets
            features[65] = 0  # Subflow Bwd Bytes
            features[66] = packet_data.get("window_size", 65535)  # Init_Win_bytes_forward
            features[67] = 0  # Init_Win_bytes_backward
            features[68] = 1  # act_data_pkt_fwd
            features[69] = 20  # min_seg_size_forward
            features[70] = 0  # Active Mean
            features[71] = 0  # Active Std
            features[72] = 0  # Active Max
            features[73] = 0  # Active Min
            features[74] = 0  # Idle Mean
            features[75] = 0  # Idle Std
            features[76] = 0  # Idle Max
            features[77] = 0  # Idle Min
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting CIC-IDS2017 features: {e}")
            return np.zeros(78)

def get_extractor(dataset_type: str) -> FeatureExtractor:
    """Factory method to get extractor"""
    if dataset_type.lower() == "nsl-kdd":
        return NSLKDDFeatureExtractor()
    elif dataset_type.lower() == "cic-ids2017":
        return CICIDS2017FeatureExtractor()
    else:
        raise ValueError(f"Unknown dataset type: {dataset_type}")
