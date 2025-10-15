#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完成跨链VC流程：持有者接收凭证，发行者颁发凭证
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

def complete_vc_flow():
    """完成跨链VC流程"""
    
    # 配置
    issuer_admin_url = "http://192.168.230.178:8080"
    holder_admin_url = "http://192.168.230.178:8081"
    cred_ex_id = "5dec67e1-73ff-49fe-8927-7ba7afb1173d"
    
    print("🔐 完成跨链VC流程")
    print("=" * 50)
    
    # 1. 检查当前状态
    print("🔍 检查当前VC状态...")
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
            print(f"📊 当前状态: {state}")
            
            if state == 'offer_sent':
                print("✅ 凭证提供已发送，开始接收流程...")
            elif state == 'credential_issued':
                print("🎉 VC已经完成颁发！")
                return True
            else:
                print(f"⚠️ 意外状态: {state}")
                return False
        else:
            print("❌ 未找到指定的VC记录")
            return False
    else:
        print(f"❌ 获取VC记录失败: HTTP {response.status_code}")
        return False
    
    # 2. 持有者接收凭证提供
    print("\n📥 持有者接收凭证提供...")
    
    # 首先获取持有者的凭证记录
    response = requests.get(f"{holder_admin_url}/issue-credential/records", timeout=10)
    if response.status_code == 200:
        holder_records = response.json().get('results', [])
        holder_vc_record = None
        for record in holder_records:
            if record.get('credential_exchange_id') == cred_ex_id:
                holder_vc_record = record
                break
        
        if holder_vc_record:
            print(f"📋 持有者VC状态: {holder_vc_record.get('state')}")
            
            # 如果持有者还没有接收，则接收凭证提供
            if holder_vc_record.get('state') == 'offer_received':
                print("📨 持有者接收凭证提供...")
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
                    print(f"响应: {response.text}")
                    return False
            else:
                print(f"ℹ️ 持有者状态: {holder_vc_record.get('state')}")
        else:
            print("⚠️ 持有者端未找到对应的VC记录")
    
    # 3. 等待一下让系统处理
    print("⏳ 等待系统处理...")
    time.sleep(3)
    
    # 4. 发行者颁发凭证
    print("\n📜 发行者颁发凭证...")
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
        print(f"响应: {response.text}")
        return False
    
    # 5. 等待最终完成
    print("⏳ 等待VC完成...")
    time.sleep(5)
    
    # 6. 检查最终状态
    print("\n🔍 检查最终状态...")
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
                print("🎉 跨链VC流程完成！")
                
                # 显示VC详情
                if 'credential' in vc_record:
                    credential = vc_record['credential']
                    print("\n📋 VC详情:")
                    print(f"  Schema ID: {credential.get('schema_id')}")
                    print(f"  凭证定义ID: {credential.get('cred_def_id')}")
                    print(f"  值: {credential.get('values', {})}")
                
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

if __name__ == "__main__":
    success = complete_vc_flow()
    if success:
        print("\n✅ 跨链VC流程完成成功！")
    else:
        print("\n❌ 跨链VC流程完成失败！")
