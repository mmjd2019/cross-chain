#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完成跨链VC颁发 - 使用正确的凭证交换ID
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

def final_vc_issuance():
    """完成跨链VC颁发"""
    
    # 配置
    issuer_admin_url = "http://192.168.230.178:8080"
    holder_admin_url = "http://192.168.230.178:8081"
    
    # 使用找到的凭证交换ID
    cred_ex_id = "5824e437-10bf-4f8b-96cf-8f7e79a10279"
    
    print("🚀 完成跨链VC颁发")
    print("=" * 50)
    print(f"凭证交换ID: {cred_ex_id}")
    
    # 1. 检查发行者端的凭证记录状态
    print(f"\n🔍 检查发行者端凭证记录状态...")
    
    try:
        response = requests.get(f"{issuer_admin_url}/issue-credential/records", timeout=10)
        if response.status_code == 200:
            records = response.json().get('results', [])
            issuer_record = None
            for record in records:
                if record.get('credential_exchange_id') == cred_ex_id:
                    issuer_record = record
                    break
            
            if issuer_record:
                print(f"✅ 发行者端凭证记录状态: {issuer_record.get('state', 'unknown')}")
                print(f"Schema: {issuer_record.get('schema_id', 'unknown')}")
                print(f"凭证定义: {issuer_record.get('credential_definition_id', 'unknown')}")
            else:
                print(f"❌ 发行者端未找到对应的凭证记录")
                return False
        else:
            print(f"❌ 获取发行者端凭证记录失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 检查发行者端凭证记录时出错: {e}")
        return False
    
    # 2. 检查持有者端的凭证记录状态
    print(f"\n🔍 检查持有者端凭证记录状态...")
    
    try:
        response = requests.get(f"{holder_admin_url}/issue-credential/records", timeout=10)
        if response.status_code == 200:
            records = response.json().get('results', [])
            holder_record = None
            for record in records:
                if record.get('credential_exchange_id') == cred_ex_id:
                    holder_record = record
                    break
            
            if holder_record:
                print(f"✅ 持有者端凭证记录状态: {holder_record.get('state', 'unknown')}")
                print(f"Schema: {holder_record.get('schema_id', 'unknown')}")
                print(f"凭证定义: {holder_record.get('credential_definition_id', 'unknown')}")
            else:
                print(f"❌ 持有者端未找到对应的凭证记录")
                return False
        else:
            print(f"❌ 获取持有者端凭证记录失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 检查持有者端凭证记录时出错: {e}")
        return False
    
    # 3. 发行者颁发凭证
    print(f"\n📜 发行者颁发凭证...")
    
    try:
        issue_data = {
            "credential_exchange_id": cred_ex_id
        }
        
        response = requests.post(
            f"{issuer_admin_url}/issue-credential/records/{cred_ex_id}/issue",
            json=issue_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 发行者颁发凭证成功")
            print(f"状态: {result.get('state', 'unknown')}")
            
            # 检查是否有凭证数据
            if 'credential' in result:
                print(f"✅ 凭证已成功颁发并包含凭证数据")
                print(f"凭证数据: {json.dumps(result['credential'], indent=2)}")
                return True
            else:
                print(f"⚠️ 凭证已颁发但未包含凭证数据")
                return True
        else:
            print(f"❌ 发行者颁发凭证失败: HTTP {response.status_code}")
            print(f"响应: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 发行者颁发凭证时出错: {e}")
        return False
    
    # 4. 最终状态检查
    print(f"\n🔍 最终状态检查...")
    
    try:
        # 检查发行者端
        response = requests.get(f"{issuer_admin_url}/issue-credential/records", timeout=10)
        if response.status_code == 200:
            records = response.json().get('results', [])
            for record in records:
                if record.get('credential_exchange_id') == cred_ex_id:
                    print(f"发行者端最终状态: {record.get('state', 'unknown')}")
                    break
        
        # 检查持有者端
        response = requests.get(f"{holder_admin_url}/issue-credential/records", timeout=10)
        if response.status_code == 200:
            records = response.json().get('results', [])
            for record in records:
                if record.get('credential_exchange_id') == cred_ex_id:
                    print(f"持有者端最终状态: {record.get('state', 'unknown')}")
                    if 'raw_credential' in record:
                        print(f"✅ 持有者已成功接收凭证")
                        print(f"凭证数据: {json.dumps(record['raw_credential'], indent=2)}")
                    break
        
        return True
    except Exception as e:
        print(f"❌ 最终状态检查时出错: {e}")
        return False

if __name__ == "__main__":
    print("🎯 开始完成跨链VC颁发流程")
    print("=" * 60)
    
    success = final_vc_issuance()
    
    if success:
        print("\n🎉 跨链VC颁发流程完成！")
        print("✅ 凭证已成功颁发给持有者")
    else:
        print("\n❌ 跨链VC颁发流程失败")
        print("请检查错误信息并重试")
    
    print("=" * 60)
