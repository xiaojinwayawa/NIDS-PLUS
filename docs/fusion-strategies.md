# 模型融合策略详解

## 概述

实验模块支持三种模型融合策略,用于组合多个模型的预测结果以提高整体性能。

## 三种融合策略

### 1. Voting (Majority) - 多数投票 ✅

**策略代码**: `fusion_strategy="voting"`

#### 工作原理
每个模型对每个样本投一票,得票最多的类别成为最终预测。

#### 算法流程
```
对于每个样本:
  1. 收集所有模型的预测
  2. 统计每个类别的票数
  3. 返回票数最多的类别
```

#### 代码实现
```python
from scipy import stats
mode_result = stats.mode(stacked, axis=0)
final_prediction = mode_result.mode.flatten()
```

#### 示例
```
样本 #1 的预测:
┌─────────────┬──────────┐
│ 模型        │ 预测     │
├─────────────┼──────────┤
│ LightGBM    │ 1 (攻击) │
│ XGBoost     │ 1 (攻击) │
│ CNN         │ 0 (正常) │
│ GRU         │ 1 (攻击) │
│ Transformer │ 1 (攻击) │
└─────────────┴──────────┘

投票统计:
- 正常 (0): 1 票
- 攻击 (1): 4 票

最终预测: 1 (攻击) ✓
```

#### 优缺点

**优点**:
- ✅ 实现简单,易于理解
- ✅ 公平对待所有模型
- ✅ 对异常值有鲁棒性
- ✅ 适合模型性能相近的情况

**缺点**:
- ❌ 不考虑模型准确率差异
- ❌ 表现差的模型权重与好模型相同
- ❌ 可能被多数"平庸"模型主导

#### 适用场景
- 模型性能相近
- 追求简单可靠
- 不确定各模型相对性能

---

### 2. Weighted Average - 加权平均 ✅

**策略代码**: `fusion_strategy="weighted"`

#### 工作原理
根据模型类型赋予不同权重,加权投票决定最终预测。

#### 权重分配策略
```python
weights = {
    "lightgbm":   1.2,  # ML模型: 速度快,准确率高
    "xgboost":    1.2,  # ML模型: 速度快,准确率高
    "cnn":        1.0,  # DL模型: 标准权重
    "gru":        1.0,  # DL模型: 标准权重
    "transformer": 1.1   # 注意力机制: 略高权重
}
```

#### 算法流程
```
对于每个样本:
  1. 初始化: weighted_votes = [0, 0]  # [正常票数, 攻击票数]
  2. 对于每个模型:
     a. 获取该模型的预测和权重
     b. weighted_votes[预测类别] += 权重
  3. 返回加权票数最高的类别
```

#### 代码实现
```python
weighted_votes = np.zeros((num_samples, 2))

for model_name, predictions in zip(model_names, pred_arrays):
    weight = weights.get(model_name, 1.0)
    for j, pred in enumerate(predictions):
        weighted_votes[j, int(pred)] += weight

final_prediction = np.argmax(weighted_votes, axis=1)
```

#### 示例
```
样本 #1 的预测和权重:
┌─────────────┬──────────┬────────┬──────────────┐
│ 模型        │ 预测     │ 权重   │ 贡献票数     │
├─────────────┼──────────┼────────┼──────────────┤
│ LightGBM    │ 1 (攻击) │ 1.2    │ 攻击 +1.2    │
│ XGBoost     │ 1 (攻击) │ 1.2    │ 攻击 +1.2    │
│ CNN         │ 0 (正常) │ 1.0    │ 正常 +1.0    │
│ GRU         │ 1 (攻击) │ 1.0    │ 攻击 +1.0    │
│ Transformer │ 0 (正常) │ 1.1    │ 正常 +1.1    │
└─────────────┴──────────┴────────┴──────────────┘

加权统计:
- 正常 (0): 1.0 + 1.1 = 2.1 票
- 攻击 (1): 1.2 + 1.2 + 1.0 = 3.4 票

最终预测: 1 (攻击) ✓
```

#### 优缺点

**优点**:
- ✅ 考虑模型特性和性能
- ✅ ML模型的速度优势得到体现
- ✅ 可以根据验证集调整权重
- ✅ 更灵活,可定制

**缺点**:
- ❌ 权重需要手动设置或学习
- ❌ 可能过度依赖某类模型
- ❌ 需要领域知识或实验调优

#### 适用场景
- 已知各模型性能差异
- 需要平衡不同模型特点
- 有验证集可以调优权重

#### 权重调优建议
```python
# 方法1: 基于验证集准确率
weights = {
    "lightgbm": val_acc_lgb / avg_val_acc,
    "xgboost": val_acc_xgb / avg_val_acc,
    # ...
}

# 方法2: 基于F1分数
weights = {
    "lightgbm": f1_lgb,
    "xgboost": f1_xgb,
    # ...
}

# 方法3: 基于模型类型 (当前实现)
weights = {
    "ML模型": 1.2,    # 快速且准确
    "DL模型": 1.0,    # 标准
    "Transformer": 1.1 # 注意力机制优势
}
```

---

### 3. Cascade (ML→DL) - 级联策略 ✅

**策略代码**: `fusion_strategy="cascade"`

#### 工作原理
先使用快速的ML模型,只在ML模型预测不一致时才使用慢速的DL模型。

#### 算法流程
```
对于每个样本:
  1. 使用所有 ML 模型 (LightGBM, XGBoost) 预测
  2. 检查 ML 模型预测是否一致:
     a. 如果一致 → 直接使用该预测 (快速路径)
     b. 如果不一致 → 使用 DL 模型投票决定 (准确路径)
  3. 返回最终预测
```

#### 代码实现
```python
# 分离 ML 和 DL 预测
ml_models = ["lightgbm", "xgboost"]
dl_models = ["cnn", "gru", "transformer"]

for sample in samples:
    ml_predictions = [model.predict(sample) for model in ml_models]
    
    if all_same(ml_predictions):
        # ML 模型一致 - 快速路径
        final_pred = ml_predictions[0]
    else:
        # ML 模型不一致 - 使用 DL 模型
        dl_predictions = [model.predict(sample) for model in dl_models]
        final_pred = majority_vote(dl_predictions)
```

#### 示例 1: ML 模型一致 (快速路径)
```
样本 #1:
┌─────────────┬──────────┬────────┐
│ 模型        │ 预测     │ 状态   │
├─────────────┼──────────┼────────┤
│ LightGBM    │ 1 (攻击) │ ✓      │
│ XGBoost     │ 1 (攻击) │ ✓      │
└─────────────┴──────────┴────────┘

ML 模型一致! ✓
最终预测: 1 (攻击)
不需要运行 DL 模型 → 节省时间!
```

#### 示例 2: ML 模型不一致 (准确路径)
```
样本 #2:
┌─────────────┬──────────┬────────┐
│ 模型        │ 预测     │ 状态   │
├─────────────┼──────────┼────────┤
│ LightGBM    │ 0 (正常) │ ✗      │
│ XGBoost     │ 1 (攻击) │ ✗      │
└─────────────┴──────────┴────────┘

ML 模型不一致! ✗
启用 DL 模型:

┌─────────────┬──────────┐
│ DL 模型     │ 预测     │
├─────────────┼──────────┤
│ CNN         │ 1 (攻击) │
│ GRU         │ 1 (攻击) │
│ Transformer │ 1 (攻击) │
└─────────────┴──────────┘

DL 投票: 3票攻击 vs 0票正常
最终预测: 1 (攻击) ✓
```

#### 性能分析
```
假设:
- ML 模型推理时间: 1ms
- DL 模型推理时间: 10ms
- ML 模型一致率: 80%

平均推理时间:
= 80% × (2×1ms) + 20% × (2×1ms + 3×10ms)
= 80% × 2ms + 20% × 32ms
= 1.6ms + 6.4ms
= 8ms

对比:
- 全部运行: 2×1ms + 3×10ms = 32ms
- Cascade: 8ms
- 加速比: 4倍! 🚀
```

#### 优缺点

**优点**:
- ✅ 充分利用ML模型速度优势
- ✅ 在需要时使用DL模型准确性
- ✅ 平衡速度和准确率
- ✅ 适合实时系统
- ✅ 可解释性强

**缺点**:
- ❌ 实现复杂
- ❌ 需要同时训练ML和DL模型
- ❌ ML模型一致率低时效果不明显

#### 适用场景
- 实时入侵检测系统
- 需要快速响应
- 有充足的ML和DL模型
- ML模型一致率较高(>70%)

---

## 策略对比总结

| 维度 | Voting | Weighted | Cascade |
|------|--------|----------|---------|
| **实现复杂度** | ⭐ 简单 | ⭐⭐ 中等 | ⭐⭐⭐ 复杂 |
| **推理速度** | ⭐⭐⭐ 慢 | ⭐⭐⭐ 慢 | ⭐⭐⭐⭐⭐ 快 |
| **准确率** | ⭐⭐⭐ 好 | ⭐⭐⭐⭐ 很好 | ⭐⭐⭐⭐ 很好 |
| **可解释性** | ⭐⭐⭐⭐⭐ 强 | ⭐⭐⭐⭐ 较强 | ⭐⭐⭐ 中等 |
| **鲁棒性** | ⭐⭐⭐⭐ 强 | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐ 强 |
| **调优难度** | ⭐ 无需调优 | ⭐⭐⭐ 需要调优 | ⭐⭐ 较少调优 |

## 选择建议

### 场景 1: 学术研究/论文
**推荐**: Voting 或 Weighted
- 简单可靠
- 易于复现
- 便于对比

### 场景 2: 生产环境/实时系统
**推荐**: Cascade
- 速度快
- 准确率高
- 资源利用率高

### 场景 3: 模型性能差异大
**推荐**: Weighted
- 充分利用好模型
- 降低差模型影响

### 场景 4: 追求最高准确率
**推荐**: Weighted (精心调优权重)
- 基于验证集优化权重
- 可以达到最优性能

## 实验建议

建议按以下顺序测试:

1. **Voting** - 建立基线
2. **Weighted** - 尝试提升
3. **Cascade** - 优化速度

对比指标:
- Accuracy, Precision, Recall, F1
- 推理时间
- 资源占用

## 代码示例

```python
from ml.experiment_runner import ExperimentRunner, ExperimentConfig

runner = ExperimentRunner()

# 测试所有策略
strategies = ["voting", "weighted", "cascade"]
results = {}

for strategy in strategies:
    config = ExperimentConfig(
        experiment_name=f"nsl_kdd_{strategy}",
        dataset_type="nsl-kdd",
        model_types=["lightgbm", "xgboost", "cnn", "gru", "transformer"],
        fusion_strategy=strategy
    )
    
    result = runner.run_experiment(config)
    results[strategy] = result
    
    print(f"\n{strategy.upper()} Strategy:")
    print(f"  Accuracy:  {result.accuracy:.4f}")
    print(f"  Precision: {result.precision:.4f}")
    print(f"  Recall:    {result.recall:.4f}")
    print(f"  F1-Score:  {result.f1_score:.4f}")

# 找出最佳策略
best_strategy = max(results.items(), key=lambda x: x[1].f1_score)
print(f"\nBest Strategy: {best_strategy[0]} (F1={best_strategy[1].f1_score:.4f})")
```

## 参考文献

1. Zhou, Z. H. (2012). Ensemble methods: foundations and algorithms.
2. Dietterich, T. G. (2000). Ensemble methods in machine learning.
3. Kuncheva, L. I. (2004). Combining pattern classifiers: methods and algorithms.

## 更新日期

2024-02-16
