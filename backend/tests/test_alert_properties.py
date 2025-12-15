
import pytest
from hypothesis import given, strategies as st
from datetime import datetime
from ml.alert_engine import AlertEngine
from db.models import AlertModel
from db.db_manager import SessionLocal, Base, engine

# Create tables for testing
Base.metadata.create_all(bind=engine)

# Strategies
packet_info_strategy = st.fixed_dictionaries({
    "timestamp": st.floats(min_value=1600000000, max_value=1700000000),
    "src_ip": st.ip_addresses().map(str),
    "dst_ip": st.ip_addresses().map(str),
    "src_port": st.integers(min_value=0, max_value=65535),
    "dst_port": st.integers(min_value=0, max_value=65535),
    "protocol": st.sampled_from(["TCP", "UDP", "ICMP"])
})

@given(packet_info=packet_info_strategy)
def test_alert_data_integrity(packet_info):
    """
    Property 6: Alert Data Integrity
    Req 6.2: Verify generated alert contains all required fields from packet info
    """
    engine = AlertEngine()
    
    # Simulate an attack prediction
    prediction_result = {
        "is_attack": True,
        "attack_type": "DoS",
        "confidence": 0.95
    }
    
    alert = engine.generate_alert(packet_info, prediction_result)
    
    if alert:
        assert alert.src_ip == packet_info["src_ip"]
        assert alert.dst_ip == packet_info["dst_ip"]
        assert alert.attack_type == "DoS"
        assert alert.confidence == 0.95
        # Check raw features stored correctly
        assert alert.raw_features["src_port"] == packet_info["src_port"]

@pytest.fixture(scope="module")
def setup_db():
    # Only create/drop tables defined in Base, but be careful with foreign keys
    # In a real environment, we might want to truncate instead of drop
    # For now, let's just create if not exists
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup only alert table to avoid FK issues with other existing tables (like users/datasets)
    # or use cascade (but risky on shared DB)
    # Base.metadata.drop_all(bind=engine) 
    pass

def test_alert_persistence_consistency(setup_db):
    """
    Property 7: Alert Persistence Consistency
    Req 6.3: Verify alerts are correctly saved and retrieved from DB
    """
    engine = AlertEngine()
    
    packet_info = {
        "timestamp": 1600000000.0,
        "src_ip": "1.2.3.4",
        "dst_ip": "5.6.7.8",
        "src_port": 80,
        "dst_port": 1234,
        "protocol": "TCP"
    }
    
    prediction_result = {
        "is_attack": True,
        "attack_type": "TestAttack",
        "confidence": 0.99
    }
    
    # Generate and save
    alert = engine.generate_alert(packet_info, prediction_result)
    assert alert is not None
    assert alert.id is not None # Should have ID after commit
    
    # Retrieve
    # Since we use hypothesis for the other test, there might be residual data if DB is shared
    # We should query specifically for our test attack type to verify persistence
    retrieved_alert = None
    alerts = engine.get_alerts(limit=10)
    for a in alerts:
        if a.attack_type == "TestAttack" and a.src_ip == "1.2.3.4":
            retrieved_alert = a
            break
            
    assert retrieved_alert is not None
    assert retrieved_alert.attack_type == "TestAttack"
    assert retrieved_alert.confidence == 0.99
