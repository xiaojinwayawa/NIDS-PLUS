#!/usr/bin/env python3
"""
数据库初始化脚本
创建所有表并插入初始数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from db.db_manager import engine, Base, SessionLocal
from db.models import UserModel, AlertModel, ModelModel, ModelMetricModel, DatasetModel
from logging_config import app_logger as logger

def create_tables_from_models():
    """使用 SQLAlchemy 模型创建表"""
    print("\n=== 使用 SQLAlchemy 创建表 ===")
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ 所有表创建成功")
        return True
    except Exception as e:
        print(f"✗ 创建表失败: {e}")
        return False

def create_tables_from_sql():
    """使用 SQL 文件创建表"""
    print("\n=== 使用 SQL 文件创建表 ===")
    
    sql_file = os.path.join(os.path.dirname(__file__), "schema.sql")
    if not os.path.exists(sql_file):
        print(f"✗ SQL 文件不存在: {sql_file}")
        return False
    
    try:
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 分割SQL语句
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        
        db = SessionLocal()
        try:
            for i, statement in enumerate(statements, 1):
                if statement:
                    try:
                        db.execute(text(statement))
                        db.commit()
                        # 只显示CREATE和INSERT语句
                        if statement.upper().startswith(('CREATE', 'INSERT')):
                            first_line = statement.split('\n')[0][:60]
                            print(f"  ✓ 执行语句 {i}: {first_line}...")
                    except Exception as e:
                        # 忽略"表已存在"的错误
                        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                            print(f"  ⚠ 语句 {i} 已存在,跳过")
                        else:
                            print(f"  ✗ 语句 {i} 失败: {e}")
                            db.rollback()
            
            print("✓ SQL 文件执行完成")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"✗ 读取 SQL 文件失败: {e}")
        return False

def verify_tables():
    """验证表是否创建成功"""
    print("\n=== 验证表结构 ===")
    
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    required_tables = ['users', 'models', 'alerts', 'model_metrics', 'datasets']
    
    all_exist = True
    for table in required_tables:
        if table in tables:
            # 获取列数
            columns = inspector.get_columns(table)
            print(f"  ✓ {table:20s} ({len(columns)} 列)")
            
            # 特别检查 alerts 表的 attack_type 列
            if table == 'alerts':
                has_attack_type = any(col['name'] == 'attack_type' for col in columns)
                if has_attack_type:
                    print(f"    ✓ attack_type 列存在")
                else:
                    print(f"    ✗ attack_type 列缺失!")
                    all_exist = False
        else:
            print(f"  ✗ {table:20s} (不存在)")
            all_exist = False
    
    return all_exist

def check_initial_data():
    """检查初始数据"""
    print("\n=== 检查初始数据 ===")
    
    db = SessionLocal()
    try:
        # 检查用户
        user_count = db.query(UserModel).count()
        print(f"  用户数: {user_count}")
        if user_count > 0:
            admin = db.query(UserModel).filter(UserModel.username == 'admin').first()
            if admin:
                print(f"    ✓ 管理员账户存在: {admin.username}")
        
        # 检查模型
        model_count = db.query(ModelModel).count()
        print(f"  模型数: {model_count}")
        
        # 检查报警
        alert_count = db.query(AlertModel).count()
        print(f"  报警数: {alert_count}")
        
    except Exception as e:
        print(f"  ✗ 查询失败: {e}")
    finally:
        db.close()

def main():
    print("=" * 60)
    print("NIDS 数据库初始化")
    print("=" * 60)
    
    try:
        # 测试连接
        print("\n=== 测试数据库连接 ===")
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        print("✓ 数据库连接成功")
        
        # 选择创建方式
        print("\n选择初始化方式:")
        print("  1. 使用 SQLAlchemy 模型 (推荐)")
        print("  2. 使用 SQL 文件")
        print("  3. 两者都用 (最安全)")
        
        choice = input("\n请选择 (1/2/3) [默认: 3]: ").strip() or "3"
        
        success = False
        if choice in ["1", "3"]:
            success = create_tables_from_models()
        
        if choice in ["2", "3"]:
            success = create_tables_from_sql() or success
        
        if success:
            # 验证
            if verify_tables():
                print("\n✓ 数据库初始化成功!")
                check_initial_data()
            else:
                print("\n⚠ 部分表创建失败")
        else:
            print("\n✗ 数据库初始化失败")
            
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
