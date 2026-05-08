
import re

with open('毕业论文直接复制版本.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 匹配 \tag{xxx} 格式，替换为 \tag{(xxx)}
fixed_content = re.sub(r'\\tag\{([^}]+)\}', r'\\tag{(\1)}', content)

with open('毕业论文直接复制版本.md', 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print('毕业论文直接复制版本.md 的公式标号修改完成！')
