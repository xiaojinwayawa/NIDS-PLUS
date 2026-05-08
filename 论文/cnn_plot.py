import matplotlib.pyplot as plt

# 设置 4:3 画布比例，学术论文风格
plt.figure(figsize=(8, 6), dpi=300)
plt.axis('off')  # 隐藏坐标轴

# 字体适配中文（论文宋体）
plt.rcParams['font.sans-serif'] = ['SimSun']
plt.rcParams['axes.unicode_minus'] = False

# 坐标定位
x1, y = 1.5, 3
x2 = 4.5
x3 = 7.5
box_w, box_h = 1.8, 1.2

# ========== 画三个模块方框 ==========
# 卷积层
rect1 = plt.Rectangle((x1-box_w/2, y-box_h/2), box_w, box_h, 
                      fill=False, linewidth=1.2)
plt.gca().add_patch(rect1)
plt.text(x1, y+0.2, '卷积层', fontsize=12, ha='center')
plt.text(x1, y-0.2, '提取局部特征', fontsize=9, ha='center')

# 池化层
rect2 = plt.Rectangle((x2-box_w/2, y-box_h/2), box_w, box_h, 
                      fill=False, linewidth=1.2)
plt.gca().add_patch(rect2)
plt.text(x2, y+0.2, '池化层', fontsize=12, ha='center')
plt.text(x2, y-0.2, '降维、增强平移不变性', fontsize=9, ha='center')

# 全连接层
rect3 = plt.Rectangle((x3-box_w/2, y-box_h/2), box_w, box_h, 
                      fill=False, linewidth=1.2)
plt.gca().add_patch(rect3)
plt.text(x3, y+0.2, '全连接层', fontsize=12, ha='center')
plt.text(x3, y-0.2, '最终分类决策', fontsize=9, ha='center')

# ========== 画箭头 ==========
plt.annotate('', xy=(x2-box_w/2-0.1, y), xytext=(x1+box_w/2+0.1, y),
             arrowprops=dict(arrowstyle='->', lw=1.2))
plt.annotate('', xy=(x3-box_w/2-0.1, y), xytext=(x2+box_w/2+0.1, y),
             arrowprops=dict(arrowstyle='->', lw=1.2))

# 标题
plt.text(4.5, 4.8, 'CNN 基本结构', fontsize=14, ha='center', weight='bold')

# 画布范围
plt.xlim(0, 10)
plt.ylim(1, 5)

# 保存高清图，白底无背景，适合论文
plt.tight_layout()
plt.savefig('cnn_structure.png', dpi=300, bbox_inches='tight', facecolor='white')
plt.close()

print("已生成论文专用 CNN 结构图：cnn_structure.png")