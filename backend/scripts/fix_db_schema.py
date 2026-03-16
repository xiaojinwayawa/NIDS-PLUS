#!/usr/bin/env python3
"""
修复数据库表结构 - 添加缺失的列
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text
from db.db_manager import engine, SessionLocal

def check_column_exists(table_name, column_name):
    """检查列是否存在"""
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    return any(col['name'] == column_name for col in columns)

def add_attack_type_column():
    """添加 attack_type 列"""
    print("\n=== 添加 attack_type 列 ===")
    
    if check_column_exists('alerts', 'attack_type'):
        print("✓ attack_type 列已存在,无需添加")
        return True
    
    print("正在添加 attack_type 列...")
    
    db = SessionLocal()
    try:
        # 添加列
        db.execute(text("""
            ALTER TABLE alerts 
            ADD COLUMN attack_type VARCHAR(50) NOT NULL DEFAULT 'Unknown'
        """))
        db.commit()
        print("✓ attack_type 列添加成功")
        
        # 创建索引
        try:
            db.execute(text("""
                CREATE INDEX ix_alerts_attack_type ON alerts(attack_type)
            """))
            db.commit()
            print("✓ 索引创建成功")
        except Exception as e:
            print(f"⚠ 索引创建失败(可能已存在): {e}")
        
        return True
        
    except Exception as e:
        print(f"✗ 添加列失败: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def verify_schema():
    """验证表结构"""
    print("\n=== 验证表结构 ===")
    
    required_columns = [
        'id', 'timestamp', 'src_ip', 'dst_ip', 'src_port', 'dst_port',
        'protocol', 'attack_type', 'confidence', 'model_id',
        'is_false_positive', 'marked_by', 'marked_at', 'raw_features'
    ]
    
    inspector = inspect(engine)
    columns = inspector.get_columns('alerts')
    existing_columns = {col['name'] for col in columns}
    
    all_present = True
    for col_name in required_columns:
        if col_name in existing_columns:
            print(f"  ✓ {col_name}")
        else:
            print(f"  ✗ {col_name} (缺失)")
            all_present = False
    
    return all_present

def main():
    print("=" * 60)
    print("数据库表结构修复工具")
    print("=" * 60)
    
    try:
        # 测试连接
        print("\n=== 测试数据库连接 ===")
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        print("✓ 数据库连接成功")
        
        # 检查表是否存在
        inspector = inspect(engine)
        if 'alerts' not in inspector.get_table_names():
            print("\n✗ alerts 表不存在!")
            print("请先运行: python backend/db/init_db.py")
            return
        
        # 添加缺失的列
        success = add_attack_type_column()
        
        if success:
            # 验证
            if verify_schema():
                print("\n✓ 表结构修复完成!")
            else:
                print("\n⚠ 仍有列缺失,可能需要重建表")
        else:
            print("\n✗ 修复失败")
            
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
