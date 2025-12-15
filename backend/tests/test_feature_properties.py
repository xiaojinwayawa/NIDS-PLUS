
import pytest
import numpy as np
from hypothesis import given, strategies as st
from ml.feature_extractor import NSLKDDFeatureExtractor, CICIDS2017FeatureExtractor, get_extractor

# Strategies for packet data
packet_data_strategy = st.fixed_dictionaries({
    "timestamp": st.floats(min_value=0, max_value=1e10),
    "src_ip": st.ip_addresses().map(str),
    "dst_ip": st.ip_addresses().map(str),
    "src_port": st.integers(min_value=0, max_value=65535),
    "dst_port": st.integers(min_value=0, max_value=65535),
    "protocol": st.sampled_from(["TCP", "UDP", "ICMP", "OTHER"]),
    "length": st.integers(min_value=0, max_value=65535)
})

def test_nsl_kdd_dimension_consistency():
    """
    Property 4: Feature Dimension Consistency
    Req 4.1: Verify NSL-KDD extractor returns 41 dimensions
    """
    extractor = NSLKDDFeatureExtractor()
    dummy_packet = {
        "timestamp": 1234567890.0,
        "src_ip": "192.168.1.1",
        "dst_ip": "10.0.0.1",
        "src_port": 1234,
        "dst_port": 80,
        "protocol": "TCP",
        "length": 60
    }
    
    features = extractor.extract_features(dummy_packet)
    
    assert isinstance(features, np.ndarray)
    assert features.shape == (41,)
    assert len(extractor.get_feature_names()) == 41

@given(packet_data=packet_data_strategy)
def test_nsl_kdd_extraction_robustness(packet_data):
    """
    Property 4: Feature Dimension Consistency
    Verify extraction never crashes and always returns correct shape
    """
    extractor = NSLKDDFeatureExtractor()
    features = extractor.extract_features(packet_data)
    assert features.shape == (41,)
    assert not np.any(np.isnan(features)) # Should handle errors gracefully (e.g. zero out)

def test_cic_ids2017_dimension_consistency():
    """
    Property 4: Feature Dimension Consistency
    Req 4.2: Verify CIC-IDS2017 extractor returns 78 dimensions
    """
    extractor = CICIDS2017FeatureExtractor()
    dummy_packet = {} # Dummy
    features = extractor.extract_features(dummy_packet)
    
    assert isinstance(features, np.ndarray)
    assert features.shape == (78,)
    assert len(extractor.get_feature_names()) == 78

def test_extractor_factory():
    """Verify factory method"""
    assert isinstance(get_extractor("nsl-kdd"), NSLKDDFeatureExtractor)
    assert isinstance(get_extractor("cic-ids2017"), CICIDS2017FeatureExtractor)
    
    with pytest.raises(ValueError):
        get_extractor("unknown")
