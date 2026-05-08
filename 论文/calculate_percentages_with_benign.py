
# CIC-IDS2017数据（包含正常流量）
data = [
    ('BENIGN', 97718 + 127537 + 189067 + 529918 + 288566 + 168186 + 432074 + 440031),
    ('DDoS', 128027),
    ('PortScan', 158930),
    ('Bot', 1966),
    ('Infiltration', 36),
    ('Web Attack - Brute Force', 1507),
    ('Web Attack - Sql Injection', 21),
    ('Web Attack - XSS', 652),
    ('FTP-Patator', 7938),
    ('SSH-Patator', 5897),
    ('DoS GoldenEye', 10293),
    ('DoS Hulk', 231072),
    ('DoS Slowhttptest', 5499),
    ('DoS slowloris', 5796),
    ('Heartbleed', 11)
]

total = sum(count for label, count in data)

print('类别\t样本数量\t占比')
print('-' * 50)
for label, count in data:
    percentage = (count / total) * 100
    print(f'{label}\t{count}\t{percentage:.2f}%')

print(f'\n总数: {total}')
