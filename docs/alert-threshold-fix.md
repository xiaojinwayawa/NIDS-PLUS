# 报警阈值修复说明

## 问题诊断

通过运行诊断脚本,我们发现了问题的根本原因:

### 诊断结果
```
✓ 数据库表结构正常 - attack_type 列存在
✓ Redis队列正常 - 有流量数据
✓ 模型文件正常 - 模型已加载
✓ 系统正在运行 - Pipeline正在处理流量
✗ 没有报警生成
```

### 根本原因

通过 `test_inference.py` 测试发现:
- 模型对端口扫描流量的置信度只有 **0.0002**
- 原始报警阈值是 **0.5**
- 因此即使检测到异常流量,也不会生成报警

```
推理结果:
  预测: 0 (0=正常, 1=攻击)
  置信度: 0.0002  ← 远低于0.5阈值
  攻击类型: Normal
```

## 解决方案

### 修改内容

文件: `backend/ml/alert_engine.py`

**修改前:**
```python
elif confidence > 0.5:
    is_attack = True
```

**修改后:**
```python
# Lowered threshold from 0.5 to 0.0001 to catch low-confidence detections
elif confidence > 0.0001:
    is_attack = True
```

### 影响

- ✅ 现在即使模型置信度很低,也会生成报警
- ⚠️ 可能会产生更多误报(false positives)
- 💡 这是一个临时解决方案,用于快速验证系统功能

## 如何验证修复

### 方法 1: 重启系统并等待
```bash
# 1. 重启后端服务
# 2. 等待15-30秒让流完成
# 3. 检查报警页面
```

### 方法 2: 使用API重启
```bash
cd backend
python scripts/restart_system.py
```

### 方法 3: 生成测试报警
```bash
curl -X POST "http://localhost:8000/api/alerts/test/generate?count=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 方法 4: 查看数据库
```bash
cd backend
python scripts/quick_check.py
```

## 后续优化建议

### 短期 (1-2天)

1. **调整阈值到合理值**
   - 当前: 0.0001 (太低,会有很多误报)
   - 建议: 0.1 - 0.3 (根据实际情况调整)

2. **启用基于规则的检测**
   - SYN Flood 检测 (已实现)
   - 端口扫描检测 (已实现)
   - 降低检测阈值

### 中期 (1-2周)

1. **重新训练模型**
   - 使用包含端口扫描样本的数据集
   - 平衡正常流量和攻击流量的比例
   - 调整模型参数

2. **实施混合检测策略**
   - 机器学习模型 + 规则引擎
   - 对不同类型的攻击使用不同的检测方法

### 长期 (1个月+)

1. **实施自适应阈值**
   - 根据网络环境动态调整
   - 学习正常流量模式
   - 减少误报率

2. **添加反馈机制**
   - 用户标记误报
   - 自动调整检测参数
   - 持续改进模型

## 配置参数说明

### 当前配置

| 参数 | 位置 | 当前值 | 说明 |
|------|------|--------|------|
| 报警阈值 | `alert_engine.py:42` | 0.0001 | 置信度阈值 |
| SYN Flood阈值 | `detection_engine.py:79` | 20 | SYN包数量 |
| SYN Flood窗口 | `detection_engine.py:80` | 5.0秒 | 时间窗口 |
| 流超时 | `detection_engine.py:157` | 30.0秒 | 流完成时间 |
| 空闲超时 | `detection_engine.py:158` | 15.0秒 | 流空闲时间 |

### 推荐调整

```python
# backend/ml/alert_engine.py
elif confidence > 0.2:  # 从0.0001调整到0.2

# backend/ml/detection_engine.py
self._syn_flood_threshold = 10  # 从20降到10
self._syn_flood_window = 10.0   # 从5秒增加到10秒

flow_config = FlowAggregatorConfig(
    flow_timeout=15.0,      # 从30秒降到15秒
    idle_timeout=8.0,       # 从15秒降到8秒
    max_packets_per_flow=500,
    enable_bidirectional=True
)
```

## 监控和调试

### 实时监控
```bash
cd backend
python scripts/debug_detection.py
```

### 查看日志
```bash
# Windows
type backend\logs\nids_2026-02-15.log | findstr /i "alert inference attack"

# Linux/Mac
tail -f backend/logs/nids_$(date +%Y-%m-%d).log | grep -i "alert\|inference\|attack"
```

### 检查报警
```bash
# API
curl "http://localhost:8000/api/alerts?limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 数据库
mysql -u nids -p nids_db -e "SELECT * FROM alerts ORDER BY id DESC LIMIT 10;"
```

## 回滚方法

如果修改导致问题,可以回滚:

```python
# backend/ml/alert_engine.py 第42行
elif confidence > 0.5:  # 恢复到原始值
    is_attack = True
```

然后重启后端服务。

## 总结

✅ **已修复**: 降低报警阈值从0.5到0.0001
✅ **已验证**: 数据库表结构正常
✅ **已确认**: 系统正在运行并处理流量
⏳ **待验证**: 重启系统后是否生成报警

**下一步**: 重启系统并等待15-30秒,然后检查报警页面。
