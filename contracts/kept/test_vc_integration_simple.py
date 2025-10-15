#!/usr/bin/env python3
"""
简化的VC集成功能测试
"""

import asyncio
import json
import logging
import aiohttp

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_acapy_connection():
    """测试ACA-Py连接"""
    logger.info("测试ACA-Py连接...")
    
    issuer_url = "http://192.168.230.178:8080"
    holder_url = "http://192.168.230.178:8081"
    
    try:
        async with aiohttp.ClientSession() as session:
            # 测试发行者连接
            async with session.get(f"{issuer_url}/status") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ 发行者连接成功: {data}")
                else:
                    logger.error(f"❌ 发行者连接失败: {response.status}")
            
            # 测试持有者连接
            async with session.get(f"{holder_url}/status") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ 持有者连接成功: {data}")
                else:
                    logger.error(f"❌ 持有者连接失败: {response.status}")
    
    except Exception as e:
        logger.error(f"测试ACA-Py连接时出错: {e}")

async def test_existing_connections():
    """测试现有连接"""
    logger.info("测试现有连接...")
    
    issuer_url = "http://192.168.230.178:8080"
    holder_url = "http://192.168.230.178:8081"
    
    try:
        async with aiohttp.ClientSession() as session:
            # 检查发行者连接
            async with session.get(f"{issuer_url}/connections") as response:
                if response.status == 200:
                    connections = await response.json()
                    active_connections = [c for c in connections.get('results', []) if c.get('state') == 'active']
                    logger.info(f"✅ 发行者端活跃连接数: {len(active_connections)}")
                    
                    for conn in active_connections:
                        logger.info(f"   - 连接ID: {conn.get('connection_id')}")
                        logger.info(f"   - 状态: {conn.get('state')}")
                        logger.info(f"   - 对方DID: {conn.get('their_did')}")
                else:
                    logger.error(f"❌ 获取发行者连接失败: {response.status}")
            
            # 检查持有者连接
            async with session.get(f"{holder_url}/connections") as response:
                if response.status == 200:
                    connections = await response.json()
                    active_connections = [c for c in connections.get('results', []) if c.get('state') == 'active']
                    logger.info(f"✅ 持有者端活跃连接数: {len(active_connections)}")
                    
                    for conn in active_connections:
                        logger.info(f"   - 连接ID: {conn.get('connection_id')}")
                        logger.info(f"   - 状态: {conn.get('state')}")
                        logger.info(f"   - 对方DID: {conn.get('their_did')}")
                else:
                    logger.error(f"❌ 获取持有者连接失败: {response.status}")
    
    except Exception as e:
        logger.error(f"测试现有连接时出错: {e}")

async def test_credential_records():
    """测试凭证记录"""
    logger.info("测试凭证记录...")
    
    issuer_url = "http://192.168.230.178:8080"
    holder_url = "http://192.168.230.178:8081"
    
    try:
        async with aiohttp.ClientSession() as session:
            # 检查发行者凭证记录
            async with session.get(f"{issuer_url}/issue-credential/records") as response:
                if response.status == 200:
                    records = await response.json()
                    logger.info(f"✅ 发行者端凭证记录数: {len(records.get('results', []))}")
                    
                    for record in records.get('results', [])[:3]:  # 只显示前3个
                        logger.info(f"   - 凭证交换ID: {record.get('credential_exchange_id')}")
                        logger.info(f"   - 状态: {record.get('state')}")
                        logger.info(f"   - 连接ID: {record.get('connection_id')}")
                else:
                    logger.error(f"❌ 获取发行者凭证记录失败: {response.status}")
            
            # 检查持有者凭证记录
            async with session.get(f"{holder_url}/issue-credential/records") as response:
                if response.status == 200:
                    records = await response.json()
                    logger.info(f"✅ 持有者端凭证记录数: {len(records.get('results', []))}")
                    
                    for record in records.get('results', [])[:3]:  # 只显示前3个
                        logger.info(f"   - 凭证交换ID: {record.get('credential_exchange_id')}")
                        logger.info(f"   - 状态: {record.get('state')}")
                        logger.info(f"   - 连接ID: {record.get('connection_id')}")
                else:
                    logger.error(f"❌ 获取持有者凭证记录失败: {response.status}")
    
    except Exception as e:
        logger.error(f"测试凭证记录时出错: {e}")

async def test_send_credential_offer():
    """测试发送凭证提供"""
    logger.info("测试发送凭证提供...")
    
    issuer_url = "http://192.168.230.178:8080"
    
    try:
        async with aiohttp.ClientSession() as session:
            # 首先获取一个活跃连接
            async with session.get(f"{issuer_url}/connections") as response:
                if response.status == 200:
                    connections = await response.json()
                    active_connections = [c for c in connections.get('results', []) if c.get('state') == 'active']
                    
                    if not active_connections:
                        logger.error("❌ 没有找到活跃连接")
                        return
                    
                    connection_id = active_connections[0]['connection_id']
                    logger.info(f"使用连接: {connection_id}")
                    
                    # 准备凭证提供
                    credential_preview = {
                        "attributes": [
                            {"name": "sourceChain", "value": "chain_a"},
                            {"name": "targetChain", "value": "chain_b"},
                            {"name": "amount", "value": "1000000000000000000"},
                            {"name": "tokenAddress", "value": "0x0000000000000000000000000000000000000000"},
                            {"name": "lockId", "value": "test_lock_123456"},
                            {"name": "transactionHash", "value": "0xabcdef1234567890"},
                            {"name": "expiry", "value": "2025-10-13T10:00:00"},
                            {"name": "userAddress", "value": "0x1234567890123456789012345678901234567890"}
                        ]
                    }
                    
                    credential_offer = {
                        "connection_id": connection_id,
                        "credential_preview": credential_preview,
                        "cred_def_id": "DPvobytTtKvmyeRTJZYjsg:3:CL:11:cross-chain-lock",
                        "auto_issue": True,
                        "auto_remove": True
                    }
                    
                    # 发送凭证提供
                    async with session.post(
                        f"{issuer_url}/issue-credential/send",
                        json=credential_offer
                    ) as offer_response:
                        if offer_response.status == 200:
                            result = await offer_response.json()
                            logger.info(f"✅ 凭证提供发送成功: {result}")
                        else:
                            error_text = await offer_response.text()
                            logger.error(f"❌ 凭证提供发送失败: {offer_response.status} - {error_text}")
                else:
                    logger.error(f"❌ 获取连接失败: {response.status}")
    
    except Exception as e:
        logger.error(f"测试发送凭证提供时出错: {e}")

async def main():
    """主测试函数"""
    logger.info("=" * 50)
    logger.info("开始VC集成功能简化测试")
    logger.info("=" * 50)
    
    try:
        # 测试1: ACA-Py连接
        await test_acapy_connection()
        
        # 测试2: 现有连接
        await test_existing_connections()
        
        # 测试3: 凭证记录
        await test_credential_records()
        
        # 测试4: 发送凭证提供
        await test_send_credential_offer()
        
        logger.info("\n" + "=" * 50)
        logger.info("所有测试完成！")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    if success:
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 测试失败！")
        sys.exit(1)
