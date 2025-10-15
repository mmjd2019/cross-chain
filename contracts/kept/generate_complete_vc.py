#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成完整的跨链VC，包括完整的流程
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

def generate_complete_vc():
    """生成完整的跨链VC"""
    
    # 配置
    issuer_admin_url = "http://192.168.230.178:8080"
    holder_admin_url = "http://192.168.230.178:8081"
    cred_def_id = "DPvobytTtKvmyeRTJZYjsg:3:CL:11:cross-chain-lock"
    
    print("🔐 生成完整的跨链VC")
    print("=" * 50)
    
    # 1. 检查连接
    print("🔍 检查连接状态...")
    
    # 检查发行者连接
    response = requests.get(f"{issuer_admin_url}/connections", timeout=10)
    if response.status_code == 200:
        connections = response.json().get('results', [])
        active_connections = [conn for conn in connections if conn.get('state') == 'active']
        
        if active_connections:
            connection = active_connections[0]
            connection_id = connection['connection_id']
            print(f"✅ 找到活跃连接: {connection_id}")
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
        "lock_id": "complete_lock_789012",
        "transaction_hash": "0x1234567890abcdef",
        "expiry": (datetime.now() + timedelta(hours=24)).isoformat()
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
        "comment": "Complete Cross-Chain Lock Credential",
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
        
        # 等待持有者处理
        print("⏳ 等待持有者处理...")
        time.sleep(5)
        
        # 检查持有者端是否接收到
        response = requests.get(f"{holder_admin_url}/issue-credential/records", timeout=10)
        if response.status_code == 200:
            holder_records = response.json().get('results', [])
            holder_vc_record = None
            for record in holder_records:
                if record.get('credential_exchange_id') == cred_ex_id:
                    holder_vc_record = record
                    break
            
            if holder_vc_record:
                print(f"✅ 持有者接收到凭证提供: {holder_vc_record.get('state')}")
                
                # 如果持有者状态是offer_received，则请求凭证
                if holder_vc_record.get('state') == 'offer_received':
                    print("📨 持有者请求凭证...")
                    response = requests.post(
                        f"{holder_admin_url}/issue-credential/send-request",
                        json={"credential_exchange_id": cred_ex_id},
                        headers={'Content-Type': 'application/json'},
                        timeout=30
                    )
                    
                    if response.status_code in [200, 201]:
                        print("✅ 持有者请求凭证成功")
                    else:
                        print(f"❌ 持有者请求凭证失败: HTTP {response.status_code}")
                        return False
                
                # 等待一下
                time.sleep(3)
                
                # 发行者颁发凭证
                print("📜 发行者颁发凭证...")
                response = requests.post(
                    f"{issuer_admin_url}/issue-credential/issue",
                    json={"credential_exchange_id": cred_ex_id},
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                if response.status_code in [200, 201]:
                    print("✅ 发行者颁发凭证成功")
                else:
                    print(f"❌ 发行者颁发凭证失败: HTTP {response.status_code}")
                    return False
                
                # 等待最终完成
                print("⏳ 等待VC完成...")
                time.sleep(5)
                
                # 检查最终状态
                print("🔍 检查最终状态...")
                response = requests.get(f"{issuer_admin_url}/issue-credential/records", timeout=10)
                if response.status_code == 200:
                    records = response.json().get('results', [])
                    vc_record = None
                    for record in records:
                        if record.get('credential_exchange_id') == cred_ex_id:
                            vc_record = record
                            break
                    
                    if vc_record:
                        state = vc_record.get('state')
                        print(f"📊 最终状态: {state}")
                        
                        if state == 'credential_acked':
                            print("🎉 跨链VC生成完成！")
                            
                            # 保存结果
                            result = {
                                "success": True,
                                "credential_exchange_id": cred_ex_id,
                                "schema_id": "DPvobytTtKvmyeRTJZYjsg:2:CrossChainLockCredential:1.0",
                                "cred_def_id": cred_def_id,
                                "connection_id": connection_id,
                                "state": state,
                                "cross_chain_data": cross_chain_data,
                                "timestamp": datetime.now().isoformat()
                            }
                            
                            with open('complete_vc_result.json', 'w') as f:
                                json.dump(result, f, indent=2)
                            
                            print(f"📁 结果已保存到: complete_vc_result.json")
                            return True
                        else:
                            print(f"⚠️ 最终状态异常: {state}")
                            return False
                    else:
                        print("❌ 未找到最终的VC记录")
                        return False
                else:
                    print(f"❌ 检查最终状态失败: HTTP {response.status_code}")
                    return False
            else:
                print("❌ 持有者端未接收到凭证提供")
                return False
        else:
            print(f"❌ 检查持有者记录失败: HTTP {response.status_code}")
            return False
    else:
        print(f"❌ 发送凭证提供失败: HTTP {response.status_code}")
        print(f"响应: {response.text}")
        return False

if __name__ == "__main__":
    success = generate_complete_vc()
    if success:
        print("\n✅ 完整跨链VC生成成功！")
    else:
        print("\n❌ 完整跨链VC生成失败！")
