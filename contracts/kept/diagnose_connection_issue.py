#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断和解决跨链VC连接问题
"""

import json
import requests
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def diagnose_connection_issue():
    """诊断和解决跨链VC连接问题"""
    
    # 配置
    issuer_admin_url = "http://192.168.230.178:8080"
    holder_admin_url = "http://192.168.230.178:8081"
    
    # 正确的DID
    correct_issuer_did = "DPvobytTtKvmyeRTJZYjsg"
    correct_holder_did = "YL2HDxkVL8qMrssaZbvtfH"
    
    print("🔍 诊断跨链VC连接问题")
    print("=" * 60)
    
    # 1. 检查服务状态
    print("1️⃣ 检查服务状态...")
    
    # 检查发行者状态
    try:
        response = requests.get(f"{issuer_admin_url}/status", timeout=10)
        if response.status_code == 200:
            print("✅ 发行者ACA-Py运行正常")
        else:
            print(f"❌ 发行者ACA-Py状态异常: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接到发行者ACA-Py: {e}")
        return False
    
    # 检查持有者状态
    try:
        response = requests.get(f"{holder_admin_url}/status", timeout=10)
        if response.status_code == 200:
            print("✅ 持有者ACA-Py运行正常")
        else:
            print(f"❌ 持有者ACA-Py状态异常: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接到持有者ACA-Py: {e}")
        return False
    
    # 2. 检查DID
    print("\n2️⃣ 检查DID...")
    
    # 检查发行者DID
    try:
        response = requests.get(f"{issuer_admin_url}/wallet/did", timeout=10)
        if response.status_code == 200:
            dids = response.json().get('results', [])
            issuer_dids = [did['did'] for did in dids]
            print(f"📋 发行者DID列表: {issuer_dids}")
            
            if correct_issuer_did in issuer_dids:
                print(f"✅ 正确的发行者DID存在: {correct_issuer_did}")
            else:
                print(f"❌ 正确的发行者DID不存在: {correct_issuer_did}")
                return False
        else:
            print(f"❌ 无法获取发行者DID: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 检查发行者DID失败: {e}")
        return False
    
    # 检查持有者DID
    try:
        response = requests.get(f"{holder_admin_url}/wallet/did", timeout=10)
        if response.status_code == 200:
            dids = response.json().get('results', [])
            holder_dids = [did['did'] for did in dids]
            print(f"📋 持有者DID列表: {holder_dids}")
            
            if correct_holder_did in holder_dids:
                print(f"✅ 正确的持有者DID存在: {correct_holder_did}")
            else:
                print(f"❌ 正确的持有者DID不存在: {correct_holder_did}")
                return False
        else:
            print(f"❌ 无法获取持有者DID: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 检查持有者DID失败: {e}")
        return False
    
    # 3. 检查连接
    print("\n3️⃣ 检查连接...")
    
    # 检查发行者端连接
    try:
        response = requests.get(f"{issuer_admin_url}/connections", timeout=10)
        if response.status_code == 200:
            connections = response.json().get('results', [])
            print(f"📋 发行者端连接数量: {len(connections)}")
            
            # 查找与正确持有者DID的连接
            correct_connection = None
            for conn in connections:
                if conn.get('their_did') == correct_holder_did and conn.get('state') == 'active':
                    correct_connection = conn
                    break
            
            if correct_connection:
                print(f"✅ 找到与正确持有者DID的连接: {correct_connection['connection_id']}")
            else:
                print(f"❌ 未找到与正确持有者DID的连接")
                print("🔍 发行者端连接详情:")
                for conn in connections:
                    print(f"   - 连接ID: {conn['connection_id']}")
                    print(f"     对方DID: {conn['their_did']}")
                    print(f"     我的DID: {conn['my_did']}")
                    print(f"     状态: {conn['state']}")
                    print()
        else:
            print(f"❌ 无法获取发行者端连接: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 检查发行者端连接失败: {e}")
        return False
    
    # 检查持有者端连接
    try:
        response = requests.get(f"{holder_admin_url}/connections", timeout=10)
        if response.status_code == 200:
            connections = response.json().get('results', [])
            print(f"📋 持有者端连接数量: {len(connections)}")
            
            # 查找与正确发行者DID的连接
            correct_connection = None
            for conn in connections:
                if conn.get('their_did') == correct_issuer_did and conn.get('state') == 'active':
                    correct_connection = conn
                    break
            
            if correct_connection:
                print(f"✅ 找到与正确发行者DID的连接: {correct_connection['connection_id']}")
            else:
                print(f"❌ 未找到与正确发行者DID的连接")
                print("🔍 持有者端连接详情:")
                for conn in connections:
                    print(f"   - 连接ID: {conn['connection_id']}")
                    print(f"     对方DID: {conn['their_did']}")
                    print(f"     我的DID: {conn['my_did']}")
                    print(f"     状态: {conn['state']}")
                    print()
        else:
            print(f"❌ 无法获取持有者端连接: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 检查持有者端连接失败: {e}")
        return False
    
    # 4. 创建正确的连接
    print("\n4️⃣ 创建正确的连接...")
    
    # 发行者创建邀请
    try:
        invitation_data = {
            "auto_accept": True,
            "multi_use": False
        }
        
        response = requests.post(
            f"{issuer_admin_url}/connections/create-invitation",
            json=invitation_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            invitation = result.get('invitation')
            connection_id = result.get('connection_id')
            print(f"✅ 发行者创建邀请成功: {connection_id}")
            print(f"📋 邀请详情: {json.dumps(invitation, indent=2)}")
        else:
            print(f"❌ 发行者创建邀请失败: HTTP {response.status_code}")
            print(f"响应: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 发行者创建邀请失败: {e}")
        return False
    
    # 持有者接收邀请
    try:
        receive_data = {"invitation": invitation}
        
        response = requests.post(
            f"{holder_admin_url}/connections/receive-invitation",
            json=receive_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            holder_connection_id = result.get('connection_id')
            print(f"✅ 持有者接收邀请成功: {holder_connection_id}")
        else:
            print(f"❌ 持有者接收邀请失败: HTTP {response.status_code}")
            print(f"响应: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 持有者接收邀请失败: {e}")
        return False
    
    # 等待连接建立
    print("⏳ 等待连接建立...")
    time.sleep(10)
    
    # 检查连接状态
    try:
        response = requests.get(f"{issuer_admin_url}/connections/{connection_id}", timeout=10)
        if response.status_code == 200:
            result = response.json()
            state = result.get('state')
            print(f"📊 发行者端连接状态: {state}")
            
            if state == 'active':
                print("✅ 连接已激活")
                return True
            else:
                print(f"⚠️ 连接未激活: {state}")
                return False
        else:
            print(f"❌ 检查连接状态失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 检查连接状态失败: {e}")
        return False

if __name__ == "__main__":
    success = diagnose_connection_issue()
    if success:
        print("\n✅ 连接问题诊断和解决成功！")
    else:
        print("\n❌ 连接问题诊断和解决失败！")
