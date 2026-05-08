
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# CIC-IDS2017数据
labels = [
    'DDoS',
    'PortScan',
    'Bot',
    'Infiltration',
    'Web Attack - Brute Force',
    'Web Attack - Sql Injection',
    'Web Attack - XSS',
    'FTP-Patator',
    'SSH-Patator',
    'DoS GoldenEye',
    'DoS Hulk',
    'DoS Slowhttptest',
    'DoS slowloris',
    'Heartbleed'
]

sizes = [
    128027,
    158930,
    1966,
    36,
    1507,
    21,
    652,
    7938,
    5897,
    10293,
    231072,
    5499,
    5796,
    11
]

# 创建图形
plt.figure(figsize=(12, 10), dpi=300)

# 使用灰度色系
colors = [
    '#000000', '#333333', '#555555', '#777777',
    '#888888', '#999999', '#AAAAAA', '#BBBBBB',
    '#CCCCCC', '#DDDDDD', '#EEEEEE', '#F0F0F0',
    '#FAFAFA', '#FFFFFF'
]

# 绘制饼图，带百分比和标签
wedges, texts, autotexts = plt.pie(
    sizes,
    labels=labels,
    autopct='%1.1f%%',
    startangle=90,
    colors=colors,
    wedgeprops={'edgecolor': 'black', 'linewidth': 1},
    textprops={'fontsize': 9}
)

# 设置百分比文字颜色
for autotext in autotexts:
    autotext.set_color('black')
    autotext.set_fontweight('bold')

# 使饼图为正圆形
plt.axis('equal')

# 添加标题
plt.title('CIC-IDS2017数据集攻击类型占比', fontsize=14, fontweight='bold')

# 保存为高分辨率图片
plt.tight_layout()
plt.savefig('cic_ids2017_pie_chart.png', dpi=300, bbox_inches='tight', facecolor='white')
plt.savefig('cic_ids2017_pie_chart.pdf', bbox_inches='tight', facecolor='white')

print('饼图已保存为 cic_ids2017_pie_chart.png 和 cic_ids2017_pie_chart.pdf')

# 显示图形
plt.show()
