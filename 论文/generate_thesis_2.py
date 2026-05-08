import os

def generate_thesis_part2():
    thesis = []
    
    # 第四章
    thesis.append("## 第四章 系统设计\n\n")
    thesis.append("需求理清楚了，接下来就是怎么设计这个系统。这一章咱们详细聊聊系统的架构设计、核心模块划分，还有数据库和融合策略是怎么构思的。\n\n")
    
    thesis.append("### 4.1 总体架构设计\n\n")
    thesis.append("为了让系统好维护、好扩展，咱们采用了经典的前后端分离架构。\n\n")
    
    thesis.append("#### 4.1.1 前后端分离架构\n\n")
    thesis.append("在这个架构下，前端只负责画页面、跟用户交互，后端只负责干苦力活儿、处理数据。它们俩中间通过RESTful API和WebSocket进行通信。这样设计的好处是，前端小哥和后端老哥可以各干各的，互不干扰。以后哪怕前端想换成别的新框架，后端代码一行都不用改。\n\n")
    thesis.append("[注：此处插入图4-1，图名：系统总体架构图]\n\n")
    
    thesis.append("#### 4.1.2 分层设计（展示层、服务层、数据层）\n\n")
    thesis.append("在总体架构下面，系统被清晰地分成了三层：\n\n")
    thesis.append("第一层是展示层，也就是Vue 3写的前端页面。包括仪表盘、告警列表、实验管理这些用户能直接看到的东西。\n\n")
    thesis.append("第二层是服务层，这是整个系统的大脑。用FastAPI写的，里面包含了检测引擎、推理引擎、告警引擎等等。各种复杂的业务逻辑都在这儿处理。\n\n")
    thesis.append("第三层是数据层。咱们用了MySQL存结构化的数据（比如用户、告警记录），用了Redis做内存消息队列来缓冲网络流量，还有本地文件系统用来存PCAP包和模型文件。\n\n")
    
    thesis.append("### 4.2 核心模块设计\n\n")
    thesis.append("咱们把服务层拆成了好几个核心模块，大家各司其职，形成了一条完整的流水线。\n\n")
    thesis.append("[注：此处插入图4-2，图名：系统数据流图]\n\n")
    
    thesis.append("#### 4.2.1 流量捕获模块\n\n")
    thesis.append("这个模块就干一件事：抓包。它支持两种模式，一种是挂在网卡上实时抓（LiveCapture），另一种是读取PCAP文件离线回放（PcapReplayCapture）。抓到的包不会直接处理，而是先塞到Redis消息队列里。这样做是为了防止流量太大把系统冲垮，起到一个缓冲的作用。\n\n")
    
    thesis.append("#### 4.2.2 流聚合模块\n\n")
    thesis.append("从Redis里拿出来的还是一段段零散的数据包，流聚合模块（Flow Aggregator）负责把它们拼凑起来。它利用五元组信息把数据包归类。同时，它内部维护了一个状态机，管理这些流是处于活跃状态、空闲状态，还是已经结束了。为了过滤掉背景噪音，它还会自动把那些包数量太少的微小流给丢掉。\n\n")
    
    thesis.append("#### 4.2.3 特征提取模块\n\n")
    thesis.append("流拼好了之后，特征提取模块（Feature Extractor）就上场了。它的任务是根据CIC-IDS2017的标准，从流里提取出78维的特征。这中间还得做数据清洗，比如把缺失值填上0，把异常的无穷大数值处理掉。最后还会用StandardScaler做一下标准化，确保给到模型的特征都是干干净净的。\n\n")
    
    thesis.append("#### 4.2.4 推理引擎模块\n\n")
    thesis.append("这可是系统的核心大脑（Inference Engine）。它负责加载训练好的LightGBM或者1D-CNN模型。特征送过来之后，它就立刻给出预测结果。它不仅能输出预测的标签（是正常还是哪种攻击），还能给出这个预测的置信度有多高。\n\n")
    
    thesis.append("#### 4.2.5 告警引擎模块\n\n")
    thesis.append("推理引擎发现攻击后，会把结果扔给告警引擎（Alert Engine）。告警引擎不会像个愣头青一样马上就报警。它有事件合并和冷却机制。如果短时间内同一个IP发起了同一种攻击，它会把这些告警合并成一个事件，只增加重复次数。这样安全人员就不会被海量的重复告警给淹没了。\n\n")
    
    thesis.append("#### 4.2.6 SHAP分析模块\n\n")
    thesis.append("每次生成告警后，SHAP分析模块会在后台默默工作。它会调用TreeExplainer等工具，计算这次预测中各个特征的贡献度。然后把结果整理成JSON格式存下来，方便前端随时调取展示。\n\n")
    
    thesis.append("### 4.3 数据库设计\n\n")
    thesis.append("系统的数据得有个安稳的家，下面是咱们的数据库设计。\n\n")
    
    thesis.append("#### 4.3.1 数据表结构\n\n")
    thesis.append("咱们主要设计了这么几张核心表：\n\n")
    thesis.append("表4-1 数据库表结构清单\n\n")
    thesis.append("| 表名 | 用途说明 |\n")
    thesis.append("| --- | --- |\n")
    thesis.append("| users | 存储用户账号、密码哈希和角色信息 |\n")
    thesis.append("| alerts | 存储系统生成的网络攻击告警记录 |\n")
    thesis.append("| models | 存储训练好的模型元数据信息 |\n")
    thesis.append("| model_metrics | 存储模型的各项评估指标 |\n")
    thesis.append("| datasets | 存储用户上传的数据集信息 |\n\n")
    
    thesis.append("其中，最核心的告警表（alerts）结构如表4-2所示：\n\n")
    thesis.append("表4-2 告警表（alerts）结构\n\n")
    thesis.append("| 字段名 | 数据类型 | 描述 |\n")
    thesis.append("| --- | --- | --- |\n")
    thesis.append("| id | INT | 主键，自增 |\n")
    thesis.append("| timestamp | DATETIME | 告警产生的时间 |\n")
    thesis.append("| src_ip | VARCHAR(45) | 攻击源IP地址 |\n")
    thesis.append("| dst_ip | VARCHAR(45) | 攻击目标IP地址 |\n")
    thesis.append("| src_port | INT | 攻击源端口 |\n")
    thesis.append("| dst_port | INT | 攻击目标端口 |\n")
    thesis.append("| protocol | VARCHAR(10) | 网络协议 |\n")
    thesis.append("| attack_type | VARCHAR(50) | 判定的攻击类型 |\n")
    thesis.append("| confidence | FLOAT | 预测的置信度 |\n")
    thesis.append("| is_false_positive | BOOLEAN | 是否被人工标记为误报 |\n")
    thesis.append("| raw_features | JSON | 原始的78维特征数据 |\n\n")
    
    thesis.append("#### 4.3.2 ER图设计\n\n")
    thesis.append("这些表之间有着紧密的联系。比如告警表里有个外键指向模型表，记录是哪个模型报的警。模型指标表也通过外键和模型表关联。\n\n")
    thesis.append("[注：此处插入图4-4，图名：数据库ER图]\n\n")
    
    thesis.append("### 4.4 API接口设计\n\n")
    thesis.append("为了让前后端顺畅沟通，咱们设计了一套标准的RESTful API。接口路径都有个`/api`的前缀。\n\n")
    thesis.append("表4-5 API接口清单（部分）\n\n")
    thesis.append("| 请求方法 | 接口路径 | 功能说明 |\n")
    thesis.append("| --- | --- | --- |\n")
    thesis.append("| POST | /api/auth/login | 用户登录认证，返回JWT令牌 |\n")
    thesis.append("| POST | /api/system/start | 启动后台检测引擎 |\n")
    thesis.append("| GET | /api/alerts | 分页获取系统告警列表 |\n")
    thesis.append("| POST | /api/alerts/{id}/false_positive | 将某条告警标记为误报 |\n")
    thesis.append("| GET | /api/experiments | 获取所有的实验记录 |\n")
    thesis.append("| POST | /api/experiments/run | 启动一次新的对比实验 |\n\n")
    
    thesis.append("### 4.5 模型融合策略设计\n\n")
    thesis.append("这是本论文的核心亮点之一。咱们不满足于单打独斗，设计了模型融合策略来提升二分类检测的性能。\n\n")
    
    thesis.append("#### 4.5.1 加权融合\n\n")
    thesis.append("在二分类任务（只分正常和攻击）中，咱们采用了加权融合策略。LightGBM是个优秀的“老手”，它处理表格数据非常稳定，所以咱们给它分配了0.6的权重。1D-CNN虽然能提取深层特征，但有时候会有波动，所以给它分配了0.4的权重。\n\n")
    thesis.append("表4-8 加权融合权重配置表\n\n")
    thesis.append("| 模型名称 | 模型类型 | 融合权重 |\n")
    thesis.append("| --- | --- | --- |\n")
    thesis.append("| LightGBM | 梯度提升决策树 | 0.6 |\n")
    thesis.append("| 1D-CNN | 一维卷积神经网络 | 0.4 |\n\n")
    
    thesis.append("融合的数学公式长这样：\n\n")
    thesis.append("$$P_{\\text{fusion}} = \\frac{w_{\\text{LGBM}} \\cdot P_{\\text{LGBM}} + w_{\\text{CNN}} \\cdot P_{\\text{CNN}}}{w_{\\text{LGBM}} + w_{\\text{CNN}}}$$\n\n")
    thesis.append("[注：LaTeX代码：P_{\\text{fusion}} = \\frac{w_{\\text{LGBM}} \\cdot P_{\\text{LGBM}} + w_{\\text{CNN}} \\cdot P_{\\text{CNN}}}{w_{\\text{LGBM}} + w_{\\text{CNN}}}]\n\n")
    thesis.append("系统在推理的时候，会分别让两个模型给出是攻击的概率。然后按照公式把概率加权平均。如果最后算出来的融合概率大于0.5，系统就拍板认定这是一次攻击。\n\n")
    thesis.append("[注：此处插入图4-5，图名：加权融合策略流程图]\n\n")
    
    thesis.append("### 4.6 人机协同学习设计\n\n")
    thesis.append("机器学习模型不可能永远不犯错。所以咱们设计了人机协同学习机制，让模型能从错误中学习。\n\n")
    
    thesis.append("#### 4.6.1 误报反馈机制\n\n")
    thesis.append("如果安全分析师在前端发现某条告警其实是正常流量，他可以点一下“标记为误报”。系统收到这个指令后，不仅会把这条告警在界面上划掉，还会把当时提取的78维特征存到一个专门的CSV文件里（比如`human_feedback_fp.csv`）。这就是在给模型攒错题本。\n\n")
    
    thesis.append("#### 4.6.2 持续学习流程\n\n")
    thesis.append("等错题攒得差不多了，用户再启动模型训练的时候。训练模块会自动把这个错题本里的数据拿出来。而且为了加深模型的印象，还会对这些误报样本进行过采样（比如默认放大100倍），然后混在正常训练集里一起让模型重新学习。这样模型下次再碰到类似的流量，就不会再犯同样的错误了。\n\n")

    # 第五章
    thesis.append("## 第五章 系统实现\n\n")
    thesis.append("设计图纸画好了，接下来就是搬砖写代码的环节。这一章咱们讲讲开发环境怎么搭的，核心功能是怎么一行行代码敲出来的。\n\n")
    
    thesis.append("### 5.1 开发环境搭建\n\n")
    thesis.append("工欲善其事，必先利其器。咱们得先把各种开发环境配好。\n\n")
    
    thesis.append("#### 5.1.1 后端环境配置\n\n")
    thesis.append("后端咱们主要用的是Python。为了不把电脑环境搞乱，咱们用了虚拟环境。安装了Python 3.11版本。然后用pip把FastAPI、Uvicorn、SQLAlchemy、LightGBM、TensorFlow这些依赖包一股脑装上。因为要用到深度学习模型，如果电脑有英伟达的显卡，还得把CUDA和cuDNN配好，这样1D-CNN训练起来才会飞快。\n\n")
    thesis.append("表5-1 开发环境配置表\n\n")
    thesis.append("| 环境组件 | 版本要求 | 备注 |\n")
    thesis.append("| --- | --- | --- |\n")
    thesis.append("| 操作系统 | Windows 10/11 或 Linux | 推荐Linux环境部署 |\n")
    thesis.append("| Python | >= 3.10 | 核心后端语言 |\n")
    thesis.append("| Node.js | >= 18.0.0 | 前端编译环境 |\n")
    thesis.append("| MySQL | 8.0 | 关系型数据库 |\n")
    thesis.append("| Redis | 7.x | 内存缓存与消息队列 |\n\n")
    
    thesis.append("#### 5.1.2 前端环境配置\n\n")
    thesis.append("前端开发环境相对简单。装好Node.js之后，用npm或者yarn装好Vue、Vite这些工具。前端的代码结构很清晰，`src/views`下面放页面，`src/components`放组件，`src/api`专门用来封装和后端的网络请求。\n\n")
    
    thesis.append("#### 5.1.3 Docker容器化部署\n\n")
    thesis.append("为了让系统部署起来像安装软件一样简单，咱们写了`docker-compose.yml`脚本。用Docker把MySQL、Redis、后端的FastAPI和前端的Nginx都打包成容器。部署的时候只要在服务器上敲一行`docker-compose up -d`，整个系统就能自动跑起来了。\n\n")
    
    thesis.append("### 5.2 核心功能实现\n\n")
    thesis.append("环境搭好后，咱们来看看流水线上的几个核心功能是怎么用代码实现的。\n\n")
    
    thesis.append("#### 5.2.1 流量捕获实现\n\n")
    thesis.append("在`LiveCapture`类里，咱们调用了Scapy的`sniff`函数。设置好要监听的网卡接口后，它就会源源不断地吐出数据包。为了不阻塞主线程，抓包这个动作是放在后台独立的线程里跑的。抓到包后，咱们把它转换成二进制格式，塞进Redis的列表里。\n\n")
    
    thesis.append("#### 5.2.2 流聚合实现（状态机管理）\n\n")
    thesis.append("在`FlowAggregator`里，代码会不断从Redis里取包。拿到包后，先解析出五元组。如果这是一个新的五元组，就创建一个新的流对象，状态设为ACTIVE；如果是已经存在的流，就把包的信息（比如长度、时间戳）更新进去。咱们还给流设置了超时机制，比如一条TCP流如果120秒都没有新包进来，状态机就会把它标记为TIMEOUT，然后强制提取特征。\n\n")
    
    thesis.append("#### 5.2.3 特征提取实现（78维特征）\n\n")
    thesis.append("特征提取这块儿是个体力活。在流结束的时候，代码会遍历这条流里的所有数据包。算一算包的平均长度、最大长度，统计一下有多少个SYN包、多少个FIN包，计算一下包和包之间到达的时间间隔。最后把这些统计数据拼接成一个78维的数组。为了防止出现除以零这种错误，咱们加了很多异常处理代码，把有问题的值强制设为0。\n\n")
    
    thesis.append("#### 5.2.4 推理引擎实现（多模型支持）\n\n")
    thesis.append("推理引擎的实现用了工厂模式。不管底下是LightGBM还是1D-CNN，上面都封装成了统一的接口。如果是加权融合模型，代码会依次调用各个子模型拿到概率，然后用numpy库做一个简单的加权平均运算，最后返回最终的结果和置信度。\n\n")
    
    thesis.append("#### 5.2.5 告警引擎实现（事件合并、冷却机制）\n\n")
    thesis.append("告警引擎里有个巧妙的设计。咱们在内存里维护了一个活跃告警字典。收到新告警时，先拿源IP和攻击类型去字典里查。如果在冷却时间（比如15秒）内查到了记录，说明这是同一次攻击，就不往数据库里插新数据了，而是把老记录的`repeat_count`加1。这大大减轻了数据库的压力。\n\n")
    
    thesis.append("#### 5.2.6 SHAP分析实现\n\n")
    thesis.append("为了算SHAP值，咱们在后台启了一个轻量级的任务。每次有高危告警，就把这78维特征喂给`shap.TreeExplainer`。计算出来的结果是一个包含了每个特征贡献度的JSON数据。因为算这个稍微有点费时间，所以是异步执行的，不会卡住主流程。\n\n")
    
    thesis.append("### 5.3 训练模块实现\n\n")
    thesis.append("让系统变聪明的核心，就是训练模块的代码实现。\n\n")
    
    thesis.append("#### 5.3.1 数据预处理流程\n\n")
    thesis.append("用户传上来的CSV文件往往脏乱差。代码会先用Pandas把文件读进来，把列名里的空格全删掉，统一对齐到标准的78维。然后把无穷大的数值替换掉，有缺失的地方补上0。接着按照8:2的比例，把数据切分成训练集和测试集。\n\n")
    
    thesis.append("#### 5.3.2 类别不平衡处理（SMOTE、Focal Loss）\n\n")
    thesis.append("在CIC-IDS2017里，正常流量特别多，有些攻击流量特别少。这就导致类别极度不平衡。为了解决这个问题，咱们在代码里用上了SMOTE算法，它能合成少数类的样本，让数据变得稍微平衡一点。对于1D-CNN深度学习模型，咱们还在训练配置里启用了Focal Loss损失函数，让模型把注意力多放在那些难认的少数类攻击上。\n\n")
    
    thesis.append("表5-5 类别分布统计表\n\n")
    thesis.append("| 类别名称 | 原始样本数 | 占比 |\n")
    thesis.append("| --- | --- | --- |\n")
    thesis.append("| Normal | 2,273,097 | 80.30% |\n")
    thesis.append("| DoS Hulk | 231,073 | 8.16% |\n")
    thesis.append("| PortScan | 158,930 | 5.61% |\n")
    thesis.append("| DDoS | 128,027 | 4.52% |\n")
    thesis.append("| 其他攻击（合计） | 39,616 | 1.40% |\n\n")
    
    thesis.append("#### 5.3.3 训练进度监控\n\n")
    thesis.append("为了让用户在前端不至于干等着，咱们在LightGBM和Keras（跑1D-CNN用的）的训练过程里注入了自定义的回调函数（Callback）。每跑完一个Epoch，就把当前的进度百分比和损失值通过WebSocket推送到前端，这样界面上的进度条就能动起来了。\n\n")
    
    thesis.append("表5-3 LightGBM模型参数配置表\n\n")
    thesis.append("| 参数名 | 二分类值 | 多分类值 | 作用 |\n")
    thesis.append("| --- | --- | --- | --- |\n")
    thesis.append("| objective | binary | multiclass | 目标函数 |\n")
    thesis.append("| metric | binary_logloss | multi_logloss | 评估指标 |\n")
    thesis.append("| num_leaves | 31 | 31 | 叶子节点数 |\n")
    thesis.append("| learning_rate | 0.1 | 0.1 | 学习率 |\n")
    thesis.append("| num_class | - | 15 | 类别总数 |\n\n")
    
    thesis.append("### 5.4 实验模块实现\n\n")
    thesis.append("实验模块专门用来跑对比测试。\n\n")
    
    thesis.append("#### 5.4.1 实验配置管理\n\n")
    thesis.append("咱们写了个`ExperimentRunner`类。前端传过来配置参数，比如要跑二分类还是多分类（通过`is_multiclass`布尔值控制），要用哪些模型。代码会根据这些配置，准备好统一的数据集，保证所有的模型都在同一套卷子上考试，这样才公平。\n\n")
    
    thesis.append("#### 5.4.2 结果持久化与对比\n\n")
    thesis.append("模型跑完之后，代码会把Accuracy、F1这些指标算出来，然后连同模型的元数据一起，打包成一个JSON文件存到硬盘上。前端读取这些JSON文件，就能画出直观的对比柱状图了。\n\n")
    
    thesis.append("### 5.5 前端界面实现\n\n")
    thesis.append("前端代码的重点是展示和交互。\n\n")
    
    thesis.append("#### 5.5.1 主布局与导航\n\n")
    thesis.append("咱们用了Vue Router做路由。左边是导航菜单，右边是主内容区。这样点来点去页面不会刷新，体验就像是用原生软件一样。\n\n")
    
    thesis.append("#### 5.5.2 实时数据展示（WebSocket）\n\n")
    thesis.append("仪表盘上的流量曲线和最新告警都是实时动的。咱们在前端用原生的WebSocket API连到后端。收到新的消息就立刻更新Vue里面的响应式数据，页面马上就跟着变了。\n\n")
    
    thesis.append("#### 5.5.3 SHAP可视化图表\n\n")
    thesis.append("告警详情页里的SHAP图表是用ECharts画的水平柱状图。正向贡献画成红色，负向贡献画成蓝色，哪个特征贡献大柱子就长。这样就算是不懂算法的人，也能一眼看明白模型是咋想的。\n\n")
    
    # 写入文件 (append)
    with open(r"c:\SpaceB\nids-system\论文\毕业论文.md", "a", encoding="utf-8") as f:
        f.writelines(thesis)

generate_thesis_part2()
