#!/usr/bin/env python3
"""
测试推理引擎 - 查看模型对流量的判断
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from ml.inference_engine import InferenceEngine
from ml.feature_extractor import get_extractor
from ml.flow_aggregator import FlowKey, FlowRecord, FlowState
from ml.flow_aggregator import FlowFeatureExtractor

def test_model_inference():
    """测试模型推理"""
    print("=" * 60)
    print("测试模型推理")
    print("=" * 60)
    
    # 1. 加载模型
    print("\n1. 加载模型...")
    engine = InferenceEngine()
    success = engine.load_model("lightgbm_cicids", "lightgbm")
    
    if not success:
        print("✗ 模型加载失败")
        return
    
    print("✓ 模型加载成功")
    
    # 2. 创建测试流 (模拟端口扫描)
    print("\n2. 创建测试流 (模拟端口扫描)...")
    
    # 端口扫描特征: 高SYN, 低ACK, 短duration, 小packets
    test_flow = FlowRecord(
        flow_key=FlowKey(
            src_ip="192.168.1.100",
            dst_ip="192.168.1.1",
            src_port=54321,
            dst_port=80,
            protocol="TCP"
        ),
        start_time=1000.0,
        last_update_time=1001.0,
        duration=1.0,
        fwd_packets=10,
        bwd_packets=0,
        total_packets=10,
        syn_count=10,
        ack_count=0,
        rst_count=5,
        total_bytes=600
    )
    test_flow.state = FlowState.FINISHED
    
    # 3. 提取特征
    print("\n3. 提取特征...")
    flow_extractor = FlowFeatureExtractor()
    features = flow_extractor.extract_features(test_flow)
    
    print(f"   特征维度: {features.shape}")
    print(f"   特征样本 (前10个): {features[:10]}")
    
    # 4. 运行推理
    print("\n4. 运行推理...")
    results = engine.predict_batch(features.reshape(1, -1))
    
    print(f"\n推理结果:")
    print(f"  预测: {results['predictions'][0]} (0=正常, 1=攻击)")
    print(f"  置信度: {results['confidences'][0]:.4f}")
    print(f"  攻击类型: {results['attack_types'][0]}")
    print(f"  推理时间: {results['inference_time_ms']:.2f} ms")
    
    # 5. 测试正常流量
    print("\n\n5. 测试正常流量...")
    normal_flow = FlowRecord(
        flow_key=FlowKey(
            src_ip="192.168.1.100",
            dst_ip="192.168.1.1",
            src_port=54321,
            dst_port=80,
            protocol="TCP"
        ),
        start_time=1000.0,
        last_update_time=1010.0,
        duration=10.0,
        fwd_packets=50,
        bwd_packets=45,
        total_packets=95,
        syn_count=1,
        ack_count=90,
        rst_count=0,
        total_bytes=50000
    )
    normal_flow.state = FlowState.FINISHED
    
    features_normal = flow_extractor.extract_features(normal_flow)
    results_normal = engine.predict_batch(features_normal.reshape(1, -1))
    
    print(f"\n推理结果 (正常流量):")
    print(f"  预测: {results_normal['predictions'][0]} (0=正常, 1=攻击)")
    print(f"  置信度: {results_normal['confidences'][0]:.4f}")
    print(f"  攻击类型: {results_normal['attack_types'][0]}")
    
    # 6. 分析
    print("\n" + "=" * 60)
    print("分析")
    print("=" * 60)
    
    if results['predictions'][0] == 0:
        print("\n⚠ 模型将端口扫描流量判断为正常!")
        print("   这可能是为什么没有报警的原因。")
        print("\n可能的解决方案:")
        print("  1. 降低报警阈值 (当前: confidence > 0.5)")
        print("  2. 重新训练模型,包含更多端口扫描样本")
        print("  3. 使用专门的端口扫描检测规则")
    else:
        print("\n✓ 模型正确识别了端口扫描!")
        print(f"   置信度: {results['confidences'][0]:.4f}")
        
        if results['confidences'][0] < 0.5:
            print("\n⚠ 但置信度低于阈值 (0.5)")
            print("   建议降低阈值或调整模型")

if __name__ == "__main__":
    test_model_inference()
