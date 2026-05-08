import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

# 混淆矩阵数据 (CNN)
cm = np.array([
    [1883159, 60334, 40880, 36261, 70344, 5718, 2832, 13706, 565, 13384, 65989, 36897, 4, 31099, 11925],
    [66, 1890, 6, 0, 2, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0],
    [1586, 2, 125744, 1, 640, 54, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [2, 0, 0, 9710, 151, 4, 4, 0, 0, 0, 0, 0, 0, 422, 0],
    [278, 11, 2220, 386, 227826, 124, 0, 78, 0, 1, 0, 0, 0, 146, 3],
    [24, 0, 3, 13, 1, 5360, 76, 0, 0, 1, 0, 5, 0, 12, 4],
    [16, 0, 0, 2, 2, 193, 5567, 0, 0, 0, 0, 5, 0, 7, 4],
    [0, 0, 0, 0, 11, 0, 48, 7868, 0, 0, 3, 6, 0, 0, 2],
    [0, 0, 0, 0, 0, 0, 0, 0, 11, 0, 0, 0, 0, 0, 0],
    [1, 1, 0, 0, 0, 0, 0, 0, 0, 34, 0, 0, 0, 0, 0],
    [7, 0, 0, 28, 113, 0, 49, 0, 0, 0, 158677, 26, 0, 2, 28],
    [10, 0, 2, 0, 11, 0, 21, 10, 0, 0, 3, 5821, 0, 19, 0],
    [0, 0, 0, 3, 1, 0, 0, 0, 0, 0, 0, 216, 70, 3, 1214],
    [2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 0, 11, 0],
    [0, 0, 0, 3, 17, 0, 0, 0, 0, 0, 1, 7, 0, 4, 620]
])

# 类别标签
labels = [
    'Normal',
    'Bot',
    'DDoS',
    'DoS GoldenEye',
    'DoS Hulk',
    'DoS Slowhttptest',
    'DoS slowloris',
    'FTP-Patator',
    'Heartbleed',
    'Infiltration',
    'PortScan',
    'SSH-Patator',
    'Web Attack - Brute Force',
    'Web Attack - Sql Injection',
    'Web Attack - XSS'
]

# 设置字体支持中文
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

# 创建图形
plt.figure(figsize=(16, 14))

# 使用对数刻度让小数值更明显
cm_log = np.log10(cm + 1)

# 绘制热力图
ax = sns.heatmap(cm_log, annot=cm, fmt='d', cmap='Blues', 
            xticklabels=labels, yticklabels=labels,
            cbar_kws={'label': '样本数 (对数刻度)'})

# 旋转x轴标签，避免重叠
plt.xticks(rotation=45, ha='right')
plt.yticks(rotation=0)

plt.xlabel('预测标签', fontsize=14)
plt.ylabel('真实标签', fontsize=14)
plt.tight_layout()
plt.savefig('confusion_matrix_cnn.png', dpi=300, bbox_inches='tight')
plt.show()