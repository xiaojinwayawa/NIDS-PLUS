
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.patches as mpatches

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 创建图形
fig, ax = plt.subplots(figsize=(14, 7), dpi=300)
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis('off')

# 定义各层的参数
layers = [
    {
        'name': '输入层',
        'detail': '78维特征',
        'x': 5,
        'y': 25,
        'width': 12,
        'height': 50,
        'color': '#FFFFFF'
    },
    {
        'name': '卷积层1',
        'detail': 'Conv1D(64,3)\n+BatchNorm+ReLU',
        'x': 22,
        'y': 30,
        'width': 14,
        'height': 40,
        'color': '#FFFFFF'
    },
    {
        'name': '池化层1',
        'detail': 'MaxPooling1D',
        'x': 41,
        'y': 35,
        'width': 10,
        'height': 30,
        'color': '#FFFFFF'
    },
    {
        'name': '卷积层2',
        'detail': 'Conv1D(128,3)\n+BatchNorm+ReLU',
        'x': 56,
        'y': 30,
        'width': 14,
        'height': 40,
        'color': '#FFFFFF'
    },
    {
        'name': '全局平均池化',
        'detail': 'GlobalAvgPool1D',
        'x': 75,
        'y': 35,
        'width': 11,
        'height': 30,
        'color': '#FFFFFF'
    },
    {
        'name': '全连接层',
        'detail': 'Dense(128)\n+ReLU',
        'x': 91,
        'y': 30,
        'width': 8,
        'height': 40,
        'color': '#FFFFFF'
    }
]

# 绘制各层
for layer in layers:
    # 绘制带黑框的白色矩形
    rect = FancyBboxPatch(
        (layer['x'], layer['y']),
        layer['width'],
        layer['height'],
        boxstyle="square,pad=0",
        facecolor=layer['color'],
        edgecolor='black',
        linewidth=2
    )
    ax.add_patch(rect)
    
    # 添加层名称（底部）
    ax.text(
        layer['x'] + layer['width']/2,
        layer['y'] - 4,
        layer['name'],
        ha='center',
        va='top',
        fontsize=11,
        fontweight='bold'
    )
    
    # 添加详细说明（中间）
    ax.text(
        layer['x'] + layer['width']/2,
        layer['y'] + layer['height']/2,
        layer['detail'],
        ha='center',
        va='center',
        fontsize=9,
        linespacing=1.5
    )

# 绘制箭头
for i in range(len(layers)-1):
    start_x = layers[i]['x'] + layers[i]['width']
    end_x = layers[i+1]['x']
    y = 50
    
    ax.annotate(
        '',
        xy=(end_x, y),
        xytext=(start_x, y),
        arrowprops=dict(arrowstyle='->', linewidth=2, color='black')
    )

# 添加输出层（单独处理）
output_x = 103
output_y = 35
output_width = 6
output_height = 30

output_rect = FancyBboxPatch(
    (output_x, output_y),
    output_width,
    output_height,
    boxstyle="square,pad=0",
    facecolor='#FFFFFF',
    edgecolor='black',
    linewidth=2
)
ax.add_patch(output_rect)

ax.text(
    output_x + output_width/2,
    output_y - 4,
    '输出层',
    ha='center',
    va='top',
    fontsize=11,
    fontweight='bold'
)

ax.text(
    output_x + output_width/2,
    output_y + output_height/2,
    'Dense(15)\n+Softmax',
    ha='center',
    va='center',
    fontsize=9,
    linespacing=1.5
)

# 最后一个箭头
ax.annotate(
    '',
    xy=(output_x, 50),
    xytext=(layers[-1]['x'] + layers[-1]['width'], 50),
    arrowprops=dict(arrowstyle='->', linewidth=2, color='black')
)

# 添加标题
ax.text(50, 92, '图2 CNN网络基本结构示意图', ha='center', va='bottom', fontsize=14, fontweight='bold')

plt.tight_layout()
plt.savefig('cnn_architecture_final.png', dpi=300, bbox_inches='tight', facecolor='white')
plt.savefig('cnn_architecture_final.pdf', bbox_inches='tight', facecolor='white')

print('CNN网络结构示意图已保存为 cnn_architecture_final.png 和 cnn_architecture_final.pdf')
plt.show()
