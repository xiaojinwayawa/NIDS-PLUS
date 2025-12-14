"""Test configuration and database connection"""
import sys
from config import settings
import pymysql
import redis

def test_config():
    """Test configuration loading"""
    print("=== 配置测试 ===")
    print(f"项目名称: {settings.PROJECT_NAME}")
    print(f"API前缀: {settings.API_V1_PREFIX}")
    print(f"MySQL主机: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}")
    print(f"Redis主机: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    print(f"流量源模式: {settings.TRAFFIC_SOURCE_MODE}")
    print(f"批量大小: {settings.BATCH_SIZE}")
    print()

def test_mysql():
    """Test MySQL connection"""
    print("=== MySQL连接测试 ===")
    try:
        conn = pymysql.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DATABASE
        )
        print("✓ MySQL连接成功")
        
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"✓ 数据库表数量: {len(tables)}")
            for table in tables:
                print(f"  - {table[0]}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"✗ MySQL连接失败: {e}")
        return False

def test_redis():
    """Test Redis connection"""
    print("\n=== Redis连接测试 ===")
    try:
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB
        )
        r.ping()
        print("✓ Redis连接成功")
        
        # Test set/get
        r.set('test_key', 'test_value')
        value = r.get('test_key')
        r.delete('test_key')
        print(f"✓ Redis读写测试成功")
        return True
    except Exception as e:
        print(f"✗ Redis连接失败: {e}")
        return False

if __name__ == "__main__":
    test_config()
    mysql_ok = test_mysql()
    redis_ok = test_redis()
    
    print("\n=== 测试总结 ===")
    if mysql_ok and redis_ok:
        print("✓ 所有配置测试通过！")
        sys.exit(0)
    else:
        print("✗ 部分配置测试失败，请检查配置")
        sys.exit(1)
