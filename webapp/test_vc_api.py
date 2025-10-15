#!/usr/bin/env python3
"""
测试VC数据API端点
"""

import requests
import json
import time

def test_api_endpoints():
    """测试API端点"""
    base_url = "http://localhost:3000"
    
    print("测试VC数据API端点...")
    print("=" * 50)
    
    # 测试VC列表API
    try:
        print("1. 测试VC列表API...")
        response = requests.get(f"{base_url}/api/vc-list", timeout=5)
        if response.status_code == 200:
            vc_list = response.json()
            print(f"   ✅ 成功获取VC列表，共 {len(vc_list)} 个VC")
            for vc in vc_list:
                print(f"      - {vc['type']} (ID: {vc['id']})")
        else:
            print(f"   ❌ 失败: HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
    
    print()
    
    # 测试VC详情API
    try:
        print("2. 测试VC详情API...")
        response = requests.get(f"{base_url}/api/vc-detail/vc_001", timeout=5)
        if response.status_code == 200:
            vc_detail = response.json()
            print(f"   ✅ 成功获取VC详情: {vc_detail['type']}")
            print(f"      - 发行者: {vc_detail['issuer']}")
            print(f"      - 状态: {vc_detail['status']}")
        else:
            print(f"   ❌ 失败: HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
    
    print()
    
    # 测试合约变量API
    try:
        print("3. 测试合约变量API...")
        response = requests.get(f"{base_url}/api/contract-variables", timeout=5)
        if response.status_code == 200:
            contract_data = response.json()
            print(f"   ✅ 成功获取合约变量数据")
            for chain_name, chain_data in contract_data.items():
                print(f"      - {chain_name}: {chain_data.get('chain_name', 'Unknown')}")
        else:
            print(f"   ❌ 失败: HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
    
    print()
    
    # 测试主页
    try:
        print("4. 测试主页...")
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("   ✅ 主页访问成功")
        else:
            print(f"   ❌ 失败: HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
    
    print()
    
    # 测试VC数据页面
    try:
        print("5. 测试VC数据页面...")
        response = requests.get(f"{base_url}/vc-data", timeout=5)
        if response.status_code == 200:
            print("   ✅ VC数据页面访问成功")
        else:
            print(f"   ❌ 失败: HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
    
    print()
    print("=" * 50)
    print("测试完成！")

if __name__ == "__main__":
    print("请确保应用已启动 (python3 enhanced_app.py)")
    print("等待5秒后开始测试...")
    time.sleep(5)
    test_api_endpoints()
