#!/usr/bin/env python
"""快速检查报警和队列状态"""
import sys
sys.path.insert(0, '.')

from db.db_manager import DatabaseManager
from datetime import datetime, timedelta
import redis

try:
    # 数据库连接
    db = DatabaseManager()
    
    # 查询总报警数
    result = db.execute_query('SELECT COUNT(*) as count FROM alerts')
    total_alerts = result[0][0] if result else 0
    print(f'📊 数据库总报警数: {total_alerts}')
    
    # 查询最后1小时的报警
    one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
    result = db.execute_query(
        f'SELECT id, timestamp, src_ip, dst_ip, alert_type, confidence FROM alerts WHERE timestamp > "{one_hour_ago}" ORDER BY timestamp DESC LIMIT 10'
    )
    
    print(f'\n📋 最近1小时的报警 ({len(result)} 条):')
    for row in result:
        print(f'  {row}')
    
    # Redis队列状态
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    queue_size = r.llen('traffic_queue')
    print(f'\n📈 Redis traffic_queue大小: {queue_size}')
    
    if queue_size > 0:
        # 查看队列中的第一个元素（不弹出）
        first_item = r.lrange('traffic_queue', 0, 0)
        print(f'  队列不为空，有待处理的流')
    
    print("\n✅ 诊断完成")
    
except Exception as e:
    print(f'❌ 错误: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
