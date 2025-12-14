# NIDS - 网络入侵检测系统

基于混合机器学习与深度学习的实时网络入侵检测系统。

## 项目结构

```
.
├── backend/              # 后端服务（FastAPI）
│   ├── config.py        # 配置管理
│   ├── requirements.txt # Python依赖
│   └── Dockerfile       # 后端Docker配置
├── frontend/            # 前端应用（Vue 3 + TypeScript）
│   ├── src/            # 源代码
│   ├── package.json    # Node.js依赖
│   └── Dockerfile      # 前端Docker配置
├── data/               # 数据目录
│   ├── datasets/       # 训练数据集
│   └── pcaps/          # pcap文件
├── models/             # 训练好的模型文件
├── docker-compose.yml  # Docker Compose配置
└── README.md          # 项目说明
```

## 技术栈

### 后端
- **Web框架**: FastAPI
- **流量捕获**: Scapy
- **机器学习**: LightGBM, XGBoost, TensorFlow, PyTorch
- **可解释性**: SHAP
- **数据库**: MySQL, Redis

### 前端
- **框架**: Vue 3 + TypeScript
- **UI组件**: Element Plus
- **图表**: ECharts
- **构建工具**: Vite

## 快速开始

### 使用Docker Compose（推荐）

1. 克隆项目
```bash
git clone <repository-url>
cd nids-system
```

2. 启动所有服务
```bash
docker-compose up -d
```

3. 访问应用
- 前端: http://localhost
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

### 本地开发

#### 后端

1. 创建虚拟环境
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件配置数据库等参数
```

4. 启动服务
```bash
uvicorn main:app --reload
```

#### 前端

1. 安装依赖
```bash
cd frontend
npm install
```

2. 启动开发服务器
```bash
npm run dev
```

3. 访问 http://localhost:3000

## 系统要求

- Python 3.11+
- Node.js 20+
- MySQL 8.0+
- Redis 7+
- Docker & Docker Compose（可选）

## 跨平台支持

系统支持在以下平台运行：
- Linux (Ubuntu 20.04+, CentOS 8+)
- Windows 10/11

**注意**: 在Windows上进行网络抓包需要安装 [Npcap](https://npcap.com/)

## 许可证

MIT License
