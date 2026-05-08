
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, Rectangle

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 创建图形
fig, ax = plt.subplots(figsize=(12, 8), dpi=300)
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis('off')

# 定义各层的位置和大小
layers = [
    {'name': '输入层', 'x': 5, 'y': 25, 'width': 15, 'height': 50, 'color': '#FFFFFF'},
    {'name': '卷积层', 'x': 25, 'y': 30, 'width': 12, 'height': 40, 'color': '#FFFFFF'},
    {'name': '池化层', 'x': 42, 'y': 32, 'width': 10, 'height': 36, 'color': '#FFFFFF'},
    {'name': '卷积层', 'x': 57, 'y': 35, 'width': 12, 'height': 30, 'color': '#FFFFFF'},
    {'name': '全连接层', 'x': 74, 'y': 30, 'width': 10, 'height': 40, 'color': '#FFFFFF'},
    {'name': '输出层', 'x': 89, 'y': 35, 'width': 8, 'height': 30, 'color': '#FFFFFF'}
]

# 绘制各层
for layer in layers:
    # 绘制带边框的矩形
    rect = FancyBboxPatch(
        (layer['x'], layer['y']),
        layer['width'],
        layer['height'],
        boxstyle="square,pad=0",
        facecolor=layer['color'],
        edgecolor='black',
        linewidth=1.5
    )
    ax.add_patch(rect)
    
    # 添加层名称
    ax.text(
        layer['x'] + layer['width']/2,
        layer['y'] - 5,
        layer['name'],
        ha='center',
        va='top',
        fontsize=10,
        fontweight='bold'
    )

# 绘制箭头
for i in range(len(layers)-1):
    start_x = layers[i]['x'] + layers[i]['width']
    end_x = layers[i+1]['x']
    y = 50
    
    # 绘制箭头
    ax.annotate(
        '',
        xy=(end_x, y),
        xytext=(start_x, y),
        arrowprops=dict(arrowstyle='->', linewidth=1.5, color='black')
    )

# 添加详细标注
annotations = [
    {'text': '输入特征\n(78维)', 'x': 12.5, 'y': 75},
    {'text': 'Conv1D\n(卷积核3×64)', 'x': 31, 'y': 75},
    {'text': 'MaxPooling\n(最大池化)', 'x': 47, 'y': 75},
    {'text': 'Conv1D\n(卷积核3×128)', 'x': 63, 'y': 75},
    {'text': 'Dense\n(128神经元)', 'x': 79, 'y': 75},
    {'text': 'Softmax\n(15类别)', 'x': 93, 'y': 75}
]

for ann in annotations:
    ax.text(
        ann['x'],
        ann['y'],
        ann['text'],
        ha='center',
        va='top',
        fontsize=9,
        bbox=dict(facecolor='white', edgecolor='black', pad=2, boxstyle='square,pad=0.2')
    )

# 添加标题
ax.text(50, 92, '图2 CNN网络基本结构示意图', ha='center', va='bottom', fontsize=14, fontweight='bold')

plt.tight_layout()
plt.savefig('cnn_architecture.png', dpi=300, bbox_inches='tight', facecolor='white')
plt.savefig('cnn_architecture.pdf', bbox_inches='tight', facecolor='white')

print('CNN网络基本结构示意图已保存为 cnn_architecture.png 和 cnn_architecture.pdf')
plt.show()
