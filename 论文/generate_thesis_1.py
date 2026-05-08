import os

def generate_thesis():
    thesis = []
    
    # 标题与摘要等可以在后面加，直接从第一章开始
    thesis.append("# 基于机器学习的网络入侵检测系统设计与实现\n\n")
    
    # 第一章
    thesis.append("## 第一章 绪论\n\n")
    thesis.append("### 1.1 研究背景与意义\n\n")
    thesis.append("#### 1.1.1 研究背景\n\n")
    thesis.append("现在的网络世界发展得特别快，咱们每天都在用各种各样的网络服务。可是，网络安全问题也越来越让人头疼。各种黑客攻击手段层出不穷，网络环境变得越来越复杂[1]。以前我们防御网络攻击，很多时候靠的是防火墙。但是传统的防火墙或者入侵检测系统，大多数是基于规则匹配的。也就是说，只有当攻击者的手段在我们的黑名单里，系统才能认出来。要是遇到新型的未知攻击，这些老办法就往往不管用了[2]。\n\n")
    thesis.append("面对海量的网络流量，光靠人工去写规则、找特征，不仅效率特别低，而且很容易出错。随着人工智能技术越来越成熟，大家开始尝试把机器学习和深度学习用在网络入侵检测上[3]。机器学习算法能够自己从海量的网络流量数据里学习，找出正常流量和异常流量的区别。这样一来，不仅能大大提高检测的准确率，还能发现那些以前没见过的未知攻击。\n\n")
    
    thesis.append("#### 1.1.2 研究意义\n\n")
    thesis.append("在网络入侵检测系统（NIDS）里引入机器学习模型，有着非常重要的实际意义。首先，这能让我们的网络防线变得更聪明。系统可以自动适应网络环境的变化，不需要咱们天天熬夜去更新防御规则[4]。其次，通过结合不同类型的算法，比如咱们这篇论文里用到的LightGBM和1D-CNN，咱们可以把它们各自的优点发挥出来。LightGBM处理表格数据特别快，而1D-CNN擅长提取空间和序列特征，两者结合能让检测效果更上一层楼[5]。\n\n")
    thesis.append("另外，咱们在做入侵检测的时候，不仅要知道“是不是攻击”，还得知道“是什么类型的攻击”。这就涉及到二分类和多分类的问题了。通过这两种维度的检测，咱们可以更全面地了解网络安全状况。不仅如此，咱们还引入了模型可解释性技术。也就是让模型不仅能抓坏人，还能告诉咱们为什么抓他。这在实际的业务落地中是非常关键的，因为安全专家需要这些依据来做出最终判断[6]。\n\n")
    
    thesis.append("### 1.2 国内外研究现状\n\n")
    thesis.append("#### 1.2.1 传统网络入侵检测方法\n\n")
    thesis.append("早期的网络入侵检测，主要依赖专家经验和规则库[7]。比如非常出名的Snort或者Suricata，它们就是靠匹配流量包里的特征码来工作的。这种方法好处是速度快，只要匹配上了，那就肯定是攻击，误报率比较低。但是缺点也很明显，就是太死板了。如果黑客把攻击流量稍微伪装一下，或者用了一种全新的攻击手段，那这些系统就成了摆设，完全检测不出来[8]。\n\n")
    
    thesis.append("#### 1.2.2 基于机器学习的入侵检测技术\n\n")
    thesis.append("后来，大家开始把机器学习引进来。像决策树、随机森林、支持向量机这些算法，都被用在了网络入侵检测上[9]。比如LightGBM这种基于梯度提升决策树的算法，因为训练速度快、占用内存小，在网络安全领域非常受欢迎[10]。它能很好地处理复杂的表格数据，分类准确率很高。同时，深度学习这几年也火得不行。特别是卷积神经网络（CNN），大家发现它不仅能看图，处理一维的网络流量数据也特别拿手。1D-CNN能自动从流量序列里提取深层次的特征，省去了人工挑选特征的麻烦[11]。\n\n")
    
    thesis.append("#### 1.2.3 模型可解释性研究\n\n")
    thesis.append("虽然机器学习和深度学习效果好，但它们很多时候就像个“黑盒”[12]。也就是咱们不知道模型到底是根据什么做出判断的。为了解决这个问题，可解释性研究变得越来越重要。现在比较流行的是SHAP值分析方法[13]。SHAP能告诉咱们，在判断一条流量是不是攻击时，哪个特征起的作用最大。这样安全人员在看到告警时，心里就有底了。\n\n")
    
    thesis.append("### 1.3 研究内容与目标\n\n")
    thesis.append("本课题的主要目标是设计并实现一个基于机器学习的网络入侵检测系统。咱们重点研究和对比LightGBM和1D-CNN这两种模型在网络入侵检测任务上的表现，并且设计一个合理的加权融合策略，把这俩兄弟结合起来。具体的研究内容包括下面几个方面：\n\n")
    thesis.append("第一，构建一个完整的数据处理流水线。从网络流量捕获开始，经过流聚合，最后提取出78维的标准流量特征。这为后面的模型训练和推理打好基础。\n\n")
    thesis.append("第二，研究和实现单体模型的训练与评估。咱们要分别训练LightGBM和1D-CNN模型。不仅要做区分正常和攻击的二分类实验，还要做能识别15种具体类别的多分类实验。通过多维度的指标来对比它们的性能。\n\n")
    thesis.append("第三，设计模型加权融合策略。咱们给LightGBM分配0.6的权重，给1D-CNN分配0.4的权重。通过这种融合方式，看看能不能在二分类任务上取得更好的检测效果。\n\n")
    thesis.append("第四，开发一套前后端分离的可视化系统。把这些检测能力封装成API，加上友好的前端界面。让用户能直观地看到实时流量、告警信息，还能进行模型的可解释性分析。\n\n")
    
    thesis.append("### 1.4 论文组织结构\n\n")
    thesis.append("这篇论文一共分成七个章节，具体安排如下：\n\n")
    thesis.append("第一章是绪论。主要介绍了课题的研究背景、意义，还有国内外的研究现状。同时也说明了咱们要研究的具体内容。\n\n")
    thesis.append("第二章介绍相关技术。这里会把咱们用到的各种技术都盘点一遍，包括流量捕获、特征提取、LightGBM算法、1D-CNN网络结构，还有系统开发用到的框架。\n\n")
    thesis.append("第三章是系统需求分析。咱们从功能需求和非功能需求两个方面，详细分析了这个入侵检测系统到底需要具备什么能力。\n\n")
    thesis.append("第四章是系统设计。重点讲解系统的总体架构、各个核心模块是怎么设计的，还有数据库结构和模型融合策略的具体设计方案。\n\n")
    thesis.append("第五章是系统实现。这部分会展示咱们是怎么把设计变成代码的。包括环境怎么搭，核心功能怎么写，前端页面是怎么实现的。\n\n")
    thesis.append("第六章是系统测试与实验分析。咱们会展示功能测试和性能测试的结果。更重要的是，这里会详细对比分析单体模型和融合模型在实验里的具体表现。\n\n")
    thesis.append("第七章是总结与展望。回顾一下咱们做的工作，说说系统还有哪些不足，以后可以怎么改进。\n\n")

    # 第二章
    thesis.append("## 第二章 相关技术概述\n\n")
    thesis.append("在开发这个网络入侵检测系统的过程中，咱们用到了不少关键技术。从底层的网络流量处理，到核心的机器学习算法，再到顶层的系统开发框架，这里咱们挨个梳理一遍。\n\n")
    
    thesis.append("### 2.1 网络流量捕获技术\n\n")
    thesis.append("咱们的系统要检测网络攻击，第一步肯定是得拿到网络流量。这部分主要涉及流量捕获和解析技术。\n\n")
    
    thesis.append("#### 2.1.1 Scapy抓包原理\n\n")
    thesis.append("Scapy是一个非常强大的Python网络流量处理库[14]。咱们用它来抓取网络网卡上的实时数据包。Scapy能在底层网络接口上监听，把路过的每一个数据包都捕获下来。它还能帮咱们把原始的二进制数据解析成我们能看懂的各种网络协议格式，比如IP层、TCP层、UDP层的信息都能轻松拿到。\n\n")
    
    thesis.append("#### 2.1.2 PCAP文件格式\n\n")
    thesis.append("除了实时抓包，咱们在做实验和测试的时候，经常会用到PCAP文件[15]。PCAP是一种标准的网络数据包存储格式。它就像是网络流量的录像带，把当时的网络情况原封不动地记录下来。咱们的系统支持读取PCAP文件，也就是把录像带回放一遍，这对于验证模型效果特别方便。\n\n")
    
    thesis.append("### 2.2 流聚合与特征提取\n\n")
    thesis.append("拿到单个的数据包还不够，因为很多网络攻击是持续一段时间的。所以咱们得把相关的数据包拼凑起来，变成一条条的“流”，然后再从中提取特征。\n\n")
    
    thesis.append("#### 2.2.1 CIC-IDS2017特征集\n\n")
    thesis.append("CIC-IDS2017是目前网络安全领域非常权威的一个公开数据集[16]。它不仅包含了各种真实的攻击流量，还定义了一套标准的78维流特征。这些特征包括了包的长度统计、到达时间间隔、TCP标志位计数等等。这78个特征就像是网络流量的“体检报告”，能很好地反映出流量的健康状况。\n\n")
    
    thesis.append("表2-1展示了部分特征的名称和含义：\n\n")
    thesis.append("| 特征名称 | 含义说明 |\n")
    thesis.append("| --- | --- |\n")
    thesis.append("| Flow Duration | 流持续时间 |\n")
    thesis.append("| Total Fwd Packets | 前向数据包总数 |\n")
    thesis.append("| Total Backward Packets | 后向数据包总数 |\n")
    thesis.append("| Flow Bytes/s | 每秒传输字节数 |\n")
    thesis.append("| Flow Packets/s | 每秒传输数据包数 |\n")
    thesis.append("| Fwd Packet Length Max | 前向数据包最大长度 |\n")
    thesis.append("| Bwd Packet Length Max | 后向数据包最大长度 |\n")
    thesis.append("| SYN Flag Count | SYN标志位出现次数 |\n")
    thesis.append("| ACK Flag Count | ACK标志位出现次数 |\n\n")
    thesis.append("[注：此处可补充完整的表2-1，表名：CIC-IDS2017数据集特征列表]\n\n")
    
    thesis.append("在类别方面，这个数据集定义了15个类别，也就是正常的流量加上14种具体的攻击类型。具体分类见表2-2。\n\n")
    thesis.append("表2-2 CIC-IDS2017攻击类型分类\n\n")
    thesis.append("| 序号 | 类别名称 | 描述 |\n")
    thesis.append("| --- | --- | --- |\n")
    thesis.append("| 1 | Normal | 正常流量 |\n")
    thesis.append("| 2 | DoS Hulk | 拒绝服务攻击（Hulk） |\n")
    thesis.append("| 3 | PortScan | 端口扫描 |\n")
    thesis.append("| 4 | DDoS | 分布式拒绝服务攻击 |\n")
    thesis.append("| 5 | DoS GoldenEye | 拒绝服务攻击（GoldenEye） |\n")
    thesis.append("| 6 | FTP-Patator | FTP暴力破解 |\n")
    thesis.append("| 7 | SSH-Patator | SSH暴力破解 |\n")
    thesis.append("| 8 | DoS slowloris | 拒绝服务攻击（slowloris） |\n")
    thesis.append("| 9 | DoS Slowhttptest | 拒绝服务攻击（Slowhttptest） |\n")
    thesis.append("| 10 | Bot | 僵尸网络 |\n")
    thesis.append("| 11 | Web Attack - Brute Force | Web暴力破解 |\n")
    thesis.append("| 12 | Web Attack - XSS | 跨站脚本攻击 |\n")
    thesis.append("| 13 | Infiltration | 渗透攻击 |\n")
    thesis.append("| 14 | Web Attack - Sql Injection | SQL注入攻击 |\n")
    thesis.append("| 15 | Heartbleed | 心血漏洞攻击 |\n\n")

    thesis.append("#### 2.2.2 五元组流标识\n\n")
    thesis.append("为了把数据包归类到不同的流里，咱们使用了经典的“五元组”概念。五元组指的是：源IP地址、目的IP地址、源端口、目的端口，还有网络协议（比如TCP或UDP）。只要这五个信息完全一样，我们就认为这些数据包属于同一次网络通信，也就是同一条流。系统会维护一个状态机，跟踪这些流的建立、活跃和关闭状态。\n\n")
    
    thesis.append("### 2.3 机器学习算法\n\n")
    thesis.append("咱们系统里用到的一员大将就是LightGBM。这是一款非常优秀的传统机器学习算法。\n\n")
    
    thesis.append("#### 2.3.1 LightGBM梯度提升树\n\n")
    thesis.append("LightGBM全称是轻量级梯度提升机，它是微软开源的一个框架[17]。梯度提升树的核心思想，就是咱们常说的“三个臭皮匠，顶个诸葛亮”。它会训练很多棵简单的决策树，每一棵新树都在努力纠正前面那些树犯的错误。把这些树的结果加起来，就能得到一个非常准确的预测。\n\n")
    thesis.append("LightGBM特别厉害的地方在于，它用了基于梯度的单边采样（GOSS）和互斥特征捆绑（EFB）技术。这让它在处理咱们这种海量的网络流量数据时，速度飞快，而且不太占内存。\n\n")
    thesis.append("[注：此处插入图2-1，图名：LightGBM梯度提升树原理图]\n\n")
    
    thesis.append("在数学上，如果咱们有训练数据集，模型的目标就是学习一个加法模型：\n\n")
    thesis.append("$$F_M(x) = \sum_{m=1}^{M} \gamma_m h_m(x)$$\n\n")
    thesis.append("[注：LaTeX代码：F_M(x) = \\sum_{m=1}^{M} \\gamma_m h_m(x)]\n\n")
    thesis.append("这里的$h_m(x)$就是咱们说的每一棵决策树，而$\\gamma_m$就是这棵树的权重。每一轮迭代，它都在拟合前一轮的负梯度，也就是残差。\n\n")
    
    thesis.append("### 2.4 深度学习模型\n\n")
    thesis.append("除了传统机器学习，咱们还用到了深度学习中的卷积神经网络。\n\n")
    
    thesis.append("#### 2.4.1 CNN卷积神经网络\n\n")
    thesis.append("大家平时听说CNN，多半是用在图像识别上。但在咱们系统里，用的是1D-CNN，也就是一维卷积神经网络[18]。网络流量特征是一维的数组，比如咱们那78维的特征。1D-CNN就像是一个滑动窗口，在这些特征上滑来滑去，自动提取特征之间的局部关联模式。\n\n")
    thesis.append("它的结构一般包括卷积层、池化层和全连接层。卷积层负责提取特征，池化层负责压缩数据、减少计算量，最后全连接层把这些特征综合起来，给出最终的分类结果。这省去了咱们人工去设计复杂特征的麻烦。\n\n")
    thesis.append("[注：此处插入图2-2，图名：1D-CNN网络结构图]\n\n")
    thesis.append("[注：此处插入图2-3，图名：一维卷积操作示意图]\n\n")
    
    thesis.append("一维卷积的数学操作可以表示为：\n\n")
    thesis.append("$$y_i = \sum_{j=1}^{k} x_{i+j-1} \cdot w_j + b$$\n\n")
    thesis.append("[注：LaTeX代码：y_i = \\sum_{j=1}^{k} x_{i+j-1} \\cdot w_j + b]\n\n")
    thesis.append("这里的$x$是输入的特征向量，$w$是卷积核的权重，$b$是偏置，而$y_i$就是计算出来的新特征。\n\n")
    
    thesis.append("### 2.5 模型可解释性技术\n\n")
    thesis.append("咱们不仅要模型算得准，还得让它能说清楚为什么这么算。\n\n")
    
    thesis.append("#### 2.5.1 SHAP值理论\n\n")
    thesis.append("SHAP值是基于博弈论里的沙普利值发展来的[19]。简单来说，它把模型预测的过程看作是一场游戏，每个特征就是游戏里的玩家。SHAP值能公平地计算出每个特征对最终预测结果的贡献有多大。是正向贡献让模型更倾向于是攻击，还是负向贡献让模型觉得是正常流量，一目了然。\n\n")
    
    thesis.append("#### 2.5.2 TreeExplainer解释器\n\n")
    thesis.append("在具体实现上，咱们给LightGBM这种树模型配了专门的TreeExplainer。它是一种针对树模型优化的快速解释算法。计算速度非常快，能实时在前端展示出每个告警的特征贡献图，这对安全人员分析威胁非常有帮助。\n\n")
    
    thesis.append("### 2.6 前后端技术栈\n\n")
    thesis.append("为了把算法落地成一个好用的系统，咱们采用了前后端分离的架构。\n\n")
    
    thesis.append("#### 2.6.1 FastAPI后端框架\n\n")
    thesis.append("后端用的是Python里的FastAPI框架。这玩意儿就像它的名字一样，速度非常快。它支持异步编程，能并发处理大量的网络请求。而且它能自动生成接口文档，开发起来特别顺手。搭配SQLAlchemy这个ORM工具，咱们操作数据库也变得很简单。\n\n")
    thesis.append("表2-3 后端技术栈\n\n")
    thesis.append("| 技术名称 | 版本 | 用途说明 |\n")
    thesis.append("| --- | --- | --- |\n")
    thesis.append("| FastAPI | 0.104.1 | 核心Web框架，提供RESTful API |\n")
    thesis.append("| Uvicorn | 0.24.0 | 异步HTTP服务器 |\n")
    thesis.append("| SQLAlchemy | 2.0.23 | 数据库ORM框架 |\n")
    thesis.append("| PyMySQL | 1.1.0 | MySQL数据库驱动 |\n")
    thesis.append("| Scapy | 2.5.0 | 网络数据包捕获与解析 |\n")
    thesis.append("| LightGBM | 4.1.0 | 梯度提升决策树模型 |\n")
    thesis.append("| TensorFlow | 2.15.0 | 深度学习框架（用于1D-CNN） |\n")
    thesis.append("| Pandas/NumPy | 最新版 | 数据处理与数值计算 |\n")
    thesis.append("| SHAP | 0.43.0 | 模型可解释性分析 |\n\n")
    
    thesis.append("#### 2.6.2 Vue 3前端框架\n\n")
    thesis.append("前端咱们选了Vue 3。这是一个非常流行、轻量级的前端框架。搭配Element Plus组件库，咱们能很快地搭出漂亮的管理界面。为了展示数据，咱们还用到了ECharts，能画出各种酷炫的统计图表。状态管理用了Pinia，让数据在各个页面之间共享变得很容易。\n\n")
    thesis.append("表2-4 前端技术栈\n\n")
    thesis.append("| 技术名称 | 版本 | 用途说明 |\n")
    thesis.append("| --- | --- | --- |\n")
    thesis.append("| Vue | 3.3.8 | 前端核心视图框架 |\n")
    thesis.append("| Vite | 5.0.4 | 前端构建工具 |\n")
    thesis.append("| Element Plus | 2.4.4 | UI组件库 |\n")
    thesis.append("| Pinia | 2.1.7 | 全局状态管理 |\n")
    thesis.append("| Vue Router | 4.2.5 | 页面路由管理 |\n")
    thesis.append("| Axios | 1.6.2 | HTTP网络请求客户端 |\n")
    thesis.append("| ECharts | 5.4.3 | 数据可视化图表 |\n\n")
    
    # 第三章
    thesis.append("## 第三章 系统需求分析\n\n")
    thesis.append("在动手写代码之前，咱们得先弄清楚这个系统到底要干些什么，要达到什么标准。这一章咱们就来详细扒一扒系统的各项需求。\n\n")
    
    thesis.append("### 3.1 功能需求\n\n")
    thesis.append("功能需求就是系统必须得有的基本操作能力。咱们的系统主要有下面这几个核心需求。\n\n")
    thesis.append("表3-1 系统功能需求表\n\n")
    thesis.append("| 需求编号 | 功能模块 | 详细描述 |\n")
    thesis.append("| --- | --- | --- |\n")
    thesis.append("| F-01 | 流量捕获与解析 | 支持从真实网卡实时抓包，也支持读取PCAP文件进行离线回放分析。 |\n")
    thesis.append("| F-02 | 特征聚合提取 | 能够把散乱的数据包按照五元组整合成流，并提取出78维的标准特征。 |\n")
    thesis.append("| F-03 | 实时推理检测 | 支持加载LightGBM和1D-CNN模型，对提取出的特征进行实时分类预测。 |\n")
    thesis.append("| F-04 | 模型训练与评估 | 允许用户上传数据集，在后台训练新的模型，并生成各种评估指标。 |\n")
    thesis.append("| F-05 | 告警管理 | 生成攻击告警，支持事件合并，提供误报标记和管理功能。 |\n")
    thesis.append("| F-06 | 实验对比与模型融合 | 支持配置和运行不同的对比实验，支持按权重(0.6/0.4)融合模型结果。 |\n")
    thesis.append("| F-07 | 可解释性分析 | 针对生成的告警，计算并展示SHAP特征贡献图，解释模型的判断依据。 |\n\n")
    
    thesis.append("#### 3.1.1 实时流量检测需求\n\n")
    thesis.append("系统得有双眼，能盯着网络看。这要求系统能直接挂在网卡上抓取真实流量，同时为了方便测试，也得能回放以前录好的PCAP流量文件。抓到数据后，系统必须能在后台把数据包聚合成流，并提取出78维特征，这个过程必须是自动且连续的。\n\n")
    
    thesis.append("#### 3.1.2 模型训练与评估需求\n\n")
    thesis.append("光能用现成的模型还不够，系统得支持“自己动手丰衣足食”。用户可以上传自己的CSV数据集，系统在后台能自动进行数据清洗、处理样本不平衡问题，然后训练出LightGBM或者1D-CNN模型。训练完了，还得给出一份详细的体检报告，包括准确率、召回率这些指标。\n\n")
    
    thesis.append("#### 3.1.3 实验对比研究需求\n\n")
    thesis.append("作为研究工具，系统得支持跑各种对比实验。不管是只分正常和攻击的二分类实验，还是能认出15种具体攻击类型的多分类实验，系统都得支持。并且系统需要把各种实验的结果持久化保存下来，方便咱们做对比分析。\n\n")
    
    thesis.append("#### 3.1.4 可解释性分析需求\n\n")
    thesis.append("告警不能只是一句冷冰冰的“发现攻击”。系统得配合SHAP工具，给每个告警画出一张特征贡献图。告诉用户，是因为这条流的包太大了，还是因为连接时间太长了，才被判定为攻击的。\n\n")
    
    thesis.append("### 3.2 非功能需求\n\n")
    thesis.append("除了能跑起来，系统还得跑得快、跑得稳。这就是非功能需求。\n\n")
    thesis.append("表3-2 系统非功能需求表\n\n")
    thesis.append("| 需求类别 | 详细要求描述 |\n")
    thesis.append("| --- | --- |\n")
    thesis.append("| 性能需求 | 推理延迟低，系统吞吐量要能扛住一般规模的网络流量冲击。 |\n")
    thesis.append("| 可用性需求 | 系统需要提供7x24小时的稳定服务，遇到异常情况能自动恢复或记录错误日志。 |\n")
    thesis.append("| 可扩展性需求 | 前后端分离设计，模块之间解耦，以后加新模型或者新功能得方便。 |\n")
    thesis.append("| 易用性需求 | 前端界面要美观大方，操作逻辑符合直觉，图表展示要清晰直观。 |\n\n")
    
    thesis.append("#### 3.2.1 性能需求（检测延迟、吞吐量）\n\n")
    thesis.append("在网络安全里，时间就是生命。系统从抓到包到发出告警，中间的检测延迟必须控制在毫秒级别。同时，系统得有足够的吞吐量。哪怕是在网络流量高峰期，系统也不能卡死。这就要求咱们的后台处理流水线必须非常高效，队列管理得当。\n\n")
    
    thesis.append("#### 3.2.2 可用性需求\n\n")
    thesis.append("系统部署上线后，得稳如老狗。不能因为个别格式错误的脏数据包就整个崩溃。这就要求代码里有完善的异常处理机制。就算是遇到断网或者数据库重启，系统也应该能优雅地处理，而不是直接报错退出。\n\n")
    
    thesis.append("#### 3.2.3 可扩展性需求\n\n")
    thesis.append("考虑到以后可能还会研究别的模型或者加入新功能，系统的架构不能写死。咱们采用前后端分离，并且把检测、训练、推理都拆分成独立的模块。这样以后想换个算法，或者升级前端页面，都不会牵一发而动全身。\n\n")
    
    thesis.append("### 3.3 系统用例分析\n\n")
    thesis.append("为了更清楚地展示用户怎么和系统交互，咱们画了系统用例图。咱们系统里的主要角色就是系统管理员或者安全分析师。\n\n")
    thesis.append("[注：此处插入图3-1，图名：系统用例图]\n\n")
    thesis.append("系统管理员可以通过网页登录系统。在仪表盘上看看整体的网络状况和告警统计。如果发现了可疑告警，可以点进去查看详情，还能看看SHAP图表分析。觉得模型不够聪明了，可以去数据集管理上传新数据，然后在训练模块启动一次新的训练。还可以跑到实验管理去跑一跑对比实验，看看融合模型是不是比单体模型更强。\n\n")
    
    # 写入文件
    with open(r"c:\SpaceB\nids-system\论文\毕业论文.md", "w", encoding="utf-8") as f:
        f.writelines(thesis)

generate_thesis()
