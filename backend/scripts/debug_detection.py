#!/usr/bin/env python3
"""
调试检测引擎 - 增加详细日志输出
运行此脚本来查看实时的检测过程
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis
import json
import time
from config import settings
from logging_config import app_logger as logger

def monitor_detection_pipeline():
    """监控检测管道"""
    print("=" * 60)
    print("实时监控检测管道")
    print("=" * 60)
    print("按 Ctrl+C 停止\n")
    
    try:
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        
        last_queue_len = 0
        packet_count = 0
        syn_packets = 0
        port_scan_targets = {}
        
        while True:
            queue_len = r.llen("traffic_queue")
            
            # 检查队列变化
            if queue_len != last_queue_len:
                print(f"\n[{time.strftime('%H:%M:%S')}] 队列长度: {queue_len} (变化: {queue_len - last_queue_len:+d})")
                last_queue_len = queue_len
            
            # 采样最新的包
            if queue_len > 0:
                sample = r.lindex("traffic_queue", 0)
                if sample:
                    pkt = json.loads(sample)
                    packet_count += 1
                    
                    # 分析包特征
                    src_ip = pkt.get('src_ip', '')
                    dst_ip = pkt.get('dst_ip', '')
                    dst_port = pkt.get('dst_port', 0)
                    protocol = pkt.get('protocol', '')
                    tcp_flags = pkt.get('tcp_flags', {})
                    
                    # 检测SYN包
                    if tcp_flags.get('SYN') and not tcp_flags.get('ACK'):
                        syn_packets += 1
                        target_key = f"{dst_ip}:{dst_port}"
                        port_scan_targets[target_key] = port_scan_targets.get(target_key, 0) + 1
                        
                        print(f"  SYN包: {src_ip} -> {dst_ip}:{dst_port}")
                    
                    # 每10个包输出统计
                    if packet_count % 10 == 0:
                        print(f"\n统计 (最近10包):")
                        print(f"  - 总包数: {packet_count}")
                        print(f"  - SYN包数: {syn_packets}")
                        print(f"  - 扫描目标数: {len(port_scan_targets)}")
                        
                        if port_scan_targets:
                            print(f"  - 热门目标:")
                            sorted_targets = sorted(port_scan_targets.items(), key=lambda x: x[1], reverse=True)
                            for target, count in sorted_targets[:5]:
                                print(f"    {target}: {count} 次")
            
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n\n监控停止")
        print(f"\n最终统计:")
        print(f"  - 总包数: {packet_count}")
        print(f"  - SYN包数: {syn_packets}")
        print(f"  - 扫描目标数: {len(port_scan_targets)}")
    except Exception as e:
        print(f"\n错误: {e}")

if __name__ == "__main__":
    monitor_detection_pipeline()
