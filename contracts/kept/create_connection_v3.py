#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用完整字段创建跨链VC连接
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

def create_connection_v3():
    """使用完整字段创建跨链VC连接"""
    
    # 配置
    issuer_admin_url = "http://192.168.230.178:8080"
    holder_admin_url = "http://192.168.230.178:8081"
    
    # 正确的DID
    correct_issuer_did = "DPvobytTtKvmyeRTJZYjsg"
    correct_holder_did = "YL2HDxkVL8qMrssaZbvtfH"
    
    print("🔗 使用完整字段创建跨链VC连接")
    print("=" * 50)
    print(f"发行者DID: {correct_issuer_did}")
    print(f"持有者DID: {correct_holder_did}")
    
    # 1. 获取发行者DID信息
    print("\n🔍 获取发行者DID信息...")
    
    try:
        response = requests.get(f"{issuer_admin_url}/wallet/did", timeout=10)
        if response.status_code == 200:
            dids = response.json().get('results', [])
            issuer_did_info = None
            for did in dids:
                if did['did'] == correct_issuer_did:
                    issuer_did_info = did
                    break
            
            if issuer_did_info:
                print(f"✅ 发行者DID信息: {issuer_did_info}")
            else:
                print(f"❌ 未找到发行者DID信息: {correct_issuer_did}")
                return None
        else:
            print(f"❌ 无法获取发行者DID信息: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ 获取发行者DID信息失败: {e}")
        return None
    
    # 2. 创建连接邀请
    print("\n🔗 创建连接邀请...")
    
    try:
        # 使用不同的邀请格式
        invitation_data = {
            "auto_accept": True,
            "multi_use": False,
            "public": True
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
            print(f"📋 邀请详情:")
            print(f"   ID: {invitation.get('@id')}")
            print(f"   类型: {invitation.get('@type')}")
            print(f"   标签: {invitation.get('label')}")
            print(f"   服务端点: {invitation.get('serviceEndpoint')}")
            print(f"   接收者密钥: {invitation.get('recipientKeys')}")
            print(f"   DID: {invitation.get('did')}")
            
            # 检查邀请是否包含所有必需字段
            required_fields = ['did', 'recipientKeys', 'serviceEndpoint']
            missing_fields = []
            for field in required_fields:
                if field not in invitation or invitation[field] is None:
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"⚠️ 邀请缺少必需字段: {missing_fields}")
                
                # 尝试手动添加缺失字段
                if 'did' not in invitation or invitation['did'] is None:
                    invitation['did'] = correct_issuer_did
                    print(f"✅ 手动添加DID: {correct_issuer_did}")
                
                if 'recipientKeys' not in invitation or not invitation['recipientKeys']:
                    invitation['recipientKeys'] = [issuer_did_info['verkey']]
                    print(f"✅ 手动添加接收者密钥: {issuer_did_info['verkey']}")
                
                if 'serviceEndpoint' not in invitation or not invitation['serviceEndpoint']:
                    invitation['serviceEndpoint'] = f"http://192.168.230.178:8000"
                    print(f"✅ 手动添加服务端点: http://192.168.230.178:8000")
                
                print(f"📋 修复后的邀请:")
                print(f"   ID: {invitation.get('@id')}")
                print(f"   类型: {invitation.get('@type')}")
                print(f"   标签: {invitation.get('label')}")
                print(f"   服务端点: {invitation.get('serviceEndpoint')}")
                print(f"   接收者密钥: {invitation.get('recipientKeys')}")
                print(f"   DID: {invitation.get('did')}")
            else:
                print("✅ 邀请包含所有必需字段")
        else:
            print(f"❌ 发行者创建邀请失败: HTTP {response.status_code}")
            print(f"响应: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 发行者创建邀请失败: {e}")
        return None
    
    # 3. 持有者接收邀请
    print("\n📨 持有者接收邀请...")
    
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
            return None
    except Exception as e:
        print(f"❌ 持有者接收邀请失败: {e}")
        return None
    
    # 4. 等待连接建立
    print("⏳ 等待连接建立...")
    time.sleep(15)
    
    # 5. 检查连接状态
    print("🔍 检查连接状态...")
    
    try:
        response = requests.get(f"{issuer_admin_url}/connections/{connection_id}", timeout=10)
        if response.status_code == 200:
            result = response.json()
            state = result.get('state')
            their_did = result.get('their_did')
            my_did = result.get('my_did')
            print(f"📊 发行者端连接状态: {state}")
            print(f"   我的DID: {my_did}")
            print(f"   对方DID: {their_did}")
            
            if state == 'active':
                print("✅ 连接已激活")
                return connection_id
            else:
                print(f"⚠️ 连接未激活: {state}")
                return None
        else:
            print(f"❌ 检查连接状态失败: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ 检查连接状态失败: {e}")
        return None

def test_vc_generation(connection_id: str):
    """测试VC生成"""
    
    # 配置
    issuer_admin_url = "http://192.168.230.178:8080"
    holder_admin_url = "http://192.168.230.178:8081"
    cred_def_id = "DPvobytTtKvmyeRTJZYjsg:3:CL:11:cross-chain-lock"
    
    print(f"\n📤 测试VC生成 (连接: {connection_id})...")
    
    # 构建凭证属性
    cross_chain_data = {
        "source_chain": "chain_a",
        "target_chain": "chain_b",
        "amount": "100",
        "token_address": "0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af",
        "lock_id": "test_connection_lock_888999",
        "transaction_hash": "0x888999aaa111222",
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
        "comment": "Test Connection Cross-Chain Lock Credential",
        "credential_preview": {
            "@type": "issue-credential/1.0/credential-preview",
            "attributes": attributes
        }
    }
    
    print(f"📋 凭证属性:")
    for attr in attributes:
        print(f"   {attr['name']}: {attr['value']}")
    
    try:
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
                    return True
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
    except Exception as e:
        print(f"❌ 测试VC生成失败: {e}")
        return False

if __name__ == "__main__":
    # 创建连接
    connection_id = create_connection_v3()
    
    if connection_id:
        # 测试VC生成
        success = test_vc_generation(connection_id)
        if success:
            print("\n✅ 连接创建和VC测试成功！")
        else:
            print("\n⚠️ 连接创建成功，但VC测试失败！")
    else:
        print("\n❌ 连接创建失败！")
