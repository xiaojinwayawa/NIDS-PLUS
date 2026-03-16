# NIDS 系统 - 快速参考卡

## 问题解决方案

**问题**: 流量密集但没有报警  
**原因**: 检测阈值过高  
**解决**: 已降低SYN Flood检测阈值 ✓

## 应用修改

✓ 已修改文件：
- `backend/ml/detection_engine.py` - 降低SYN检测阈值
- `backend/ml/alert_engine.py` - 增加置信度触发逻辑

## 立即验证

### 1. 重启系统 (从Python REPL)

```python
import requests
requests.post("http://localhost:8000/api/system/stop")
import time; time.sleep(2)
requests.post("http://localhost:8000/api/system/start", 
              json={"mode": "live", "model_name": "MyLightGBM_20260214(1)"})
```

### 2. 检查状态

```bash
# 在 backend 目录
C:/SpaceB/nids-system/backend/venv/Scripts/python.exe scripts/quick_network_check.py
```

预期输出：
```
traffic_queue 大小: > 0  ✓
系统正在捕获流量 ✓
```

### 3. 运行Nmap扫描

在 Kali 虚拟机：
```bash
nmap -sT -p 1-100 192.168.31.1
```

预期：NIDS 应该生成警报

## 前端验证

访问 `http://localhost:3000`:
- 左侧图表应显示流量上升
- 右侧警报列表应出现新警报

## 关键优化

| 参数 | 前 | 后 |
|------|-----|-----|
| SYN阈值 | 50 | 20 |
| 最小SYN数 | 10 | 5 |
| 源IP数要求 | 5+ | 3+ |
| 置信度触发 | - | 0.5 |

## 疑难排除

### 无法连接到系统
```bash
# 检查FastAPI服务
netstat -ano | findstr :8000
```

### Redis队列为空
```bash
redis-cli LLEN traffic_queue
```

### 没有新警报
```bash
tail -f backend/logs/nids_2026-02-15.log | grep -i "alert\|detected"
```

## 重要文件位置

- 代码: `c:\SpaceB\nids-system\backend\`
- 日志: `c:\SpaceB\nids-system\backend\logs\`
- 模型: `c:\SpaceB\nids-system\models\`
- 前端: `c:\SpaceB\nids-system\frontend\`

## 一行命令

```bash
# 完整诊断
cd c:\SpaceB\nids-system && C:/SpaceB/nids-system/backend/venv/Scripts/python.exe backend/scripts/quick_network_check.py 2>&1 | tail -30
```

## 支持文档

- 详细分析: `SYSTEM_OPTIMIZATION_SUMMARY.md`
- 故障排除: `ALERT_TROUBLESHOOTING.md`
- 网络诊断: `DIAGNOSIS_AND_SOLUTION.md`

---

**状态**: ✓ 优化已应用  
**下一步**: 重启系统 → 运行Nmap测试 → 验证警报
