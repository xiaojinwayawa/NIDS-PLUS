#!/usr/bin/env python3
"""
诊断脚本 - 检查为什么没有报警数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis
import json
from db.db_manager import SessionLocal
from db.models import AlertModel
from config import settings

def check_redis_queue():
    """检查Redis队列中的数据"""
    print("\n=== 检查 Redis 队列 ===")
    try:
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        queue_length = r.llen("traffic_queue")
        print(f"✓ Redis连接成功")
        print(f"✓ 队列长度: {queue_length}")
        
        if queue_length > 0:
            # 查看最近的几个包
            samples = r.lrange("traffic_queue", 0, 2)
            print(f"\n最近的包样本:")
            for i, sample in enumerate(samples):
                pkt = json.loads(sample)
                print(f"  包 {i+1}: {pkt.get('src_ip')} -> {pkt.get('dst_ip')}:{pkt.get('dst_port')} [{pkt.get('protocol')}]")
                if pkt.get('tcp_flags'):
                    flags = [k for k, v in pkt['tcp_flags'].items() if v]
                    print(f"         TCP Flags: {', '.join(flags)}")
        else:
            print("⚠ 队列为空 - 可能流量捕获没有运行")
            
    except Exception as e:
        print(f"✗ Redis连接失败: {e}")

def check_database_alerts():
    """检查数据库中的报警"""
    print("\n=== 检查数据库报警 ===")
    try:
        db = SessionLocal()
        total_alerts = db.query(AlertModel).count()
        recent_alerts = db.query(AlertModel).order_by(AlertModel.id.desc()).limit(5).all()
        
        print(f"✓ 数据库连接成功")
        print(f"✓ 总报警数: {total_alerts}")
        
        if recent_alerts:
            print(f"\n最近的报警:")
            for alert in recent_alerts:
                print(f"  ID {alert.id}: {alert.attack_type}")
                print(f"    {alert.src_ip} -> {alert.dst_ip}:{alert.dst_port}")
                print(f"    置信度: {alert.confidence:.2f}, 时间: {alert.timestamp}")
        else:
            print("⚠ 数据库中没有报警记录")
            
        db.close()
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")

def check_model_files():
    """检查模型文件"""
    print("\n=== 检查模型文件 ===")
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(backend_dir)
    models_dir = os.path.join(project_root, "models")
    
    if not os.path.exists(models_dir):
        print(f"✗ 模型目录不存在: {models_dir}")
        return
    
    print(f"✓ 模型目录: {models_dir}")
    
    model_files = [f for f in os.listdir(models_dir) if f.endswith(('.joblib', '.json', '.pkl', '.h5'))]
    if model_files:
        print(f"✓ 找到 {len(model_files)} 个模型文件:")
        for f in model_files:
            size = os.path.getsize(os.path.join(models_dir, f)) / (1024*1024)
            print(f"  - {f} ({size:.2f} MB)")
    else:
        print("⚠ 没有找到模型文件")

def check_logs():
    """检查最近的日志"""
    print("\n=== 检查最近的日志 ===")
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logs_dir = os.path.join(backend_dir, "logs")
    
    if not os.path.exists(logs_dir):
        print(f"⚠ 日志目录不存在: {logs_dir}")
        return
    
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(logs_dir, f"nids_{today}.log")
    
    if os.path.exists(log_file):
        print(f"✓ 日志文件: {log_file}")
        # 读取最后50行
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            last_lines = lines[-50:] if len(lines) > 50 else lines
            
            # 查找关键信息
            errors = [l for l in last_lines if 'ERROR' in l]
            warnings = [l for l in last_lines if 'WARNING' in l or 'WARN' in l]
            alerts = [l for l in last_lines if 'Alert generated' in l or 'alert' in l.lower()]
            
            print(f"\n最近的错误 ({len(errors)}):")
            for e in errors[-5:]:
                print(f"  {e.strip()}")
            
            print(f"\n最近的警告 ({len(warnings)}):")
            for w in warnings[-5:]:
                print(f"  {w.strip()}")
            
            print(f"\n最近的报警日志 ({len(alerts)}):")
            for a in alerts[-5:]:
                print(f"  {a.strip()}")
    else:
        print(f"⚠ 今天的日志文件不存在: {log_file}")

def main():
    print("=" * 60)
    print("NIDS 报警诊断工具")
    print("=" * 60)
    
    check_redis_queue()
    check_database_alerts()
    check_model_files()
    check_logs()
    
    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)
    
    print("\n建议:")
    print("1. 如果Redis队列为空,检查系统是否在运行 (System Control)")
    print("2. 如果队列有数据但没有报警,可能是:")
    print("   - 模型置信度太低 (检查日志中的inference结果)")
    print("   - 流还没有超时完成 (等待15-30秒)")
    print("   - 模型没有正确加载 (检查日志中的模型加载信息)")
    print("3. 尝试生成测试报警: POST /api/alerts/test/generate")

if __name__ == "__main__":
    main()
