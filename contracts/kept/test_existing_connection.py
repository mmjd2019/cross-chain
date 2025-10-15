#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试现有连接的VC生成
"""

import json
import requests
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_existing_connection():
    """测试使用现有连接生成VC"""
    
    # 配置
    issuer_admin_url = "http://192.168.230.178:8080"
    holder_admin_url = "http://192.168.230.178:8081"
    cred_def_id = "DPvobytTtKvmyeRTJZYjsg:3:CL:11:cross-chain-lock"
    
    print("🔐 测试现有连接的VC生成")
    print("=" * 50)
    
    # 1. 检查现有连接
    print("🔍 检查现有连接...")
    response = requests.get(f"{issuer_admin_url}/connections", timeout=10)
    if response.status_code == 200:
        connections = response.json().get('results', [])
        active_connections = [conn for conn in connections if conn.get('state') == 'active']
        
        if active_connections:
            connection = active_connections[0]
            connection_id = connection['connection_id']
            print(f"✅ 找到活跃连接: {connection_id}")
            print(f"   对方DID: {connection.get('their_did')}")
            print(f"   我的DID: {connection.get('my_did')}")
        else:
            print("❌ 没有找到活跃连接")
            return False
    else:
        print(f"❌ 获取连接失败: HTTP {response.status_code}")
        return False
    
    # 2. 生成跨链VC
    print("\n📤 生成跨链VC...")
    
    # 构建凭证属性
    cross_chain_data = {
        "source_chain": "chain_a",
        "target_chain": "chain_b",
        "amount": "100",
        "token_address": "0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af",
        "lock_id": "test_lock_123456",
        "transaction_hash": "0xabcdef1234567890",
        "expiry": (datetime.now() + timedelta(hours=24)).isoformat(),
        "user_address": "0x1234567890123456789012345678901234567890"
    }
    
    attributes = [
        {"name": "sourceChain", "value": cross_chain_data.get('source_chain', '')},
        {"name": "targetChain", "value": cross_chain_data.get('target_chain', '')},
        {"name": "amount", "value": str(cross_chain_data.get('amount', 0))},
        {"name": "tokenAddress", "value": cross_chain_data.get('token_address', '')},
        {"name": "lockId", "value": cross_chain_data.get('lock_id', '')},
        {"name": "transactionHash", "value": cross_chain_data.get('transaction_hash', '')},
        {"name": "expiry", "value": cross_chain_data.get('expiry', '')}
    ]
    
    # 发送凭证提供
    offer_data = {
        "connection_id": connection_id,
        "cred_def_id": cred_def_id,
        "comment": "Cross-Chain Lock Credential",
        "credential_preview": {
            "@type": "issue-credential/1.0/credential-preview",
            "attributes": attributes
        }
    }
    
    print(f"📋 凭证属性:")
    for attr in attributes:
        print(f"   {attr['name']}: {attr['value']}")
    
    response = requests.post(
        f"{issuer_admin_url}/issue-credential/send-offer",
        json=offer_data,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )
    
    if response.status_code in [200, 201]:
        result = response.json()
        cred_ex_id = result.get('credential_exchange_id')
        print(f"✅ 凭证提供发送成功: {cred_ex_id}")
        
        # 等待一下让持有者处理
        print("⏳ 等待持有者处理...")
        time.sleep(3)
        
        # 检查凭证状态
        response = requests.get(f"{issuer_admin_url}/issue-credential/{cred_ex_id}", timeout=10)
        if response.status_code == 200:
            result = response.json()
            state = result.get('state')
            print(f"📊 凭证状态: {state}")
            
            if state == 'credential_acked':
                print("🎉 跨链VC生成成功！")
                return True
            else:
                print(f"⚠️ 凭证状态异常: {state}")
                return False
        else:
            print(f"❌ 检查凭证状态失败: HTTP {response.status_code}")
            return False
    else:
        print(f"❌ 发送凭证提供失败: HTTP {response.status_code}")
        print(f"响应: {response.text}")
        return False

if __name__ == "__main__":
    success = test_existing_connection()
    if success:
        print("\n✅ 测试成功！")
    else:
        print("\n❌ 测试失败！")
