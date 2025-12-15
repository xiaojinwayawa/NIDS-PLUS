"""
Traffic Capture Module
Handles network traffic capture from live interfaces or PCAP files
"""
import abc
import time
import threading
import json
import logging
import platform
import os
import asyncio
from typing import List, Dict, Optional, Any
import redis
from scapy.all import sniff, rdpcap, PcapReader, conf
from scapy.layers.inet import IP, TCP, UDP
from scapy.packet import Packet

from config import settings
from logging_config import app_logger as logger

class TrafficCapture(abc.ABC):
    """Base class for traffic capture"""
    
    def __init__(self):
        self.is_running = False
        self.redis_client = None
        self._connect_redis()
        self.stop_event = threading.Event()
        self.capture_thread = None

    def _connect_redis(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("Connected to Redis for traffic capture")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None

    def process_packet(self, packet: Packet):
        """
        Process a single packet and push to Redis
        """
        if not self.is_running:
            return

        try:
            if IP in packet:
                # Extract basic info
                src_ip = packet[IP].src
                dst_ip = packet[IP].dst
                timestamp = float(packet.time)
                length = len(packet)
                
                protocol = "OTHER"
                src_port = 0
                dst_port = 0
                
                if TCP in packet:
                    protocol = "TCP"
                    src_port = packet[TCP].sport
                    dst_port = packet[TCP].dport
                elif UDP in packet:
                    protocol = "UDP"
                    src_port = packet[UDP].sport
                    dst_port = packet[UDP].dport
                
                # Construct data dict
                packet_data = {
                    "timestamp": timestamp,
                    "src_ip": src_ip,
                    "dst_ip": dst_ip,
                    "src_port": src_port,
                    "dst_port": dst_port,
                    "protocol": protocol,
                    "length": length,
                    # We might need raw bytes or more fields for feature extraction later
                    # For now, let's keep it lightweight for the queue
                    # "raw": bytes(packet).hex() 
                }
                
                # Push to Redis list (Queue)
                if self.redis_client:
                    # Use lpush to add to the head of the list
                    self.redis_client.lpush("traffic_queue", json.dumps(packet_data))
                    
                    # Optional: Trim list to prevent memory issues if consumer is slow
                    # self.redis_client.ltrim("traffic_queue", 0, settings.MAX_QUEUE_SIZE - 1)
                    
        except Exception as e:
            logger.error(f"Error processing packet: {e}")

    @abc.abstractmethod
    def start(self):
        """Start capture"""
        pass

    @abc.abstractmethod
    def stop(self):
        """Stop capture"""
        pass

class PcapReplayCapture(TrafficCapture):
    """Capture from PCAP file (Replay)"""
    
    def __init__(self, pcap_path: str, loop: bool = False, interval: float = 0.0):
        super().__init__()
        self.pcap_path = pcap_path
        self.loop = loop
        self.interval = interval # Delay between packets to simulate real-time
        
        # Verify file exists
        if not os.path.exists(self.pcap_path):
            raise FileNotFoundError(f"PCAP file not found: {self.pcap_path}")

    def _replay_loop(self):
        """Internal replay loop"""
        logger.info(f"Starting PCAP replay from {self.pcap_path}")
        self.is_running = True
        
        while self.is_running and not self.stop_event.is_set():
            try:
                # Use PcapReader for memory efficiency with large files
                with PcapReader(self.pcap_path) as pcap_reader:
                    for packet in pcap_reader:
                        if not self.is_running or self.stop_event.is_set():
                            break
                        
                        self.process_packet(packet)
                        
                        if self.interval > 0:
                            time.sleep(self.interval)
                            
                if not self.loop:
                    logger.info("PCAP replay finished")
                    break
                else:
                    logger.info("PCAP replay restarting (loop=True)")
                    
            except Exception as e:
                logger.error(f"Error during PCAP replay: {e}")
                self.is_running = False
                break
        
        self.is_running = False

    def start(self):
        if self.is_running:
            logger.warning("Capture already running")
            return
            
        self.stop_event.clear()
        self.capture_thread = threading.Thread(target=self._replay_loop, daemon=True)
        self.capture_thread.start()
        logger.info("PcapReplayCapture started")

    def stop(self):
        logger.info("Stopping PcapReplayCapture...")
        self.is_running = False
        self.stop_event.set()
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
        logger.info("PcapReplayCapture stopped")

class LiveCapture(TrafficCapture):
    """Capture from live network interface"""
    
    def __init__(self, interface: str):
        super().__init__()
        self.interface = interface
        
    def _sniff_loop(self):
        """Internal sniffing loop"""
        logger.info(f"Starting live capture on interface {self.interface}")
        self.is_running = True
        
        try:
            # scapy sniff is blocking, but we can stop it with a stop_filter or separate thread handling
            # simpler approach: sniff in small batches or use prn
            
            # Using prn callback
            sniff(
                iface=self.interface,
                prn=self.process_packet,
                store=0, # Don't store packets in memory
                stop_filter=lambda x: self.stop_event.is_set()
            )
        except Exception as e:
            logger.error(f"Error during live capture: {e}")
        finally:
            self.is_running = False
            logger.info("Live capture stopped")

    def start(self):
        if self.is_running:
            logger.warning("Capture already running")
            return

        self.stop_event.clear()
        self.capture_thread = threading.Thread(target=self._sniff_loop, daemon=True)
        self.capture_thread.start()
        logger.info("LiveCapture started")

    def stop(self):
        logger.info("Stopping LiveCapture...")
        self.stop_event.set()
        # Sniff might take a moment to notice the stop event (on next packet)
        # We don't forcefully join immediately to avoid blocking if traffic is low
        self.is_running = False
        
def get_network_interfaces() -> List[str]:
    """
    Get available network interfaces cross-platform
    """
    interfaces = []
    system = platform.system()
    
    try:
        # Use scapy to get interfaces
        if_list = conf.ifaces
        for iface_name in if_list.data.keys():
             # Get the interface object
            iface = if_list.data[iface_name]
            # Depending on platform, description or name might be better
            # On Windows, scapy uses names like 'Ethernet', 'Wi-Fi' etc.
            # On Linux, 'eth0', 'wlan0'
            interfaces.append(iface.name)
            
    except Exception as e:
        logger.error(f"Error listing interfaces: {e}")
        
    return interfaces

def get_default_interface() -> str:
    """Get default gateway interface"""
    return conf.iface.name
