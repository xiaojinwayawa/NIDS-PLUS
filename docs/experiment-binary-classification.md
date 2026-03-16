# 实验模块二分类说明

## 概述

实验模块 (`backend/ml/experiment_runner.py`) 已被配置为**仅支持二分类**,而训练模块 (`backend/ml/trainer.py`) 保持对多分类的支持。

## 模块对比

| 特性 | 训练模块 (trainer.py) | 实验模块 (experiment_runner.py) |
|------|---------------------|--------------------------------|
| 分类类型 | 支持二分类和多分类 | **仅支持二分类** |
| 用途 | 日常模型训练 | 可复现的对比实验 |
| 数据集处理 | 保留原始标签 | 强制转换为二分类 |
| 模型类型 | LightGBM, XGBoost, CNN, GRU, Transformer | 同左 |
| 融合策略 | 不支持 | **支持 3 种融合策略** |

## 融合策略详解

实验模块支持三种模型融合策略,用于组合多个模型的预测结果:

### 1️⃣ Voting (Majority) - 多数投票

**原理**: 每个模型投一票,得票最多的类别获胜

**示例**:
```
5 个模型的预测:
- LightGBM:    1 (攻击)
- XGBoost:     1 (攻击)
- CNN:         0 (正常)
- GRU:         1 (攻击)
- Transformer: 1 (攻击)

投票结果: 4票攻击 vs 1票正常
最终预测: 1 (攻击)
```

**优点**:
- ✅ 简单直观
- ✅ 公平对待所有模型
- ✅ 适合模型性能相近的情况

**缺点**:
- ❌ 不考虑模型准确率差异
- ❌ 表现差的模型权重与好模型相同

**配置**:
```python
config = ExperimentConfig(
    fusion_strategy="voting"  # 默认策略
)
```

### 2️⃣ Weighted Average - 加权平均

**原理**: 根据模型类型赋予不同权重,加权投票

**权重分配**:
```python
LightGBM:   1.2  # ML模型,速度快且准确
XGBoost:    1.2  # ML模型,速度快且准确
CNN:        1.0  # DL模型,标准权重
GRU:        1.0  # DL模型,标准权重
Transformer: 1.1  # 注意力机制,略高权重
```

**示例**:
```
5 个模型的预测和权重:
- LightGBM (1.2):    1 (攻击) → 1.2 票给攻击
- XGBoost (1.2):     1 (攻击) → 1.2 票给攻击
- CNN (1.0):         0 (正常) → 1.0 票给正常
- GRU (1.0):         1 (攻击) → 1.0 票给攻击
- Transformer (1.1): 1 (攻击) → 1.1 票给攻击

加权结果:
- 正常: 1.0 票
- 攻击: 1.2 + 1.2 + 1.0 + 1.1 = 4.5 票

最终预测: 1 (攻击)
```

**优点**:
- ✅ 考虑模型特性
- ✅ ML模型速度优势得到体现
- ✅ 可以根据验证集性能调整权重

**缺点**:
- ❌ 权重需要手动调整
- ❌ 可能过度依赖某类模型

**配置**:
```python
config = ExperimentConfig(
    fusion_strategy="weighted"
)
```

### 3️⃣ Cascade (ML→DL) - 级联策略

**原理**: 先用快速的ML模型,只在ML模型不一致时才使用慢速的DL模型

**工作流程**:
```
1. 首先使用 ML 模型 (LightGBM, XGBoost) 预测
2. 如果 ML 模型预测一致 → 直接使用该预测
3. 如果 ML 模型预测不一致 → 使用 DL 模型投票决定
```

**示例 1 - ML 模型一致**:
```
样本 #1:
- LightGBM: 1 (攻击)
- XGBoost:  1 (攻击)  ← ML 模型一致!

最终预测: 1 (攻击)
不需要运行 DL 模型,节省时间!
```

**示例 2 - ML 模型不一致**:
```
样本 #2:
- LightGBM: 0 (正常)
- XGBoost:  1 (攻击)  ← ML 模型不一致!

启用 DL 模型:
- CNN:         1 (攻击)
- GRU:         1 (攻击)
- Transformer: 1 (攻击)

DL 投票结果: 3票攻击 vs 0票正常
最终预测: 1 (攻击)
```

**优点**:
- ✅ 充分利用ML模型的速度优势
- ✅ 在需要时使用DL模型的准确性
- ✅ 平衡速度和准确率
- ✅ 适合实时系统

**缺点**:
- ❌ 实现复杂
- ❌ 需要同时训练ML和DL模型

**配置**:
```python
config = ExperimentConfig(
    fusion_strategy="cascade",
    model_types=["lightgbm", "xgboost", "cnn", "gru", "transformer"]
)
```

## 融合策略对比

| 策略 | 速度 | 准确率 | 复杂度 | 适用场景 |
|------|------|--------|--------|----------|
| Voting | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | 模型性能相近 |
| Weighted | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | 已知模型性能差异 |
| Cascade | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | 实时系统,需要平衡速度和准确率 |

## 二分类转换规则

### NSL-KDD 数据集
```python
# 标签转换
normal -> 0 (正常)
所有攻击类型 -> 1 (攻击)
```

### CIC-IDS2017 数据集
```python
# 标签转换
BENIGN/Normal -> 0 (正常)
所有攻击类型 -> 1 (攻击)

# 支持的攻击类型包括:
# - DoS, DDoS
# - PortScan
# - Bot
# - Infiltration
# - Web Attack
# - Brute Force
# - Heartbleed
# 等等...
```

## 代码修改点

### 1. 数据预处理 - NSL-KDD
```python
def _preprocess_nsl_kdd(self, df: pd.DataFrame, use_one_hot: bool = True):
    """Preprocess NSL-KDD dataframe - BINARY CLASSIFICATION ONLY"""
    # 强制二分类
    df['label'] = df['label'].apply(
        lambda x: 0 if str(x).lower() == 'normal' else 1
    )
```

### 2. 数据预处理 - CIC-IDS2017
```python
def _preprocess_cicids2017(self, df: pd.DataFrame):
    """Preprocess CIC-IDS2017 dataframe - BINARY CLASSIFICATION ONLY"""
    # 强制二分类
    df['label_binary'] = df[label_col].apply(
        lambda x: 0 if str(x).lower() in ['benign', 'normal'] else 1
    )
    label_mapping = {0: 'Normal', 1: 'Attack'}
```

### 3. ML 模型训练
```python
def _train_ml_model(self, ...):
    """Train a traditional ML model - BINARY CLASSIFICATION ONLY"""
    # 强制检查
    if num_classes != 2:
        logger.warning(f"Forcing binary classification. Got {num_classes} classes.")
        num_classes = 2
    
    # 只使用二分类参数
    params = {
        'objective': 'binary',  # LightGBM
        # 或
        'objective': 'binary:logistic',  # XGBoost
    }
```

### 4. DL 模型训练
```python
def _train_dl_model(self, ...):
    """Train a deep learning model - BINARY CLASSIFICATION ONLY"""
    # 强制二分类
    if num_classes != 2:
        logger.warning(f"Forcing binary classification.")
        num_classes = 2
    
    # 二分类设置
    loss_fn = 'binary_crossentropy'
    output_activation = 'sigmoid'
    output_units = 1
```

## 使用示例

### 示例 1: 使用不同融合策略运行实验

```python
from ml.experiment_runner import ExperimentRunner, ExperimentConfig

runner = ExperimentRunner()

# 1. Voting 策略
voting_config = ExperimentConfig(
    experiment_name="nsl_kdd_voting",
    dataset_type="nsl-kdd",
    model_types=["lightgbm", "xgboost", "cnn", "gru", "transformer"],
    fusion_strategy="voting"
)
voting_result = runner.run_experiment(voting_config)
print(f"Voting - Accuracy: {voting_result.accuracy:.4f}")

# 2. Weighted 策略
weighted_config = ExperimentConfig(
    experiment_name="nsl_kdd_weighted",
    dataset_type="nsl-kdd",
    model_types=["lightgbm", "xgboost", "cnn", "gru", "transformer"],
    fusion_strategy="weighted"
)
weighted_result = runner.run_experiment(weighted_config)
print(f"Weighted - Accuracy: {weighted_result.accuracy:.4f}")

# 3. Cascade 策略
cascade_config = ExperimentConfig(
    experiment_name="nsl_kdd_cascade",
    dataset_type="nsl-kdd",
    model_types=["lightgbm", "xgboost", "cnn", "gru", "transformer"],
    fusion_strategy="cascade"
)
cascade_result = runner.run_experiment(cascade_config)
print(f"Cascade - Accuracy: {cascade_result.accuracy:.4f}")
```

### 示例 2: 对比三种融合策略

```python
# 运行完整对比实验 (自动测试所有策略)
results = runner.run_comparative_experiments(dataset_type="cic-ids2017")

for exp_name, result in results.items():
    print(f"{exp_name}:")
    print(f"  Accuracy:  {result.accuracy:.4f}")
    print(f"  Precision: {result.precision:.4f}")
    print(f"  Recall:    {result.recall:.4f}")
    print(f"  F1-Score:  {result.f1_score:.4f}")
```

### 示例 3: 单独测试 ML 或 DL 模型

```python
# 只使用 ML 模型
ml_only_config = ExperimentConfig(
    experiment_name="ml_only",
    dataset_type="nsl-kdd",
    model_types=["lightgbm", "xgboost"],
    fusion_strategy="voting"  # ML 模型用投票即可
)
ml_result = runner.run_experiment(ml_only_config)

# 只使用 DL 模型
dl_only_config = ExperimentConfig(
    experiment_name="dl_only",
    dataset_type="cic-ids2017",
    model_types=["cnn", "gru", "transformer"],
    fusion_strategy="weighted"  # DL 模型可以用加权
)
dl_result = runner.run_experiment(dl_only_config)
```

## 评估指标

由于是二分类,所有指标都针对二分类优化:

- **Accuracy**: 总体准确率
- **Precision**: 精确率 (攻击预测的准确性)
- **Recall**: 召回率 (检测到的攻击比例)
- **F1-Score**: F1 分数 (精确率和召回率的调和平均)
- **FPR**: 假阳性率 (误报率)
- **FNR**: 假阴性率 (漏报率)

## 为什么分离?

### 实验模块使用二分类的原因:
1. **可比性**: 不同数据集的攻击类型不同,二分类便于跨数据集比较
2. **实用性**: 入侵检测的核心任务是区分正常和攻击
3. **简化**: 避免类别不平衡和多分类复杂性
4. **标准化**: 学术论文中常用二分类进行对比

### 训练模块保持多分类的原因:
1. **灵活性**: 用户可能需要识别具体攻击类型
2. **实际应用**: 生产环境可能需要细粒度分类
3. **兼容性**: 保持与现有系统的兼容

## 注意事项

⚠️ **重要提示**:
- 实验模块生成的模型**只能用于二分类**
- 如果需要多分类模型,请使用训练模块 (`trainer.py`)
- 两个模块的模型**不可互换使用**

## 日志输出

运行实验时,你会看到类似的日志:
```
INFO: Dataset loaded: Train=100000, Test=25000, Classes=2
INFO: Class mapping: {0: 'Normal', 1: 'Attack'}
WARNING: Experiment module only supports binary classification. Got 15 classes, forcing binary.
```

## 相关文件

- `backend/ml/experiment_runner.py` - 实验运行器(二分类)
- `backend/ml/trainer.py` - 训练管理器(多分类)
- `backend/ml/deep_learning_trainer.py` - 深度学习训练器(多分类)
- `backend/api/routers/experiments.py` - 实验 API 路由

## 更新日期

2024-02-16
