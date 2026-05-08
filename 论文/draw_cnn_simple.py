
import matplotlib.pyplot as plt

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 创建图形
fig, ax = plt.subplots(figsize=(14, 6), dpi=300)
ax.axis('off')

# 网络结构各层
layers = [
    '输入层\n(78维特征)',
    '卷积层1\nConv1D(64,3)',
    '池化层1\nMaxPooling',
    '卷积层2\nConv1D(128,3)',
    '全局平均池化\nGlobalAvgPool',
    '全连接层\nDense(128)',
    '输出层\nSoftmax(15)'
]

# 绘制各层的方框
y_pos = list(range(len(layers), 0, -1))
width = 0.6

for i, layer in enumerate(layers):
    y = y_pos[i]
    # 绘制方框
    rect = plt.Rectangle((1 - width/2, y - 0.4, width, 0.8, 
                        facecolor='white', edgecolor='black', linewidth=2)
    ax.add_patch(rect)
    # 添加文字
    ax.text(1, y, layer, ha='center', va='center', fontsize=11, fontweight='bold')

# 设置坐标轴
ax.set_xlim(0, 2)
ax.set_ylim(0, len(layers) + 1)

# 绘制箭头
for i in range(len(layers)-1):
    y_from = y_pos[i]
    y_to = y_pos[i+1]
    ax.annotate('', xy=(1, y_to + 0.5), xytext=(1, y_from - 0.5),
                arrowprops=dict(arrowstyle='->', linewidth=2, color='black'))

# 添加标题
ax.text(1, len(layers) + 0.5, '图2 CNN网络基本结构示意图', 
        ha='center', va='bottom', fontsize=14, fontweight='bold')

plt.tight_layout()
plt.savefig('cnn_architecture_v2.png', dpi=300, bbox_inches='tight', facecolor='white')
plt.savefig('cnn_architecture_v2.pdf', bbox_inches='tight', facecolor='white')

print('CNN网络结构示意图已保存为 cnn_architecture_v2.png 和 cnn_architecture_v2.pdf')
plt.show()
