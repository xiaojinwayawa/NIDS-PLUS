#!/usr/bin/env python
"""快速测试模型推理"""
import sys
sys.path.insert(0, '.')

import numpy as np
from ml.inference_engine import InferenceEngine

engine = InferenceEngine()

# 加载当前模型
success = engine.load_model('MyLightGBM_20260214(1)', 'lightgbm')
print(f'模型加载: {success}')

# 创建随机特征并推理
X_test = np.random.rand(10, 78)  # 78个特征
results = engine.predict_batch(X_test)

print(f'推理结果:')
print(f'  预测: {results.get("predictions", "无")}')
print(f'  置信度: {results.get("confidences", "无")}')
preds = results.get("predictions", [])
if preds:
    print(f'  攻击数: {sum(1 for p in preds if p == 1)}')
