#!/usr/bin/env python
"""测试系统推理管道，追踪数据流"""
import sys
import time
sys.path.insert(0, '.')

from backend.ml.detection_engine import DetectionEngine
from backend.config import settings

# 启动detection engine并监视推理过程
engine = DetectionEngine()
engine.current_model_name = 'lightgbm_cicids'
engine.current_model_type = 'lightgbm'

# 配置为PCAP模式 - 回放历史数据更快
settings.TRAFFIC_SOURCE_MODE = 'pcap'

print("🚀 启动Detection Engine...")
engine.configure()
engine.start()

print("⏳ 运行30秒监测")
time.sleep(30)

print("🛑 停止Detection Engine...")
engine.stop()

print("\n📊 统计信息:")
print(f"  处理的包数: {engine._packets_processed}")
print(f"  处理的流数: {len(engine.flow_aggregator.flows) if engine.flow_aggregator else 'N/A'}")
print(f"  推理时间 (平均ms): {sum(engine._processing_times)/len(engine._processing_times) if engine._processing_times else 'N/A'}")

print("\n✅ 诊断完成")
