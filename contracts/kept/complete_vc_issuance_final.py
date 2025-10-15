#!/usr/bin/env python3
"""
完成跨链VC颁发流程
使用正确的credential_exchange_id和thread_id
"""

import asyncio
import aiohttp
import json
from datetime import datetime

# 配置
ISSUER_ADMIN_URL = "http://192.168.230.178:8080"
HOLDER_ADMIN_URL = "http://192.168.230.178:8081"

# 从持有者端找到的凭证记录信息
CRED_EX_ID = "5824e437-10bf-4f8b-96cf-8f7e79a10279"
THREAD_ID = "dd984407-d9b7-4c75-953f-05ad599fa17a"

async def check_issuer_credential_records():
    """检查发行者端的凭证记录"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{ISSUER_ADMIN_URL}/issue-credential/records") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 发行者端共有 {len(data['results'])} 个凭证记录")
                    
                    # 查找匹配的thread_id
                    for record in data['results']:
                        if record.get('thread_id') == THREAD_ID:
                            print(f"✅ 找到匹配的凭证记录: {record['credential_exchange_id']}")
                            print(f"   状态: {record['state']}")
                            print(f"   连接ID: {record['connection_id']}")
                            return record['credential_exchange_id']
                    
                    print(f"❌ 发行者端未找到thread_id为 {THREAD_ID} 的记录")
                    return None
                else:
                    print(f"❌ 获取发行者端凭证记录失败: HTTP {response.status}")
                    return None
        except Exception as e:
            print(f"❌ 检查发行者端凭证记录时出错: {e}")
            return None

async def issue_credential(cred_ex_id):
    """发行凭证"""
    async with aiohttp.ClientSession() as session:
        try:
            # 发行凭证
            issue_data = {
                "cred_ex_id": cred_ex_id,
                "comment": "Cross-Chain Lock Credential Issued"
            }
            
            async with session.post(
                f"{ISSUER_ADMIN_URL}/issue-credential/records/{cred_ex_id}/issue",
                json=issue_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ 凭证颁发成功!")
                    print(f"   凭证交换ID: {result.get('credential_exchange_id', 'N/A')}")
                    print(f"   状态: {result.get('state', 'N/A')}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ 凭证颁发失败: HTTP {response.status}")
                    print(f"   错误信息: {error_text}")
                    return False
        except Exception as e:
            print(f"❌ 颁发凭证时出错: {e}")
            return False

async def check_holder_credential_status():
    """检查持有者端凭证状态"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{HOLDER_ADMIN_URL}/issue-credential/records/{CRED_EX_ID}") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 持有者端凭证状态: {data['state']}")
                    if data['state'] == 'credential_received':
                        print(f"✅ 持有者已成功接收凭证!")
                        return True
                    else:
                        print(f"⏳ 持有者端状态: {data['state']}")
                        return False
                else:
                    print(f"❌ 获取持有者端凭证状态失败: HTTP {response.status}")
                    return False
        except Exception as e:
            print(f"❌ 检查持有者端凭证状态时出错: {e}")
            return False

async def main():
    """主函数"""
    print("🚀 开始完成跨链VC颁发流程")
    print(f"📋 使用凭证交换ID: {CRED_EX_ID}")
    print(f"📋 使用线程ID: {THREAD_ID}")
    print()
    
    # 1. 检查发行者端是否有对应的凭证记录
    print("1️⃣ 检查发行者端凭证记录...")
    issuer_cred_ex_id = await check_issuer_credential_records()
    
    if not issuer_cred_ex_id:
        print("❌ 发行者端没有找到对应的凭证记录，无法完成颁发")
        return
    
    # 2. 尝试颁发凭证
    print("\n2️⃣ 尝试颁发凭证...")
    success = await issue_credential(issuer_cred_ex_id)
    
    if not success:
        print("❌ 凭证颁发失败")
        return
    
    # 3. 检查持有者端状态
    print("\n3️⃣ 检查持有者端凭证状态...")
    await asyncio.sleep(2)  # 等待2秒让状态更新
    await check_holder_credential_status()
    
    print("\n🎉 跨链VC颁发流程完成!")

if __name__ == "__main__":
    asyncio.run(main())
