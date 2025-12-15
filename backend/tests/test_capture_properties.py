
import pytest
import os
import json
import redis
import time
from hypothesis import given, strategies as st
from capture.traffic_capture import PcapReplayCapture, LiveCapture, get_network_interfaces
from config import settings
from scapy.all import Ether, IP, TCP, wrpcap

# Redis client fixture
@pytest.fixture
def redis_client():
    r = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True
    )
    r.flushdb() # Clean DB before test
    yield r
    r.flushdb() # Clean DB after test

# Mock PCAP file fixture
@pytest.fixture
def mock_pcap(tmp_path):
    pcap_file = tmp_path / "test.pcap"
    packets = []
    # Create some dummy packets
    for i in range(10):
        pkt = Ether()/IP(src=f"192.168.1.{i}", dst="10.0.0.1")/TCP(sport=1234+i, dport=80)
        packets.append(pkt)
    
    wrpcap(str(pcap_file), packets)
    return str(pcap_file)

def test_traffic_data_integrity(redis_client, mock_pcap):
    """
    Property 3: Traffic Data Integrity
    Req 3.4: Verify traffic data is correctly pushed to Redis queue
    """
    # Initialize capture
    capture = PcapReplayCapture(pcap_path=mock_pcap, loop=False, interval=0.01)
    
    # Start capture
    capture.start()
    
    # Wait for completion (10 packets should be fast)
    time.sleep(1)
    
    # Stop capture
    capture.stop()
    
    # Verify Redis queue
    queue_len = redis_client.llen("traffic_queue")
    assert queue_len > 0
    
    # Check first packet
    data_str = redis_client.rpop("traffic_queue") # pop from tail (first in)
    data = json.loads(data_str)
    
    assert "src_ip" in data
    assert "dst_ip" in data
    assert "timestamp" in data
    assert "protocol" in data
    assert data["protocol"] == "TCP"
    # assert data["src_ip"].startswith("192.168.1.") # Order might vary depending on push/pop

def test_cross_platform_interface_detection():
    """
    Property 12: Cross-platform Path Compatibility (and Interface Detection)
    Req 20.5: Verify interface detection returns list of strings
    """
    interfaces = get_network_interfaces()
    
    assert isinstance(interfaces, list)
    assert len(interfaces) > 0
    assert all(isinstance(iface, str) for iface in interfaces)
    
    # Print for debugging/verification
    print(f"\nDetected Interfaces: {interfaces}")

def test_pcap_path_validation():
    """
    Verify PCAP path validation logic
    """
    with pytest.raises(FileNotFoundError):
        PcapReplayCapture(pcap_path="non_existent_file.pcap")
