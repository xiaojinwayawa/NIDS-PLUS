# 设计文档

## 概述

本系统是一个基于混合机器学习与深度学习的实时网络入侵检测系统（NIDS），采用前后端分离架构。系统融合传统机器学习模型（LightGBM/XGBoost）与深度学习模型（1D-CNN/GRU），通过异步批量推理实现低延迟检测（端到端<100ms），并集成SHAP可解释性分析帮助安全分析师理解检测结果。

### 核心特性

- **前后端分离**：后端独立运行提供API服务，前端通过Web界面控制系统启停
- **混合模型架构**：结合传统ML和深度学习的优势，提高检测准确率
- **实时检测**：异步批量推理保证端到端延迟<100ms
- **可解释性**：集成SHAP分析，提供特征重要性可视化
- **灵活流量源**：支持pcap文件回放和真实网卡抓包，可配置切换
- **跨平台支持**：兼容Linux和Windows操作系统

### 技术栈

**后端：**
- Web框架：FastAPI（异步高性能）
- 流量捕获：Scapy（跨平台）
- 特征提取：NumPy、Pandas
- 机器学习：LightGBM、XGBoost、TensorFlow/PyTorch
- 可解释性：SHAP
- 消息队列：Redis
- 数据库：MySQL
- 实时通信：WebSocket

**前端：**
- 框架：Vue 3 + TypeScript
- UI组件库：Element Plus（定制为直角风格）
- 图表库：ECharts
- 状态管理：Pinia
- HTTP客户端：Axios
- WebSocket客户端：原生WebSocket API

**部署：**
- 容器化：Docker + Docker Compose
- 反向代理：Nginx
- 进程管理：Supervisor（Linux）/ NSSM（Windows）

## 架构

### 总体架构

系统采用三层架构：

```
┌─────────────────────────────────────────────────────────────┐
│                         前端层                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 仪表盘   │  │ 流量分析 │  │ 告警详情 │  │ 模型管理 │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│         │              │              │              │       │
│         └──────────────┴──────────────┴──────────────┘       │
│                         │                                     │
│                    HTTP/WebSocket                            │
└─────────────────────────┼───────────────────────────────────┘
                          │
┌─────────────────────────┼───────────────────────────────────┐
│                    API服务层                                 │
│  ┌──────────────────────┴────────────────────────────────┐  │
│  │              FastAPI应用                               │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐           │  │
│  │  │ REST API │  │ WebSocket│  │ JWT认证  │           │  │
│  │  └──────────┘  └──────────┘  └──────────┘           │  │
│  └────────────────────┬──────────────────────────────────┘  │
└───────────────────────┼─────────────────────────────────────┘
                        │
┌───────────────────────┼─────────────────────────────────────┐
│                  检测引擎层                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ 流量捕获    │→ │ 特征提取    │→ │ 模型推理    │        │
│  │ (Scapy)     │  │ (NumPy)     │  │ (混合模型)  │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│         │                 │                 │               │
│         ↓                 ↓                 ↓               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ Redis队列   │  │ 告警引擎    │  │ SHAP分析    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│                           │                                  │
│                           ↓                                  │
│                  ┌─────────────┐                            │
│                  │ MySQL数据库 │                            │
│                  └─────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

### 状态机设计

系统状态转换：

```
     启动后端服务
          │
          ↓
    ┌──────────┐
    │  IDLE    │ ←──────────┐
    │ (待命)   │            │
    └──────────┘            │
          │                 │
    前端发送start命令      │
          │                 │
          ↓                 │
    ┌──────────┐            │
    │ RUNNING  │            │
    │ (运行中) │            │
    └──────────┘            │
          │                 │
    前端发送stop命令       │
          │                 │
          └─────────────────┘
```

### 数据流设计

```
网卡/pcap文件
     │
     ↓
流量捕获线程 ──→ Redis队列(raw_traffic)
                    │
                    ↓
特征提取线程池 ←─── Redis队列
     │
     ↓
Redis队列(features) ──→ 推理线程池
                           │
                           ↓
                    ┌──────┴──────┐
                    │  混合模型    │
                    │ LightGBM    │
                    │ XGBoost     │
                    │ 1D-CNN      │
                    │ GRU         │
                    └──────┬──────┘
                           │
                           ↓
                    结果融合(投票/加权)
                           │
                           ↓
                    ┌──────┴──────┐
                    │  正常流量   │  异常流量
                    └──────┬──────┘
                           │
                           ↓ (异常)
                    告警生成引擎
                           │
                    ┌──────┴──────┐
                    │             │
                    ↓             ↓
              MySQL存储    WebSocket推送
```

## 组件和接口

### 核心组件

#### 1. 流量捕获模块 (TrafficCapture)

**职责：** 从不同流量源捕获网络数据包

**接口：**
```python
class TrafficCapture:
    def __init__(self, mode: str, config: dict):
        """
        mode: 'pcap' 或 'live'
        config: 配置参数（pcap文件路径或网卡名称）
        """
        pass
    
    def start(self) -> None:
        """启动流量捕获"""
        pass
    
    def stop(self) -> None:
        """停止流量捕获"""
        pass
    
    def set_callback(self, callback: Callable) -> None:
        """设置数据包回调函数"""
        pass
```

**实现细节：**
- pcap模式：使用`scapy.rdpcap()`读取文件，支持循环回放
- live模式：使用`scapy.sniff()`实时抓包
- 跨平台处理：自动检测操作系统，使用对应的抓包库（Linux: libpcap, Windows: Npcap）
- 数据包放入Redis队列`raw_traffic`

#### 2. 特征提取模块 (FeatureExtractor)

**职责：** 从原始数据包提取标准化特征向量

**接口：**
```python
class FeatureExtractor:
    def __init__(self, dataset_type: str):
        """
        dataset_type: 'nsl-kdd' 或 'cic-ids2017'
        """
        pass
    
    def extract(self, packets: List[Packet]) -> np.ndarray:
        """
        提取特征向量
        返回: shape为(n_samples, n_features)的numpy数组
        """
        pass
    
    def preprocess(self, features: np.ndarray) -> np.ndarray:
        """标准化和编码"""
        pass
```

**特征说明：**
- NSL-KDD：41维特征（duration, protocol_type, service, flag等）
- CIC-IDS2017：78维特征（flow duration, packet length stats等）
- 预处理：标准化（StandardScaler）、分类变量编码（LabelEncoder）

#### 3. 推理引擎模块 (InferenceEngine)

**职责：** 管理模型加载和批量推理

**接口：**
```python
class InferenceEngine:
    def __init__(self):
        self.models: Dict[str, Model] = {}
        self.active_models: List[str] = []
    
    def load_model(self, model_id: str, model_path: str) -> None:
        """加载模型到内存"""
        pass
    
    def unload_model(self, model_id: str) -> None:
        """卸载模型"""
        pass
    
    def predict(self, features: np.ndarray) -> Dict[str, Any]:
        """
        批量推理
        返回: {
            'predictions': List[int],  # 0=正常, 1=异常
            'probabilities': List[float],
            'attack_types': List[str],
            'latency_ms': float
        }
        """
        pass
    
    def ensemble_predict(self, features: np.ndarray, method: str) -> Dict:
        """
        混合模型推理
        method: 'voting' 或 'weighted'
        """
        pass
```

**模型管理：**
- 支持的模型类型：LightGBM (.pkl), XGBoost (.pkl), TensorFlow (.h5), PyTorch (.pt)
- 模型热切换：新模型加载完成后再卸载旧模型，保证服务不中断
- 集成策略：
  - 投票法：多数投票决定最终结果
  - 加权平均：根据模型性能加权融合概率

#### 4. 告警引擎模块 (AlertEngine)

**职责：** 生成和管理告警记录

**接口：**
```python
class AlertEngine:
    def generate_alert(self, 
                      packet_info: dict,
                      prediction: dict) -> Alert:
        """
        生成告警记录
        返回: Alert对象
        """
        pass
    
    def save_alert(self, alert: Alert) -> int:
        """保存到数据库，返回alert_id"""
        pass
    
    def mark_false_positive(self, alert_id: int) -> None:
        """标记误报"""
        pass
```

**告警结构：**
```python
@dataclass
class Alert:
    timestamp: datetime
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    attack_type: str
    confidence: float
    is_false_positive: bool = False
```

#### 5. SHAP分析模块 (SHAPAnalyzer)

**职责：** 计算特征重要性

**接口：**
```python
class SHAPAnalyzer:
    def __init__(self, model, background_data: np.ndarray):
        """
        model: 待分析的模型
        background_data: 背景数据集（用于SHAP计算）
        """
        pass
    
    def explain(self, features: np.ndarray) -> Dict[str, float]:
        """
        计算SHAP值
        返回: {feature_name: shap_value}
        """
        pass
    
    def get_top_features(self, shap_values: dict, top_k: int = 10) -> List[Tuple]:
        """返回贡献度最高的K个特征"""
        pass
```

#### 6. API服务模块 (FastAPI Application)

**RESTful接口：**

```python
# 系统控制
POST   /api/system/start          # 启动检测引擎
POST   /api/system/stop           # 停止检测引擎
GET    /api/system/status         # 获取系统状态

# 用户认证
POST   /api/auth/login            # 用户登录
POST   /api/auth/logout           # 用户登出
GET    /api/auth/verify           # 验证token

# 告警管理
GET    /api/alerts                # 获取告警列表（分页、筛选）
GET    /api/alerts/{id}           # 获取告警详情
GET    /api/alerts/{id}/shap      # 获取SHAP分析结果
POST   /api/alerts/{id}/mark-fp   # 标记误报

# 流量分析
GET    /api/traffic/stats         # 获取流量统计
GET    /api/traffic/timeseries    # 获取时序数据
GET    /api/traffic/protocols     # 获取协议分布
GET    /api/traffic/top-ips       # 获取IP排行

# 攻击统计
GET    /api/attacks/distribution  # 获取攻击类型分布
GET    /api/attacks/timeseries    # 获取攻击趋势
GET    /api/attacks/accuracy      # 获取检测准确率

# 模型管理
GET    /api/models                # 获取模型列表
POST   /api/models/train          # 触发模型训练
GET    /api/models/{id}           # 获取模型详情
POST   /api/models/{id}/activate  # 激活模型
GET    /api/models/{id}/metrics   # 获取模型性能指标

# 数据集管理
GET    /api/datasets              # 获取数据集列表
POST   /api/datasets/upload       # 上传数据集
GET    /api/datasets/{id}         # 获取数据集详情
DELETE /api/datasets/{id}         # 删除数据集

# 系统日志
GET    /api/logs                  # 获取日志（分页、筛选）
GET    /api/logs/export           # 导出日志

# 系统配置
GET    /api/config                # 获取配置
PUT    /api/config                # 更新配置
```

**WebSocket接口：**

```python
# 实时数据推送
WS     /ws/realtime/traffic       # 实时流量数据
WS     /ws/realtime/alerts        # 实时告警推送
WS     /ws/realtime/metrics       # 实时性能指标
WS     /ws/realtime/training      # 训练进度推送
```

**WebSocket消息格式：**
```json
{
  "type": "traffic_update",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "throughput_pps": 1500,
    "throughput_mbps": 12.5,
    "normal_count": 1450,
    "anomaly_count": 50,
    "latency_ms": 85
  }
}
```

## 数据模型

### MySQL数据库表结构

#### 1. users（用户表）

```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    role VARCHAR(20) DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_username (username)
);
```

#### 2. alerts（告警表）

```sql
CREATE TABLE alerts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    timestamp TIMESTAMP NOT NULL,
    src_ip VARCHAR(45) NOT NULL,
    dst_ip VARCHAR(45) NOT NULL,
    src_port INT,
    dst_port INT,
    protocol VARCHAR(10),
    attack_type VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL,
    model_id INT,
    is_false_positive BOOLEAN DEFAULT FALSE,
    marked_by INT NULL,
    marked_at TIMESTAMP NULL,
    raw_features JSON,
    INDEX idx_timestamp (timestamp),
    INDEX idx_attack_type (attack_type),
    INDEX idx_src_ip (src_ip),
    FOREIGN KEY (model_id) REFERENCES models(id),
    FOREIGN KEY (marked_by) REFERENCES users(id)
);
```

#### 3. models（模型表）

```sql
CREATE TABLE models (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL,  -- 'lightgbm', 'xgboost', 'cnn', 'gru'
    version VARCHAR(20) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    dataset_type VARCHAR(50),  -- 'nsl-kdd', 'cic-ids2017'
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trained_at TIMESTAMP NULL,
    INDEX idx_type (type),
    INDEX idx_active (is_active)
);
```

#### 4. model_metrics（模型性能指标表）

```sql
CREATE TABLE model_metrics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    model_id INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accuracy FLOAT,
    precision_score FLOAT,
    recall FLOAT,
    f1_score FLOAT,
    false_positive_rate FLOAT,
    false_negative_rate FLOAT,
    inference_time_ms FLOAT,
    INDEX idx_model_timestamp (model_id, timestamp),
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
);
```

#### 5. traffic_logs（流量日志表）

```sql
CREATE TABLE traffic_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    timestamp TIMESTAMP NOT NULL,
    src_ip VARCHAR(45),
    dst_ip VARCHAR(45),
    protocol VARCHAR(10),
    packet_size INT,
    is_anomaly BOOLEAN,
    prediction_confidence FLOAT,
    INDEX idx_timestamp (timestamp),
    INDEX idx_anomaly (is_anomaly)
) PARTITION BY RANGE (UNIX_TIMESTAMP(timestamp)) (
    PARTITION p_old VALUES LESS THAN (UNIX_TIMESTAMP('2024-01-01')),
    PARTITION p_current VALUES LESS THAN MAXVALUE
);
```

#### 6. datasets（数据集表）

```sql
CREATE TABLE datasets (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL,  -- 'nsl-kdd', 'cic-ids2017', 'custom'
    file_path VARCHAR(255) NOT NULL,
    file_size_mb FLOAT,
    sample_count INT,
    feature_count INT,
    class_distribution JSON,  -- {"normal": 67343, "dos": 45927, ...}
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_by INT,
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);
```

#### 7. system_logs（系统日志表）

```sql
CREATE TABLE system_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level VARCHAR(10) NOT NULL,  -- 'DEBUG', 'INFO', 'WARNING', 'ERROR'
    module VARCHAR(50),
    message TEXT NOT NULL,
    details JSON,
    INDEX idx_timestamp (timestamp),
    INDEX idx_level (level)
) PARTITION BY RANGE (UNIX_TIMESTAMP(timestamp)) (
    PARTITION p_old VALUES LESS THAN (UNIX_TIMESTAMP('2024-01-01')),
    PARTITION p_current VALUES LESS THAN MAXVALUE
);
```

#### 8. system_config（系统配置表）

```sql
CREATE TABLE system_config (
    id INT PRIMARY KEY AUTO_INCREMENT,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    value_type VARCHAR(20),  -- 'string', 'int', 'float', 'bool', 'json'
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by INT,
    FOREIGN KEY (updated_by) REFERENCES users(id)
);
```

**默认配置项：**
```sql
INSERT INTO system_config (config_key, config_value, value_type, description) VALUES
('traffic_source_mode', 'pcap', 'string', '流量源模式: pcap或live'),
('pcap_file_path', '/data/pcaps/sample.pcap', 'string', 'pcap文件路径'),
('network_interface', 'eth0', 'string', '网卡名称'),
('batch_size', '100', 'int', '批量推理大小'),
('inference_interval_ms', '50', 'int', '推理间隔（毫秒）'),
('alert_threshold', '0.8', 'float', '告警阈值'),
('max_queue_size', '10000', 'int', 'Redis队列最大长度'),
('enable_shap', 'true', 'bool', '是否启用SHAP分析'),
('log_level', 'INFO', 'string', '日志级别');
```

### Redis数据结构

```python
# 流量队列
raw_traffic: List[bytes]  # 原始数据包（序列化）

# 特征队列
features: List[bytes]  # 特征向量（序列化numpy数组）

# 实时统计（过期时间60秒）
stats:current: Hash {
    'throughput_pps': int,
    'throughput_mbps': float,
    'normal_count': int,
    'anomaly_count': int,
    'latency_ms': float
}

# 系统状态
system:state: String  # 'idle', 'running', 'stopped'

# 模型缓存
model:{model_id}:metadata: Hash  # 模型元数据

# 会话管理
session:{token}: Hash {
    'user_id': int,
    'username': str,
    'expires_at': timestamp
}  # 过期时间24小时
```

### 前端数据模型

```typescript
// 系统状态
interface SystemStatus {
  state: 'idle' | 'running' | 'stopped';
  uptime: number;
  trafficSource: 'pcap' | 'live';
  activeModels: string[];
}

// 实时流量数据
interface TrafficMetrics {
  timestamp: string;
  throughputPps: number;
  throughputMbps: number;
  normalCount: number;
  anomalyCount: number;
  latencyMs: number;
}

// 告警
interface Alert {
  id: number;
  timestamp: string;
  srcIp: string;
  dstIp: string;
  srcPort: number;
  dstPort: number;
  protocol: string;
  attackType: string;
  confidence: number;
  isFalsePositive: boolean;
}

// SHAP分析结果
interface SHAPResult {
  alertId: number;
  features: Array<{
    name: string;
    value: number;
    shapValue: number;
  }>;
  topFeatures: Array<{
    name: string;
    contribution: number;
  }>;
}

// 模型信息
interface Model {
  id: number;
  name: string;
  type: 'lightgbm' | 'xgboost' | 'cnn' | 'gru';
  version: string;
  isActive: boolean;
  metrics: {
    accuracy: number;
    precision: number;
    recall: number;
    f1Score: number;
    fpr: number;
    fnr: number;
  };
  createdAt: string;
}

// 数据集
interface Dataset {
  id: number;
  name: string;
  type: 'nsl-kdd' | 'cic-ids2017' | 'custom';
  fileSizeMb: number;
  sampleCount: number;
  featureCount: number;
  classDistribution: Record<string, number>;
  uploadedAt: string;
}
```


## 正确性属性

*属性是系统在所有有效执行中应该保持为真的特征或行为——本质上是关于系统应该做什么的形式化陈述。属性作为人类可读规范和机器可验证正确性保证之间的桥梁。*

### 属性 1：系统状态转换一致性
*对于任何*系统状态，当接收到有效的状态转换命令时，系统应该转换到预期状态并保持状态一致性
**验证需求：1.3, 1.4**

### 属性 2：认证令牌有效性
*对于任何*生成的JWT令牌，在过期时间内该令牌应该能够通过验证，过期后应该被拒绝
**验证需求：2.4, 2.5**

### 属性 3：流量数据完整性
*对于任何*从流量源捕获的数据包，该数据包应该被完整地放入Redis队列而不丢失
**验证需求：3.4**

### 属性 4：特征维度一致性
*对于任何*NSL-KDD格式的流量，提取的特征向量维度应该恰好为41；对于任何CIC-IDS2017格式的流量，特征向量维度应该恰好为78
**验证需求：4.1, 4.2**

### 属性 5：推理延迟保证
*对于任何*批量特征数据，从特征提取完成到返回推理结果的时间应该小于100毫秒
**验证需求：5.5, 19.1**

### 属性 6：告警数据完整性
*对于任何*被判定为异常的流量，系统应该生成包含所有必需字段（时间戳、源IP、目标IP、攻击类型、置信度）的告警记录
**验证需求：6.2**

### 属性 7：告警持久化一致性
*对于任何*生成的告警，该告警应该同时被存储到MySQL数据库和通过WebSocket推送到前端
**验证需求：6.3, 6.4**

### 属性 8：SHAP计算时效性
*对于任何*告警的SHAP分析请求，系统应该在5秒内返回特征重要性结果
**验证需求：7.3**

### 属性 9：WebSocket推送实时性
*对于任何*实时数据更新，系统应该在100毫秒内通过WebSocket推送到已连接的前端客户端
**验证需求：8.4, 19.4**

### 属性 10：模型加载幂等性
*对于任何*已加载的模型，重复加载同一模型应该不改变系统状态（幂等操作）
**验证需求：5.1**

### 属性 11：批量推理吞吐量
*对于任何*1秒时间窗口，系统应该能够处理至少1000条流量记录
**验证需求：19.2**

### 属性 12：跨平台路径兼容性
*对于任何*文件路径操作，在Linux和Windows平台上应该产生正确的路径格式
**验证需求：20.5**


## 错误处理

### 错误分类

**1. 流量捕获错误**
- 网卡权限不足
- 网卡不存在
- pcap文件不存在或损坏
- 网络断开

**处理策略：**
```python
try:
    capture.start()
except PermissionError:
    logger.error("网卡权限不足，需要管理员权限")
    notify_frontend({"type": "error", "message": "需要管理员权限"})
    system_state = "error"
except FileNotFoundError:
    logger.error(f"pcap文件不存在: {pcap_path}")
    notify_frontend({"type": "error", "message": "pcap文件未找到"})
```

**2. 特征提取错误**
- 数据包格式不支持
- 特征计算异常
- 内存不足

**处理策略：**
- 记录错误日志
- 跳过异常数据包
- 继续处理下一批数据

**3. 模型推理错误**
- 模型文件损坏
- 内存溢出
- 特征维度不匹配

**处理策略：**
```python
try:
    predictions = model.predict(features)
except MemoryError:
    logger.error("内存不足，减小批量大小")
    # 降级处理：减小batch_size
    batch_size = batch_size // 2
    retry_with_smaller_batch()
except ValueError as e:
    logger.error(f"特征维度不匹配: {e}")
    skip_batch()
```

**4. 数据库错误**
- 连接失败
- 查询超时
- 磁盘空间不足

**处理策略：**
- 自动重连（最多3次）
- 降级到内存模式（告警暂存Redis）
- 磁盘空间告警

**5. WebSocket错误**
- 连接断开
- 消息发送失败

**处理策略：**
- 前端自动重连
- 后端缓存最近N条消息，重连后补发

### 异常恢复机制

```python
class ErrorRecovery:
    def __init__(self):
        self.retry_count = {}
        self.max_retries = 3
    
    def handle_error(self, component: str, error: Exception):
        """统一错误处理入口"""
        if component not in self.retry_count:
            self.retry_count[component] = 0
        
        self.retry_count[component] += 1
        
        if self.retry_count[component] <= self.max_retries:
            logger.warning(f"{component} 错误，尝试恢复 ({self.retry_count[component]}/{self.max_retries})")
            return self.recover(component)
        else:
            logger.error(f"{component} 恢复失败，进入降级模式")
            return self.degrade(component)
    
    def recover(self, component: str):
        """尝试恢复"""
        if component == "database":
            return reconnect_database()
        elif component == "capture":
            return restart_capture()
    
    def degrade(self, component: str):
        """降级处理"""
        if component == "database":
            switch_to_memory_mode()
        elif component == "shap":
            disable_shap_analysis()
```


## 测试策略

### 单元测试

**测试框架：** pytest

**测试覆盖：**

1. **特征提取模块**
   - 测试NSL-KDD特征提取正确性
   - 测试CIC-IDS2017特征提取正确性
   - 测试特征标准化
   - 测试异常数据包处理

2. **推理引擎模块**
   - 测试单模型推理
   - 测试混合模型投票
   - 测试混合模型加权
   - 测试模型加载/卸载

3. **告警引擎模块**
   - 测试告警生成
   - 测试告警持久化
   - 测试误报标记

4. **SHAP分析模块**
   - 测试SHAP值计算
   - 测试Top-K特征提取

5. **API接口**
   - 测试所有REST端点
   - 测试JWT认证
   - 测试参数验证

### 属性测试（Property-Based Testing）

**测试框架：** Hypothesis（Python）

**测试属性：**

1. **属性测试 1：特征维度一致性**
   ```python
   from hypothesis import given, strategies as st
   
   @given(st.lists(st.binary(), min_size=1, max_size=100))
   def test_feature_dimension_consistency(packets):
       """对于任何数据包列表，NSL-KDD特征应该是41维"""
       extractor = FeatureExtractor('nsl-kdd')
       features = extractor.extract(packets)
       assert features.shape[1] == 41
   ```

2. **属性测试 2：推理延迟保证**
   ```python
   @given(st.integers(min_value=1, max_value=1000))
   def test_inference_latency(batch_size):
       """对于任何批量大小，推理延迟应该<100ms"""
       features = generate_random_features(batch_size, 41)
       start = time.time()
       engine.predict(features)
       latency = (time.time() - start) * 1000
       assert latency < 100
   ```

3. **属性测试 3：告警数据完整性**
   ```python
   @given(st.dictionaries(
       keys=st.sampled_from(['src_ip', 'dst_ip', 'protocol']),
       values=st.text()
   ))
   def test_alert_completeness(packet_info):
       """对于任何数据包信息，生成的告警应该包含所有必需字段"""
       alert = alert_engine.generate_alert(packet_info, prediction)
       assert all(hasattr(alert, field) for field in 
                  ['timestamp', 'src_ip', 'dst_ip', 'attack_type', 'confidence'])
   ```

4. **属性测试 4：模型加载幂等性**
   ```python
   @given(st.text(min_size=1))
   def test_model_load_idempotent(model_id):
       """重复加载同一模型应该是幂等的"""
       engine.load_model(model_id, model_path)
       state1 = engine.get_state()
       engine.load_model(model_id, model_path)
       state2 = engine.get_state()
       assert state1 == state2
   ```

5. **属性测试 5：跨平台路径兼容性**
   ```python
   @given(st.lists(st.text(min_size=1), min_size=1))
   def test_path_compatibility(path_parts):
       """路径操作在不同平台应该产生正确格式"""
       from pathlib import Path
       path = Path(*path_parts)
       assert path.exists() or not path.is_absolute()
   ```

### 集成测试

1. **端到端流程测试**
   - pcap回放 → 特征提取 → 模型推理 → 告警生成 → 数据库存储
   - 验证整个流程的数据一致性

2. **WebSocket通信测试**
   - 测试前端连接
   - 测试实时数据推送
   - 测试断线重连

3. **模型训练流程测试**
   - 触发训练 → 进度推送 → 模型保存 → 模型激活

### 性能测试

**测试工具：** Locust（负载测试）

**测试场景：**

1. **吞吐量测试**
   - 目标：1000条/秒
   - 测试方法：使用大型pcap文件回放，监控处理速度

2. **延迟测试**
   - 目标：端到端<100ms
   - 测试方法：记录每批数据的处理时间

3. **并发测试**
   - 目标：支持10个并发前端连接
   - 测试方法：模拟多个WebSocket客户端

4. **压力测试**
   - 测试系统在高负载下的稳定性
   - 逐步增加流量直到系统达到瓶颈

### 测试数据

**数据集：**
- NSL-KDD训练集：125,973条记录
- NSL-KDD测试集：22,544条记录
- CIC-IDS2017：约280万条记录

**测试pcap文件：**
- 正常流量pcap（用于基线测试）
- 攻击流量pcap（DoS, Probe, R2L, U2R）
- 混合流量pcap（正常+攻击）

