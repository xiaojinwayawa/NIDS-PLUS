
import pandas as pd

# CIC-IDS2017数据
data = {
    '攻击类型': [
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
    ],
    '样本数量': [
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
}

# 创建DataFrame
df = pd.DataFrame(data)

# 保存到Excel
df.to_excel('cic_ids2017_data.xlsx', index=False, sheet_name='CIC-IDS2017数据')

print('Excel文件已生成：cic_ids2017_data.xlsx')
print('请在Excel中打开该文件，选中两列数据后插入饼图')
