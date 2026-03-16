# 故障排查: 为什么没有报警数据

## 问题描述
仪表盘显示有流量数据,但经过实时端口检测和Kali端口扫描后,没有生成报警。

## 可能原因分析

### 0. 数据库表结构问题 (最常见!)
**问题**: `alerts` 表缺少 `attack_type` 列,导致报警无法保存到数据库。

**症状**:
- 日志中可能显示 "Alert generated" 但数据库中没有记录
- 可能出现数据库错误: "Unknown column 'attack_type'"

**检查方法**:
```bash
cd backend
python scripts/check_db_schema.py
```

**解决方案**:
```bash
# 方案 1: 添加缺失的列 (推荐,不会丢失数据)
python scripts/fix_db_schema.py

# 方案 2: 重新初始化数据库 (会清空数据)
python db/init_db.py
```

### 1. 流聚合延迟
**问题**: 系统使用流级别检测,需要等待流完成才会进行推理。

**当前配置**:
```python
flow_timeout=30.0秒  # 流超时时间
idle_timeout=15.0秒  # 空闲超时时间
```

**解决方案**: 
- 等待15-30秒让流完成
- 或者降低超时时间(见下方配置调整)

### 2. SYN Flood 检测阈值过高
**问题**: 端口扫描速度较慢,达不到SYN flood检测阈值。

**当前配置**:
```python
_syn_flood_threshold = 20  # 需要20个SYN包
_syn_flood_window = 5.0    # 5秒窗口内
```

**解决方案**: 降低阈值(见下方配置调整)

### 3. 模型置信度阈值
**问题**: 模型对端口扫描的置信度可能低于0.5。

**当前逻辑**:
```python
# 只有当 confidence > 0.5 时才生成报警
if confidence > 0.5:
    is_attack = True
```

**解决方案**: 降低置信度阈值或检查模型训练质量

### 4. 模型未正确加载
**问题**: 模型文件不存在或加载失败。

**检查方法**:
```bash
cd backend
python scripts/diagnose_alerts.py
```

## 诊断步骤

### 步骤 0: 检查数据库表结构 (最重要!)
```bash
cd backend
python scripts/check_db_schema.py
```

这会检查:
- `alerts` 表是否存在
- `attack_type` 列是否存在
- 所有必需的列是否完整

**如果发现 `attack_type` 列缺失**:
```bash
# 自动修复
python scripts/fix_db_schema.py
```

### 步骤 1: 运行诊断脚本
```bash
cd backend
python scripts/diagnose_alerts.py
```

这会检查:
- Redis队列状态
- 数据库报警记录
- 模型文件
- 系统日志

### 步骤 2: 实时监控检测管道
```bash
cd backend
python scripts/debug_detection.py
```

这会显示:
- 实时包处理情况
- SYN包统计
- 端口扫描目标

### 步骤 3: 检查系统日志
```bash
# Windows
type backend\logs\nids_YYYY-MM-DD.log | findstr /i "error alert inference"

# Linux/Mac
tail -f backend/logs/nids_$(date +%Y-%m-%d).log | grep -i "error\|alert\|inference"
```

查找:
- 模型加载错误
- 推理错误
- 报警生成日志

### 步骤 4: 生成测试报警
使用API生成测试报警,验证前端显示是否正常:

```bash
curl -X POST "http://localhost:8000/api/alerts/test/generate?count=5" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 配置调整建议

### 方案 1: 降低检测阈值(推荐用于测试)

编辑 `backend/ml/detection_engine.py`:

```python
# 第79-81行,降低SYN flood阈值
self._syn_flood_threshold = 5   # 从20降到5
self._syn_flood_window = 10.0   # 从5秒增加到10秒

# 第157-159行,降低流超时时间
flow_config = FlowAggregatorConfig(
    flow_timeout=10.0,      # 从30秒降到10秒
    idle_timeout=5.0,       # 从15秒降到5秒
    max_packets_per_flow=500,
    enable_bidirectional=True
)

# 第372-375行,降低可疑流阈值
is_suspicious = (
    flow.syn_count >= 3 and    # 从5降到3
    syn_ratio > 0.6 and        # 从0.7降到0.6
    ack_ratio < 0.4 and        # 从0.3增加到0.4
    flow.bwd_packets == 0
)
```

### 方案 2: 降低报警置信度阈值

编辑 `backend/ml/alert_engine.py`:

```python
# 第40-42行,降低置信度阈值
if not is_attack:
    preds = prediction_result.get("predictions", [])
    if preds and preds[0] == 1:
        is_attack = True
    elif confidence > 0.3:  # 从0.5降到0.3
        is_attack = True
```

### 方案 3: 增加详细日志

编辑 `backend/ml/detection_engine.py`,在 `_process_completed_flows` 方法中添加:

```python
# 在第565行附近,inference之后添加
logger.info(f"Inference results: {attack_count} attacks detected")
logger.info(f"Predictions: {predictions}")
logger.info(f"Confidences: {confidences}")

# 在第580行附近,每个检测到的攻击添加
logger.info(f"Attack detected: {attack_type}, confidence: {confidences[i]:.3f}")
logger.info(f"Flow: {flow.flow_key.src_ip}:{flow.flow_key.src_port} -> {flow.flow_key.dst_ip}:{flow.flow_key.dst_port}")
```

## 测试验证

### 1. 使用Nmap进行端口扫描测试

```bash
# 快速SYN扫描(应该触发SYN flood检测)
nmap -sS -T4 --max-rate 100 TARGET_IP

# 慢速扫描(可能需要降低阈值)
nmap -sS -T2 TARGET_IP
```

### 2. 使用hping3进行SYN flood测试

```bash
# 发送大量SYN包
hping3 -S -p 80 --flood TARGET_IP

# 或者指定速率
hping3 -S -p 80 --faster TARGET_IP
```

### 3. 检查报警是否生成

```bash
# 查看数据库
mysql -u nids -p nids_db -e "SELECT COUNT(*) FROM alerts;"
mysql -u nids -p nids_db -e "SELECT * FROM alerts ORDER BY id DESC LIMIT 5;"

# 或使用API
curl "http://localhost:8000/api/alerts?limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 常见问题

### Q1: 队列有数据但没有报警
**A**: 可能是流还没有超时完成。等待15-30秒,或降低流超时时间。

### Q2: 日志显示"No models loaded"
**A**: 模型文件不存在或路径错误。检查 `models/` 目录。

### Q3: 日志显示"Inference error"
**A**: 特征提取失败或模型输入维度不匹配。检查模型训练时使用的特征数量。

### Q4: 置信度总是很低
**A**: 模型可能没有在类似的攻击数据上训练。考虑重新训练模型或使用预训练模型。

### Q5: 前端显示不了报警
**A**: 
1. 检查WebSocket连接是否正常
2. 检查浏览器控制台是否有错误
3. 尝试生成测试报警验证前端功能

## 进一步帮助

如果以上方法都无法解决问题,请:

1. 收集完整的日志文件
2. 运行诊断脚本并保存输出
3. 记录具体的测试步骤和结果
4. 检查系统资源使用情况(CPU, 内存, Redis)

## 性能优化建议

如果报警正常工作后,可以考虑:

1. **调整批处理大小**: `config.py` 中的 `BATCH_SIZE`
2. **启用/禁用SHAP**: `config.py` 中的 `ENABLE_SHAP`
3. **调整流超时**: 根据网络环境调整超时时间
4. **模型融合**: 使用多个模型提高检测准确率
