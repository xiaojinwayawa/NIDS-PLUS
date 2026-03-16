#!/usr/bin/env python3
"""
检查数据库表结构
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text
from db.db_manager import engine, SessionLocal
from db.models import AlertModel, UserModel, ModelModel

def check_table_exists(table_name):
    """检查表是否存在"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()

def get_table_columns(table_name):
    """获取表的列信息"""
    inspector = inspect(engine)
    if not check_table_exists(table_name):
        return None
    return inspector.get_columns(table_name)

def check_alerts_table():
    """检查alerts表结构"""
    print("\n=== 检查 alerts 表 ===")
    
    if not check_table_exists("alerts"):
        print("✗ alerts 表不存在!")
        print("\n建议: 运行数据库初始化脚本")
        print("  python backend/db/init_db.py")
        return False
    
    print("✓ alerts 表存在")
    
    # 获取列信息
    columns = get_table_columns("alerts")
    print(f"\n表结构 ({len(columns)} 列):")
    
    required_columns = {
        'id': 'INTEGER',
        'timestamp': 'DATETIME',
        'src_ip': 'VARCHAR',
        'dst_ip': 'VARCHAR',
        'src_port': 'INTEGER',
        'dst_port': 'INTEGER',
        'protocol': 'VARCHAR',
        'attack_type': 'VARCHAR',  # 关键列
        'confidence': 'FLOAT',
        'model_id': 'INTEGER',
        'is_false_positive': 'BOOLEAN',
        'marked_by': 'INTEGER',
        'marked_at': 'DATETIME',
        'raw_features': 'JSON'
    }
    
    existing_columns = {}
    for col in columns:
        col_name = col['name']
        col_type = str(col['type']).upper()
        existing_columns[col_name] = col_type
        
        # 检查是否是必需列
        if col_name in required_columns:
            status = "✓"
        else:
            status = "?"
        
        nullable = "NULL" if col.get('nullable', True) else "NOT NULL"
        print(f"  {status} {col_name:20s} {col_type:15s} {nullable}")
    
    # 检查缺失的列
    missing_columns = set(required_columns.keys()) - set(existing_columns.keys())
    if missing_columns:
        print(f"\n✗ 缺失的列: {', '.join(missing_columns)}")
        print("\n这是问题所在! 需要添加缺失的列或重建表。")
        return False
    
    # 特别检查 attack_type 列
    if 'attack_type' not in existing_columns:
        print("\n✗ 关键问题: attack_type 列不存在!")
        print("   这会导致报警无法保存到数据库。")
        return False
    else:
        print(f"\n✓ attack_type 列存在: {existing_columns['attack_type']}")
    
    return True

def check_sample_data():
    """检查是否有示例数据"""
    print("\n=== 检查数据 ===")
    
    if not check_table_exists("alerts"):
        return
    
    db = SessionLocal()
    try:
        count = db.execute(text("SELECT COUNT(*) FROM alerts")).scalar()
        print(f"✓ alerts 表中有 {count} 条记录")
        
        if count > 0:
            # 查看最近的记录
            result = db.execute(text("""
                SELECT id, timestamp, src_ip, dst_ip, attack_type, confidence 
                FROM alerts 
                ORDER BY id DESC 
                LIMIT 3
            """))
            
            print("\n最近的记录:")
            for row in result:
                print(f"  ID {row[0]}: {row[4]} ({row[5]:.2f}) - {row[2]} -> {row[3]}")
    except Exception as e:
        print(f"✗ 查询数据失败: {e}")
    finally:
        db.close()

def suggest_fix():
    """提供修复建议"""
    print("\n" + "=" * 60)
    print("修复建议")
    print("=" * 60)
    
    if not check_table_exists("alerts"):
        print("\n方案 1: 初始化数据库")
        print("  python backend/db/init_db.py")
        
        print("\n方案 2: 手动创建表")
        print("  使用 SQLAlchemy 的 create_all()")
    else:
        columns = get_table_columns("alerts")
        existing_columns = {col['name'] for col in columns}
        
        if 'attack_type' not in existing_columns:
            print("\n方案 1: 添加缺失的列 (推荐)")
            print("  运行以下SQL:")
            print("  ALTER TABLE alerts ADD COLUMN attack_type VARCHAR(50) NOT NULL DEFAULT 'Unknown';")
            
            print("\n方案 2: 重建表 (会丢失数据)")
            print("  1. 备份现有数据")
            print("  2. DROP TABLE alerts;")
            print("  3. 运行 python backend/db/init_db.py")
            
            print("\n方案 3: 使用迁移脚本")
            print("  创建 Alembic 迁移脚本来更新表结构")

def main():
    print("=" * 60)
    print("数据库表结构检查工具")
    print("=" * 60)
    
    try:
        # 测试数据库连接
        print("\n=== 测试数据库连接 ===")
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        print("✓ 数据库连接成功")
        
        # 检查表结构
        is_valid = check_alerts_table()
        
        # 检查数据
        check_sample_data()
        
        # 提供修复建议
        if not is_valid:
            suggest_fix()
        else:
            print("\n✓ 数据库表结构正常!")
        
    except Exception as e:
        print(f"\n✗ 数据库连接失败: {e}")
        print("\n请检查:")
        print("  1. MySQL 服务是否运行")
        print("  2. backend/config.py 中的数据库配置")
        print("  3. 数据库用户权限")

if __name__ == "__main__":
    main()
