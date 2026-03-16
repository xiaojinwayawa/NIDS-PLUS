#!/usr/bin/env python3
"""
重启检测系统
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import time

API_BASE = "http://localhost:8000/api"

def get_token():
    """获取认证token"""
    try:
        response = requests.post(
            f"{API_BASE}/auth/login",
            data={
                "username": "admin",
                "password": "admin123"
            }
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            print(f"✗ 登录失败: {response.status_code}")
            return None
    except Exception as e:
        print(f"✗ 登录失败: {e}")
        return None

def stop_system(token):
    """停止系统"""
    try:
        response = requests.post(
            f"{API_BASE}/system/stop",
            headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code == 200:
            print("✓ 系统已停止")
            return True
        else:
            print(f"⚠ 停止失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠ 停止失败: {e}")
        return False

def start_system(token, mode="pcap"):
    """启动系统"""
    try:
        response = requests.post(
            f"{API_BASE}/system/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"mode": mode}
        )
        if response.status_code == 200:
            print(f"✓ 系统已启动 (模式: {mode})")
            return True
        else:
            print(f"✗ 启动失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
    except Exception as e:
        print(f"✗ 启动失败: {e}")
        return False

def get_status(token):
    """获取系统状态"""
    try:
        response = requests.get(
            f"{API_BASE}/system/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        return None

def main():
    print("=" * 60)
    print("重启检测系统")
    print("=" * 60)
    
    # 1. 获取token
    print("\n1. 登录...")
    token = get_token()
    if not token:
        print("\n✗ 无法获取认证token")
        print("   请确保后端服务正在运行")
        return
    
    print("✓ 登录成功")
    
    # 2. 检查当前状态
    print("\n2. 检查当前状态...")
    status = get_status(token)
    if status:
        print(f"   当前状态: {status.get('state', 'unknown')}")
        if status.get('state') == 'running':
            print("   系统正在运行,需要先停止")
            stop_system(token)
            time.sleep(2)
    
    # 3. 启动系统
    print("\n3. 启动系统...")
    if start_system(token, mode="pcap"):
        print("\n等待系统初始化...")
        time.sleep(3)
        
        # 4. 验证状态
        print("\n4. 验证状态...")
        status = get_status(token)
        if status and status.get('state') == 'running':
            print("✓ 系统运行正常")
            print(f"\n系统信息:")
            print(f"  状态: {status.get('state')}")
            print(f"  模式: {status.get('mode')}")
            print(f"  模型: {status.get('current_model')}")
            
            print("\n✓ 重启完成!")
            print("\n现在系统会对所有流量生成报警(阈值已降低到0.0001)")
            print("等待15-30秒让流完成,然后检查报警。")
        else:
            print("⚠ 系统状态异常")
    else:
        print("\n✗ 启动失败")

if __name__ == "__main__":
    main()
