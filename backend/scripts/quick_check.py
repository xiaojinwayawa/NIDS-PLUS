#!/usr/bin/env python3
"""
快速检查 - 诊断报警问题的最常见原因
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_database_schema():
    """检查数据库表结构"""
    print("1. 检查数据库表结构...")
    try:
        from sqlalchemy import inspect
        from db.db_manager import engine
        
        inspector = inspect(engine)
        
        # 检查表是否存在
        if 'alerts' not in inspector.get_table_names():
            print("   ✗ alerts 表不存在!")
            print("   → 运行: python backend/db/init_db.py")
            return False
        
        # 检查 attack_type 列
        columns = inspector.get_columns('alerts')
        column_names = [col['name'] for col in columns]
        
        if 'attack_type' not in column_names:
            print("   ✗ attack_type 列不存在! (这是问题所在)")
            print("   → 运行: python backend/scripts/fix_db_schema.py")
            return False
        
        print("   ✓ 数据库表结构正常")
        return True
        
    except Exception as e:
        print(f"   ✗ 检查失败: {e}")
        return False

def check_redis():
    """检查Redis连接和队列"""
    print("\n2. 检查Redis队列...")
    try:
        import redis
        from config import settings
        
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        
        queue_len = r.llen("traffic_queue")
        print(f"   ✓ Redis连接正常, 队列长度: {queue_len}")
        
        if queue_len == 0:
            print("   ⚠ 队列为空 - 系统可能没有运行")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ✗ Redis连接失败: {e}")
        return False

def check_model_files():
    """检查模型文件"""
    print("\n3. 检查模型文件...")
    try:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_root = os.path.dirname(backend_dir)
        models_dir = os.path.join(project_root, "models")
        
        if not os.path.exists(models_dir):
            print(f"   ✗ 模型目录不存在: {models_dir}")
            return False
        
        model_files = [f for f in os.listdir(models_dir) 
                      if f.endswith(('.joblib', '.json', '.pkl'))]
        
        if not model_files:
            print("   ✗ 没有找到模型文件")
            return False
        
        print(f"   ✓ 找到 {len(model_files)} 个模型文件")
        return True
        
    except Exception as e:
        print(f"   ✗ 检查失败: {e}")
        return False

def check_alerts_in_db():
    """检查数据库中的报警"""
    print("\n4. 检查数据库中的报警...")
    try:
        from db.db_manager import SessionLocal
        from db.models import AlertModel
        
        db = SessionLocal()
        count = db.query(AlertModel).count()
        db.close()
        
        print(f"   ✓ 数据库中有 {count} 条报警记录")
        
        if count == 0:
            print("   ⚠ 没有报警记录")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ✗ 查询失败: {e}")
        return False

def main():
    print("=" * 60)
    print("快速诊断 - 报警问题检查")
    print("=" * 60)
    print()
    
    results = []
    
    # 按优先级检查
    results.append(("数据库表结构", check_database_schema()))
    results.append(("Redis队列", check_redis()))
    results.append(("模型文件", check_model_files()))
    results.append(("数据库报警", check_alerts_in_db()))
    
    print("\n" + "=" * 60)
    print("诊断结果")
    print("=" * 60)
    
    all_ok = all(r[1] for r in results)
    
    for name, ok in results:
        status = "✓" if ok else "✗"
        print(f"{status} {name}")
    
    print()
    
    if not results[0][1]:  # 数据库表结构问题
        print("⚠ 关键问题: 数据库表结构不正确")
        print("\n立即修复:")
        print("  python backend/scripts/fix_db_schema.py")
        print("\n或重新初始化:")
        print("  python backend/db/init_db.py")
        
    elif not results[1][1]:  # Redis问题
        print("⚠ 系统可能没有运行")
        print("\n请检查:")
        print("  1. Redis 服务是否运行")
        print("  2. 系统是否已启动 (System Control)")
        
    elif not results[2][1]:  # 模型文件问题
        print("⚠ 模型文件缺失")
        print("\n请检查:")
        print("  1. models/ 目录是否存在")
        print("  2. 是否已训练或下载模型")
        
    elif not results[3][1]:  # 没有报警
        print("⚠ 数据库中没有报警记录")
        print("\n可能原因:")
        print("  1. 流量还没有触发报警 (等待15-30秒)")
        print("  2. 模型置信度太低")
        print("  3. 检测阈值太高")
        print("\n尝试生成测试报警:")
        print("  POST /api/alerts/test/generate")
        
    else:
        print("✓ 所有检查通过!")
        print("\n如果仍然没有报警,请:")
        print("  1. 查看日志: backend/logs/nids_*.log")
        print("  2. 运行详细诊断: python backend/scripts/diagnose_alerts.py")
        print("  3. 实时监控: python backend/scripts/debug_detection.py")

if __name__ == "__main__":
    main()
