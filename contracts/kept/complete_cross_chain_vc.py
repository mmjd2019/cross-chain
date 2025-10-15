#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完成跨链VC流程
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

def complete_cross_chain_vc():
    """完成跨链VC流程"""
    
    # 配置
    issuer_admin_url = "http://192.168.230.178:8080"
    holder_admin_url = "http://192.168.230.178:8081"
    
    print("🚀 完成跨链VC流程")
    print("=" * 50)
    
    # 1. 获取持有者端的凭证记录
    print("🔍 获取持有者端的凭证记录...")
    
    try:
        response = requests.get(f"{holder_admin_url}/issue-credential/records", timeout=10)
        if response.status_code == 200:
            records = response.json().get('results', [])
            print(f"✅ 找到 {len(records)} 个凭证记录")
            
            # 找到跨链凭证记录
            cross_chain_record = None
            for record in records:
                if (record.get('state') == 'offer_received' and 
                    record.get('credential_definition_id') == 'DPvobytTtKvmyeRTJZYjsg:3:CL:11:cross-chain-lock'):
                    cross_chain_record = record
                    break
            
            if cross_chain_record:
                cred_ex_id = cross_chain_record['credential_exchange_id']
                print(f"✅ 找到跨链凭证记录: {cred_ex_id}")
                print(f"   状态: {cross_chain_record.get('state')}")
                print(f"   Schema: {cross_chain_record.get('schema_id')}")
                print(f"   凭证定义: {cross_chain_record.get('credential_definition_id')}")
            else:
                print("❌ 未找到跨链凭证记录")
                return False
        else:
            print(f"❌ 获取持有者凭证记录失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 获取持有者凭证记录失败: {e}")
        return False
    
    # 2. 持有者发送凭证请求
    print(f"\n📤 持有者发送凭证请求...")
    
    try:
        # 使用正确的API端点
        request_data = {
            "credential_exchange_id": cred_ex_id
        }
        
        response = requests.post(
            f"{holder_admin_url}/issue-credential/send-request",
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            print("✅ 持有者凭证请求发送成功")
        else:
            print(f"❌ 持有者发送凭证请求失败: HTTP {response.status_code}")
            print(f"响应: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 持有者发送凭证请求失败: {e}")
        return False
    
    # 3. 等待一下
    print("⏳ 等待凭证请求处理...")
    time.sleep(3)
    
    # 4. 发行者颁发凭证
    print(f"\n📜 发行者颁发凭证...")
    
    try:
        issue_data = {
            "credential_exchange_id": cred_ex_id
        }
        
        response = requests.post(
            f"{issuer_admin_url}/issue-credential/issue",
            json=issue_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            print("✅ 发行者颁发凭证成功")
        else:
            print(f"❌ 发行者颁发凭证失败: HTTP {response.status_code}")
            print(f"响应: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 发行者颁发凭证失败: {e}")
        return False
    
    # 5. 等待最终完成
    print("⏳ 等待VC完成...")
    time.sleep(5)
    
    # 6. 检查最终状态
    print("🔍 检查最终状态...")
    
    try:
        # 检查发行者端状态
        response = requests.get(f"{issuer_admin_url}/issue-credential/records", timeout=10)
        if response.status_code == 200:
            records = response.json().get('results', [])
            issuer_record = None
            for record in records:
                if record.get('credential_exchange_id') == cred_ex_id:
                    issuer_record = record
                    break
            
            if issuer_record:
                state = issuer_record.get('state')
                print(f"📊 发行者端最终状态: {state}")
                
                if state in ['credential_issued', 'credential_acked']:
                    print("🎉 跨链VC生成完成！")
                    
                    # 保存结果
                    result = {
                        "success": True,
                        "credential_exchange_id": cred_ex_id,
                        "schema_id": "DPvobytTtKvmyeRTJZYjsg:2:CrossChainLockCredential:1.0",
                        "cred_def_id": "DPvobytTtKvmyeRTJZYjsg:3:CL:11:cross-chain-lock",
                        "issuer_state": state,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    with open('cross_chain_vc_completed.json', 'w') as f:
                        json.dump(result, f, indent=2)
                    
                    print(f"📁 结果已保存到: cross_chain_vc_completed.json")
                    return True
                else:
                    print(f"⚠️ 发行者端状态异常: {state}")
                    return False
            else:
                print("❌ 未找到发行者端的凭证记录")
                return False
        else:
            print(f"❌ 检查发行者端状态失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 检查最终状态失败: {e}")
        return False

if __name__ == "__main__":
    success = complete_cross_chain_vc()
    if success:
        print("\n✅ 跨链VC流程完成成功！")
    else:
        print("\n❌ 跨链VC流程完成失败！")
