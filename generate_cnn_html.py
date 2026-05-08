import json
import os

def generate_cnn_html():
    html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>1D-CNN 网络结构图</title>
    <style>
        body {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background-color: #f5f5f5; /* 方便在浏览器中预览，实际截图时背景是白色的 */
            font-family: 'Times New Roman', Times, serif;
        }
        .container {
            background-color: white;
            padding: 40px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            /* 适合论文的尺寸，A4纸宽度大概800-900px */
            width: 900px;
            text-align: center;
        }
        h2 {
            margin-top: 0;
            margin-bottom: 30px;
            font-size: 22px;
            color: black;
        }
        svg {
            font-family: 'Times New Roman', Times, serif;
            display: block;
            margin: 0 auto;
        }
        .layer-box {
            fill: white;
            stroke: black;
            stroke-width: 1.5;
        }
        .layer-text {
            font-size: 12px;
            fill: black;
            text-anchor: middle;
            dominant-baseline: middle;
        }
        .layer-title {
            font-size: 14px;
            fill: black;
            text-anchor: middle;
            font-weight: bold;
        }
        .layer-subtitle {
            font-size: 12px;
            fill: #333;
            text-anchor: middle;
        }
        .arrow {
            stroke: black;
            stroke-width: 1.5;
            fill: none;
        }
        .arrow-head {
            fill: black;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>1D-CNN Architecture for Network Intrusion Detection</h2>
        <!-- SVG content will be injected here -->
        {svg_content}
    </div>
</body>
</html>
"""
    
    # 定义每一层: (名称, 形状文本, 高度, 宽度, 深度(用于绘制立体堆叠效果), 子标题)
    # 高度模拟序列长度，宽度模拟扁平结构，深度模拟通道数
    layers = [
        ("Input", "(78, 1)", 156, 16, 1, "Features"),
        ("Conv1D", "(78, 64)", 156, 16, 3, "64 filters"),
        ("MaxPool", "(39, 64)", 78, 16, 3, "pool_size=2"),
        ("Conv1D", "(39, 128)", 78, 16, 4, "128 filters"),
        ("MaxPool", "(19, 128)", 38, 16, 4, "pool_size=2"),
        ("Flatten", "(2432)", 16, 120, 1, ""),
        ("Dense", "(128)", 100, 16, 1, "ReLU"),
        ("Dense", "(64)", 60, 16, 1, "ReLU"),
        ("Output", "(Classes)", 30, 16, 1, "Softmax/Sigmoid")
    ]

    svg_width = 880
    svg_height = 350
    svg_elements = []
    
    # 整个图的垂直中心点
    center_y = 150
    
    x_offset = 30
    centers = []
    
    for i, (name, shape, h, w, depth, subtitle) in enumerate(layers):
        # 堆叠矩形的横向偏移量
        depth_offset = 4
        
        # 计算该层最前方矩形的中心点X
        layer_x_center = x_offset + w/2 + (depth-1)*depth_offset/2
        centers.append(layer_x_center)
        
        # 从后往前绘制堆叠的矩形（制造3D多通道效果）
        for d in range(depth-1, -1, -1):
            curr_x = x_offset + d * depth_offset
            curr_y = center_y - h/2 - d * depth_offset
            
            # 白底黑框，符合学术风
            rect = f'<rect x="{curr_x}" y="{curr_y}" width="{w}" height="{h}" class="layer-box" />'
            svg_elements.append(rect)
        
        # 文本在最前方的矩形上
        text_x = x_offset + w/2
        text_y = center_y
        
        # 如果矩形很高且很窄，则旋转文本
        if h > 40 and w < 30:
            transform = f'transform="rotate(-90 {text_x} {text_y})"'
        else:
            transform = ""
            
        # 添加维度形状文本
        svg_elements.append(f'<text x="{text_x}" y="{text_y}" class="layer-text" {transform}>{shape}</text>')
        
        # 添加层名称文本（在底部）
        name_y = center_y + 100
        svg_elements.append(f'<text x="{layer_x_center}" y="{name_y}" class="layer-title">{name}</text>')
        
        # 添加子标题（如激活函数或通道数）
        if subtitle:
            svg_elements.append(f'<text x="{layer_x_center}" y="{name_y + 16}" class="layer-subtitle">{subtitle}</text>')
        
        # 更新x_offset为下一层做准备
        x_offset += w + (depth-1)*depth_offset + 50
        
    # 绘制连接箭头
    for i in range(len(layers) - 1):
        # 当前层的右边缘
        current_w = layers[i][3]
        current_depth = layers[i][4]
        start_x = centers[i] + current_w/2 + (current_depth-1)*2 + 2
        
        # 下一层的左边缘
        next_w = layers[i+1][3]
        next_depth = layers[i+1][4]
        end_x = centers[i+1] - next_w/2 - (next_depth-1)*2 - 10
        
        # 对于Flatten层，修正边界
        if layers[i][0] == "Flatten":
            start_x = centers[i] + current_w/2 + 2
        if layers[i+1][0] == "Flatten":
            end_x = centers[i+1] - next_w/2 - 10
            
        y = center_y
        
        # 绘制箭头直线
        svg_elements.append(f'<line x1="{start_x}" y1="{y}" x2="{end_x}" y2="{y}" class="arrow" />')
        # 绘制箭头三角形头部
        svg_elements.append(f'<polygon points="{end_x+8},{y} {end_x-2},{y-4} {end_x-2},{y+4}" class="arrow-head" />')
        
    # 组合SVG
    svg_content = f'<svg width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}">\n' + '\n'.join(svg_elements) + '\n</svg>'
    
    # 替换模板
    final_html = html_content.replace('{svg_content}', svg_content)
    
    # 写入HTML文件
    output_path = os.path.join(os.path.dirname(__file__), '1d_cnn_architecture.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_html)
    print(f"Generated successfully at: {output_path}")

if __name__ == "__main__":
    generate_cnn_html()
