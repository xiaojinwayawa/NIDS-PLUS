import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_cnn_architecture():
    fig, ax = plt.subplots(figsize=(14, 5), facecolor='white')
    ax.axis('off')
    
    # Layer definitions matching the thesis requirements:
    # "输入层、多个1D卷积层、池化层（MaxPooling）、展平层、全连接层（Dense）、输出层"
    # Format: (name, shape_text, height, width, facecolor)
    # Following the memory rule: "白底黑框、黑字"
    layers = [
        ("Input Layer", "(78, 1)", 78, 4),
        ("Conv1D Layer 1", "(78, 64)", 78, 8),
        ("MaxPooling1D", "(39, 64)", 39, 8),
        ("Conv1D Layer 2", "(39, 128)", 39, 12),
        ("MaxPooling1D", "(19, 128)", 19, 12),
        ("Flatten", "(2432)", 6, 16),
        ("Dense Layer 1", "(128)", 20, 6),
        ("Dense Layer 2", "(64)", 15, 6),
        ("Output Layer", "(Classes)", 8, 4)
    ]
    
    x_offset = 0
    max_y = 100
    
    for i, (name, shape, h, w) in enumerate(layers):
        y_offset = (max_y - h) / 2
        # White background, black border, black text
        rect = patches.Rectangle((x_offset, y_offset), w, h, 
                               linewidth=1.5, edgecolor='black', facecolor='white', zorder=2)
        ax.add_patch(rect)
        
        # Add shape text inside the box if it fits, or outside
        ax.text(x_offset + w/2, y_offset + h/2, shape, ha='center', va='center', 
                fontsize=9, color='black', rotation=90 if h > 20 else 0)
        
        # Add layer name text below the box
        ax.text(x_offset + w/2, -15, name, ha='center', va='top', 
                fontsize=10, color='black')
        
        # Add arrow to next layer
        if i < len(layers) - 1:
            next_w = layers[i+1][3]
            arrow_x_start = x_offset + w
            arrow_x_end = arrow_x_start + 8
            ax.annotate('', xy=(arrow_x_end, max_y/2), xytext=(arrow_x_start, max_y/2),
                        arrowprops=dict(arrowstyle="-|>", color='black', lw=1.5), zorder=1)
            
            x_offset += w + 8
        else:
            x_offset += w
            
    ax.set_xlim(-5, x_offset + 5)
    ax.set_ylim(-30, max_y + 10)
    
    plt.title("1D-CNN Network Architecture", fontsize=14, pad=20, color='black', fontweight='bold')
    plt.tight_layout()
    plt.savefig('1d_cnn_architecture.png', dpi=300, bbox_inches='tight')
    print("Saved 1d_cnn_architecture.png")

if __name__ == "__main__":
    draw_cnn_architecture()
