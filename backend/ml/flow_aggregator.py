"""
Flow Aggregator Module
Aggregates network packets into flows based on 5-tuple and extracts flow-level features.
Supports sequence sample construction for deep learning models.

补充需求 C：流级特征提取与序列样本构造
"""
import time
import threading
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

from config import settings
from logging_config import app_logger as logger



class FlowState(Enum):
    """Flow lifecycle states"""
    ACTIVE = "active"
    IDLE = "idle"
    FINISHED = "finished"
    TIMEOUT = "timeout"


@dataclass
class FlowKey:
    """5-tuple flow identifier"""
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    
    def __hash__(self):
        return hash((self.src_ip, self.dst_ip, self.src_port, self.dst_port, self.protocol))
    
    def __eq__(self, other):
        if not isinstance(other, FlowKey):
            return False
        return (self.src_ip == other.src_ip and 
                self.dst_ip == other.dst_ip and
                self.src_port == other.src_port and
                self.dst_port == other.dst_port and
                self.protocol == other.protocol)
    
    def reverse(self) -> 'FlowKey':
        """Get reverse direction flow key"""
        return FlowKey(
            src_ip=self.dst_ip,
            dst_ip=self.src_ip,
            src_port=self.dst_port,
            dst_port=self.src_port,
            protocol=self.protocol
        )


@dataclass
class FlowRecord:
    """Stores aggregated flow statistics"""
    flow_key: FlowKey
    state: FlowState = FlowState.ACTIVE
    
    # Timing
    start_time: float = 0.0
    last_update_time: float = 0.0
    duration: float = 0.0
    
    # Packet counts
    fwd_packets: int = 0
    bwd_packets: int = 0
    total_packets: int = 0
    
    # Byte counts
    fwd_bytes: int = 0
    bwd_bytes: int = 0
    total_bytes: int = 0
    
    # Packet lengths (for statistics)
    fwd_packet_lengths: List[int] = field(default_factory=list)
    bwd_packet_lengths: List[int] = field(default_factory=list)
    
    # Inter-arrival times
    fwd_iats: List[float] = field(default_factory=list)
    bwd_iats: List[float] = field(default_factory=list)
    flow_iats: List[float] = field(default_factory=list)
    
    # Last packet times for IAT calculation
    last_fwd_time: float = 0.0
    last_bwd_time: float = 0.0
    last_packet_time: float = 0.0
    
    # TCP flags
    fin_count: int = 0
    syn_count: int = 0
    rst_count: int = 0
    psh_count: int = 0
    ack_count: int = 0
    urg_count: int = 0
    cwe_count: int = 0
    ece_count: int = 0
    
    # Window sizes
    init_win_fwd: int = 0
    init_win_bwd: int = 0
    
    # Active/Idle tracking
    active_times: List[float] = field(default_factory=list)
    idle_times: List[float] = field(default_factory=list)
    
    # Raw packets for sequence models
    packet_sequence: List[Dict[str, Any]] = field(default_factory=list)


class FlowAggregatorConfig:
    """Configuration for flow aggregation"""
    def __init__(self,
                 flow_timeout: float = 120.0,      # Flow timeout in seconds
                 idle_timeout: float = 60.0,       # Idle timeout in seconds
                 max_packets_per_flow: int = 1000, # Max packets to store per flow
                 sequence_window_size: int = 100,  # Window size for sequence samples
                 sequence_step_size: int = 50,     # Step size for sliding window
                 enable_bidirectional: bool = True, # Track bidirectional flows
                 tcp_flow_timeout: float = 30.0,    # TCP flow timeout
                 udp_flow_timeout: float = 5.0,     # UDP flow timeout (shorter)
                 icmp_flow_timeout: float = 2.0,    # ICMP flow timeout (very short)
                 fin_immediate_close: bool = True   # Immediately close flow on FIN/RST flag
                 ):
        self.flow_timeout = flow_timeout
        self.idle_timeout = idle_timeout
        self.max_packets_per_flow = max_packets_per_flow
        self.sequence_window_size = sequence_window_size
        self.sequence_step_size = sequence_step_size
        self.enable_bidirectional = enable_bidirectional
        self.tcp_flow_timeout = tcp_flow_timeout
        self.udp_flow_timeout = udp_flow_timeout
        self.icmp_flow_timeout = icmp_flow_timeout
        self.fin_immediate_close = fin_immediate_close


class FlowAggregator:
    """
    Aggregates packets into flows and extracts flow-level features.
    Supports both traditional ML features and sequence samples for DL models.
    """
    
    def __init__(self, config: FlowAggregatorConfig = None):
        self.config = config or FlowAggregatorConfig()
        self.flows: Dict[FlowKey, FlowRecord] = {}
        self.lock = threading.RLock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
    def start(self):
        """Start background cleanup thread"""
        self._stop_event.clear()
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        logger.info("Flow aggregator started")
        
    def stop(self):
        """Stop background cleanup thread"""
        self._stop_event.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)
        logger.info("Flow aggregator stopped")
    
    def _cleanup_loop(self):
        """Background thread to clean up expired flows"""
        while not self._stop_event.is_set():
            try:
                self._cleanup_expired_flows()
            except Exception as e:
                logger.error(f"Error in flow cleanup: {e}")
            time.sleep(settings.FLOW_CLEANUP_INTERVAL)
    
    def _cleanup_expired_flows(self):
        """Remove expired flows and return them for processing"""
        current_time = time.time()
        expired_flows = []
        
        with self.lock:
            keys_to_remove = []
            for key, flow in self.flows.items():
                time_since_update = current_time - flow.last_update_time
                
                protocol = flow.flow_key.protocol.upper()
                
                # Get timeout based on protocol
                if protocol == 'TCP':
                    timeout = getattr(self.config, 'tcp_flow_timeout', self.config.flow_timeout)
                elif protocol == 'UDP':
                    timeout = getattr(self.config, 'udp_flow_timeout', self.config.flow_timeout)
                elif protocol == 'ICMP':
                    timeout = getattr(self.config, 'icmp_flow_timeout', self.config.flow_timeout)
                else:
                    timeout = self.config.flow_timeout
                
                # Check for timeout
                if time_since_update > timeout:
                    flow.state = FlowState.TIMEOUT
                    expired_flows.append(flow)
                    keys_to_remove.append(key)
                elif time_since_update > self.config.idle_timeout:
                    flow.state = FlowState.IDLE
                    expired_flows.append(flow)
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.flows[key]
        
        if expired_flows:
            logger.debug(f"Cleaned up {len(expired_flows)} expired flows")
        
        return expired_flows
    def cleanup_and_get_expired_flows(self):
        """Public method to cleanup and return expired flows for detection"""
        return self._cleanup_expired_flows()

    def add_packet(self, packet_data):
        """
        Add a packet to its corresponding flow.
        Returns the flow record if it's complete/ready for processing.
        
        Args:
            packet_data: Dictionary with packet info (src_ip, dst_ip, etc.)
            
        Returns:
            FlowRecord if flow is complete, None otherwise
        """
        current_time = time.time()
        
        # Extract flow key from packet
        flow_key = self._extract_flow_key(packet_data)
        if not flow_key:
            return None
        
        # Determine direction (forward or backward)
        is_forward = True
        reverse_key = flow_key.reverse()
        
        with self.lock:
            # Check if this is a reverse flow
            if self.config.enable_bidirectional and reverse_key in self.flows:
                flow_key = reverse_key
                is_forward = False
            
            # Get or create flow record
            if flow_key not in self.flows:
                flow = FlowRecord(
                    flow_key=flow_key,
                    start_time=current_time,
                    last_update_time=current_time,
                    last_packet_time=current_time
                )
                self.flows[flow_key] = flow
            else:
                flow = self.flows[flow_key]
            
            # Update flow with packet data
            self._update_flow(flow, packet_data, is_forward, current_time)
            
            # Check if flow is finished (FIN or RST flag) - controlled by config
            tcp_flags = packet_data.get("tcp_flags", {})
            if self.config.fin_immediate_close and (tcp_flags.get("FIN") or tcp_flags.get("RST")):
                flow.state = FlowState.FINISHED
                del self.flows[flow_key]
                return flow
            
            # Check if max packets reached
            if flow.total_packets >= self.config.max_packets_per_flow:
                flow.state = FlowState.FINISHED
                del self.flows[flow_key]
                return flow
        
        return None
    
    def _extract_flow_key(self, packet_data: Dict[str, Any]) -> Optional[FlowKey]:
        """Extract 5-tuple flow key from packet data"""
        try:
            src_ip = packet_data.get("src_ip", "")
            dst_ip = packet_data.get("dst_ip", "")
            src_port = packet_data.get("src_port", 0)
            dst_port = packet_data.get("dst_port", 0)
            protocol = packet_data.get("protocol", "TCP").upper()
            
            if not src_ip or not dst_ip:
                return None
            
            return FlowKey(
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_port=src_port or 0,
                dst_port=dst_port or 0,
                protocol=protocol
            )
        except Exception as e:
            logger.error(f"Error extracting flow key: {e}")
            return None
    
    def _update_flow(self, flow: FlowRecord, packet_data: Dict[str, Any], 
                     is_forward: bool, current_time: float):
        """Update flow record with packet data"""
        pkt_len = packet_data.get("length", 0)
        tcp_flags = packet_data.get("tcp_flags", {})
        
        # Update timing
        flow.last_update_time = current_time
        flow.duration = current_time - flow.start_time
        
        # Calculate IAT
        if flow.last_packet_time > 0:
            iat = current_time - flow.last_packet_time
            flow.flow_iats.append(iat)
        flow.last_packet_time = current_time
        
        # Update direction-specific stats
        if is_forward:
            flow.fwd_packets += 1
            flow.fwd_bytes += pkt_len
            flow.fwd_packet_lengths.append(pkt_len)
            
            if flow.last_fwd_time > 0:
                fwd_iat = current_time - flow.last_fwd_time
                flow.fwd_iats.append(fwd_iat)
            flow.last_fwd_time = current_time
            
            # First forward packet - capture window size
            if flow.fwd_packets == 1:
                flow.init_win_fwd = packet_data.get("window_size", 0)
        else:
            flow.bwd_packets += 1
            flow.bwd_bytes += pkt_len
            flow.bwd_packet_lengths.append(pkt_len)
            
            if flow.last_bwd_time > 0:
                bwd_iat = current_time - flow.last_bwd_time
                flow.bwd_iats.append(bwd_iat)
            flow.last_bwd_time = current_time
            
            # First backward packet - capture window size
            if flow.bwd_packets == 1:
                flow.init_win_bwd = packet_data.get("window_size", 0)
        
        # Update totals
        flow.total_packets = flow.fwd_packets + flow.bwd_packets
        flow.total_bytes = flow.fwd_bytes + flow.bwd_bytes
        
        # Update TCP flags
        if tcp_flags.get("FIN"):
            flow.fin_count += 1
        if tcp_flags.get("SYN"):
            flow.syn_count += 1
        if tcp_flags.get("RST"):
            flow.rst_count += 1
        if tcp_flags.get("PSH"):
            flow.psh_count += 1
        if tcp_flags.get("ACK"):
            flow.ack_count += 1
        if tcp_flags.get("URG"):
            flow.urg_count += 1
        if tcp_flags.get("CWR"):
            flow.cwe_count += 1
        if tcp_flags.get("ECE"):
            flow.ece_count += 1
        
        # Store packet for sequence models (limited)
        if len(flow.packet_sequence) < self.config.max_packets_per_flow:
            flow.packet_sequence.append({
                "timestamp": current_time,
                "length": pkt_len,
                "is_forward": is_forward,
                "flags": tcp_flags
            })
    
    def get_active_flows(self) -> List[FlowRecord]:
        """Get all active flows"""
        with self.lock:
            return list(self.flows.values())
    
    def get_flow_count(self) -> int:
        """Get number of active flows"""
        with self.lock:
            return len(self.flows)
    
    def force_export_all(self) -> List[FlowRecord]:
        """Force export all flows (for shutdown)"""
        with self.lock:
            flows = list(self.flows.values())
            self.flows.clear()
            return flows


class FlowFeatureExtractor:
    """
    Extracts features from FlowRecord for ML/DL models.
    Supports both CIC-IDS2017 style features and sequence samples.
    """
    
    def __init__(self):
        self.feature_names = self._get_feature_names()
        self.lock = threading.Lock()
    
    def _get_feature_names(self) -> List[str]:
        """Get list of flow feature names (CIC-IDS2017 compatible)"""
        return [
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
    
    def extract_features(self, flow: FlowRecord) -> np.ndarray:
        """
        Extract 78 CIC-IDS2017 compatible features from a flow record.
        
        Args:
            flow: FlowRecord with aggregated flow statistics
            
        Returns:
            numpy array of 78 features
        """
        features = np.zeros(78)
        
        try:
            # Basic flow info
            features[0] = flow.flow_key.dst_port  # Destination Port
            features[1] = flow.duration * 1e6  # Flow Duration (microseconds)
            features[2] = flow.fwd_packets  # Total Fwd Packets
            features[3] = flow.bwd_packets  # Total Backward Packets
            features[4] = flow.fwd_bytes  # Total Length of Fwd Packets
            features[5] = flow.bwd_bytes  # Total Length of Bwd Packets
            
            # Forward packet length stats
            if flow.fwd_packet_lengths:
                features[6] = max(flow.fwd_packet_lengths)  # Fwd Packet Length Max
                features[7] = min(flow.fwd_packet_lengths)  # Fwd Packet Length Min
                features[8] = np.mean(flow.fwd_packet_lengths)  # Fwd Packet Length Mean
                features[9] = np.std(flow.fwd_packet_lengths) if len(flow.fwd_packet_lengths) > 1 else 0  # Std
            
            # Backward packet length stats
            if flow.bwd_packet_lengths:
                features[10] = max(flow.bwd_packet_lengths)  # Bwd Packet Length Max
                features[11] = min(flow.bwd_packet_lengths)  # Bwd Packet Length Min
                features[12] = np.mean(flow.bwd_packet_lengths)  # Bwd Packet Length Mean
                features[13] = np.std(flow.bwd_packet_lengths) if len(flow.bwd_packet_lengths) > 1 else 0  # Std
            
            # Flow rates
            duration_sec = max(flow.duration, 0.001)  # Avoid division by zero
            features[14] = flow.total_bytes / duration_sec  # Flow Bytes/s
            features[15] = flow.total_packets / duration_sec  # Flow Packets/s
            
            # Flow IAT stats
            if flow.flow_iats:
                features[16] = np.mean(flow.flow_iats) * 1e6  # Flow IAT Mean (us)
                features[17] = np.std(flow.flow_iats) * 1e6 if len(flow.flow_iats) > 1 else 0  # Std
                features[18] = max(flow.flow_iats) * 1e6  # Max
                features[19] = min(flow.flow_iats) * 1e6  # Min
            
            # Forward IAT stats
            if flow.fwd_iats:
                features[20] = sum(flow.fwd_iats) * 1e6  # Fwd IAT Total
                features[21] = np.mean(flow.fwd_iats) * 1e6  # Mean
                features[22] = np.std(flow.fwd_iats) * 1e6 if len(flow.fwd_iats) > 1 else 0  # Std
                features[23] = max(flow.fwd_iats) * 1e6  # Max
                features[24] = min(flow.fwd_iats) * 1e6  # Min
            
            # Backward IAT stats
            if flow.bwd_iats:
                features[25] = sum(flow.bwd_iats) * 1e6  # Bwd IAT Total
                features[26] = np.mean(flow.bwd_iats) * 1e6  # Mean
                features[27] = np.std(flow.bwd_iats) * 1e6 if len(flow.bwd_iats) > 1 else 0  # Std
                features[28] = max(flow.bwd_iats) * 1e6  # Max
                features[29] = min(flow.bwd_iats) * 1e6  # Min
            
            # TCP flags (simplified - count PSH/URG in forward direction)
            features[30] = flow.psh_count  # Fwd PSH Flags (approximation)
            features[31] = 0  # Bwd PSH Flags
            features[32] = flow.urg_count  # Fwd URG Flags
            features[33] = 0  # Bwd URG Flags
            
            # Header lengths (approximation)
            features[34] = flow.fwd_packets * 20  # Fwd Header Length
            features[35] = flow.bwd_packets * 20  # Bwd Header Length
            
            # Packets per second
            features[36] = flow.fwd_packets / duration_sec  # Fwd Packets/s
            features[37] = flow.bwd_packets / duration_sec  # Bwd Packets/s
            
            # All packet length stats
            all_lengths = flow.fwd_packet_lengths + flow.bwd_packet_lengths
            if all_lengths:
                features[38] = min(all_lengths)  # Min Packet Length
                features[39] = max(all_lengths)  # Max Packet Length
                features[40] = np.mean(all_lengths)  # Packet Length Mean
                features[41] = np.std(all_lengths) if len(all_lengths) > 1 else 0  # Std
                features[42] = np.var(all_lengths) if len(all_lengths) > 1 else 0  # Variance
            
            # Flag counts
            features[43] = flow.fin_count
            features[44] = flow.syn_count
            features[45] = flow.rst_count
            features[46] = flow.psh_count
            features[47] = flow.ack_count
            features[48] = flow.urg_count
            features[49] = flow.cwe_count
            features[50] = flow.ece_count
            
            # Ratios
            features[51] = flow.bwd_packets / flow.fwd_packets if flow.fwd_packets > 0 else 0  # Down/Up Ratio
            features[52] = flow.total_bytes / flow.total_packets if flow.total_packets > 0 else 0  # Avg Packet Size
            features[53] = flow.fwd_bytes / flow.fwd_packets if flow.fwd_packets > 0 else 0  # Avg Fwd Segment Size
            features[54] = flow.bwd_bytes / flow.bwd_packets if flow.bwd_packets > 0 else 0  # Avg Bwd Segment Size
            
            # Additional features
            features[55] = flow.fwd_packets * 20  # Fwd Header Length.1
            features[56] = 0  # Fwd Avg Bytes/Bulk
            features[57] = 0  # Fwd Avg Packets/Bulk
            features[58] = 0  # Fwd Avg Bulk Rate
            features[59] = 0  # Bwd Avg Bytes/Bulk
            features[60] = 0  # Bwd Avg Packets/Bulk
            features[61] = 0  # Bwd Avg Bulk Rate
            
            # Subflow features
            features[62] = flow.fwd_packets  # Subflow Fwd Packets
            features[63] = flow.fwd_bytes  # Subflow Fwd Bytes
            features[64] = flow.bwd_packets  # Subflow Bwd Packets
            features[65] = flow.bwd_bytes  # Subflow Bwd Bytes
            
            # Window sizes
            features[66] = flow.init_win_fwd  # Init_Win_bytes_forward
            features[67] = flow.init_win_bwd  # Init_Win_bytes_backward
            
            # Active data packets
            features[68] = flow.fwd_packets  # act_data_pkt_fwd
            features[69] = 20  # min_seg_size_forward (default TCP header)
            
            # Active/Idle times (simplified)
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
            logger.error(f"Error extracting flow features: {e}")
            return np.zeros(78)
    
    def get_feature_names(self) -> List[str]:
        """Get feature names"""
        return self.feature_names


class SequenceSampleBuilder:
    """
    Builds sequence samples from flow records for deep learning models (1D-CNN/GRU).
    Supports sliding window, padding, and masking.
    """
    
    def __init__(self, 
                 window_size: int = 100,
                 step_size: int = 50,
                 feature_dim: int = 10,
                 padding_value: float = 0.0):
        """
        Args:
            window_size: Number of packets per sequence sample
            step_size: Step size for sliding window
            feature_dim: Number of features per packet
            padding_value: Value to use for padding
        """
        self.window_size = window_size
        self.step_size = step_size
        self.feature_dim = feature_dim
        self.padding_value = padding_value
    
    def build_samples(self, flow: FlowRecord) -> Tuple[np.ndarray, np.ndarray]:
        """
        Build sequence samples from a flow record.
        
        Args:
            flow: FlowRecord with packet sequence
            
        Returns:
            Tuple of (samples, masks) where:
            - samples: shape (num_samples, window_size, feature_dim)
            - masks: shape (num_samples, window_size) - 1 for real data, 0 for padding
        """
        packets = flow.packet_sequence
        
        if not packets:
            # Return empty sample with padding
            sample = np.full((1, self.window_size, self.feature_dim), self.padding_value)
            mask = np.zeros((1, self.window_size))
            return sample, mask
        
        # Extract packet features
        packet_features = self._extract_packet_features(packets)
        num_packets = len(packet_features)
        
        # Calculate number of samples using sliding window
        if num_packets <= self.window_size:
            num_samples = 1
        else:
            num_samples = (num_packets - self.window_size) // self.step_size + 1
        
        samples = []
        masks = []
        
        for i in range(num_samples):
            start_idx = i * self.step_size
            end_idx = start_idx + self.window_size
            
            # Get window of packets
            window_packets = packet_features[start_idx:end_idx]
            actual_len = len(window_packets)
            
            # Create sample with padding
            sample = np.full((self.window_size, self.feature_dim), self.padding_value)
            mask = np.zeros(self.window_size)
            
            # Fill in actual data
            sample[:actual_len] = window_packets
            mask[:actual_len] = 1
            
            samples.append(sample)
            masks.append(mask)
        
        return np.array(samples), np.array(masks)
    
    def _extract_packet_features(self, packets: List[Dict[str, Any]]) -> np.ndarray:
        """
        Extract features from packet sequence.
        
        Features per packet:
        - length (normalized)
        - is_forward (0/1)
        - time_delta (normalized)
        - FIN flag
        - SYN flag
        - RST flag
        - PSH flag
        - ACK flag
        - URG flag
        - ECE flag
        """
        features = []
        prev_time = packets[0]["timestamp"] if packets else 0
        
        for pkt in packets:
            flags = pkt.get("flags", {})
            time_delta = pkt["timestamp"] - prev_time
            prev_time = pkt["timestamp"]
            
            pkt_features = [
                pkt.get("length", 0) / 1500.0,  # Normalize by MTU
                1.0 if pkt.get("is_forward", True) else 0.0,
                min(time_delta, 10.0) / 10.0,  # Normalize time delta
                1.0 if flags.get("FIN") else 0.0,
                1.0 if flags.get("SYN") else 0.0,
                1.0 if flags.get("RST") else 0.0,
                1.0 if flags.get("PSH") else 0.0,
                1.0 if flags.get("ACK") else 0.0,
                1.0 if flags.get("URG") else 0.0,
                1.0 if flags.get("ECE") else 0.0,
            ]
            features.append(pkt_features)
        
        return np.array(features)
    
    def build_single_sample(self, flow: FlowRecord) -> Tuple[np.ndarray, np.ndarray]:
        """
        Build a single sequence sample from a flow (no sliding window).
        Useful for inference on individual flows.
        
        Returns:
            Tuple of (sample, mask) where:
            - sample: shape (window_size, feature_dim)
            - mask: shape (window_size,)
        """
        samples, masks = self.build_samples(flow)
        # Return the last (most recent) sample
        return samples[-1], masks[-1]


# Convenience function for creating flow-level feature extractor
def create_flow_extractor(config: FlowAggregatorConfig = None) -> Tuple[FlowAggregator, FlowFeatureExtractor]:
    """
    Create flow aggregator and feature extractor pair.
    
    Returns:
        Tuple of (FlowAggregator, FlowFeatureExtractor)
    """
    aggregator = FlowAggregator(config)
    extractor = FlowFeatureExtractor()
    return aggregator, extractor


def create_sequence_builder(window_size: int = 100, 
                           step_size: int = 50) -> SequenceSampleBuilder:
    """
    Create sequence sample builder for deep learning models.
    
    Args:
        window_size: Number of packets per sequence
        step_size: Step size for sliding window
        
    Returns:
        SequenceSampleBuilder instance
    """
    return SequenceSampleBuilder(
        window_size=window_size,
        step_size=step_size,
        feature_dim=10  # 10 features per packet
    )
