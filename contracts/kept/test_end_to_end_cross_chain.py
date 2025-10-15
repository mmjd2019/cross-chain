#!/usr/bin/env python3
"""
端到端跨链交易流程测试
测试完整的跨链VC系统功能
"""

import asyncio
import json
import logging
import aiohttp
import sys
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EndToEndCrossChainTest:
    """端到端跨链交易测试"""
    
    def __init__(self):
        self.issuer_url = "http://192.168.230.178:8080"
        self.holder_url = "http://192.168.230.178:8081"
        self.test_results = {}
    
    async def test_complete_workflow(self):
        """测试完整工作流程"""
        logger.info("开始端到端跨链交易流程测试")
        
        try:
            # 步骤1: 检查服务状态
            await self.check_services_status()
            
            # 步骤2: 建立连接
            connection_id = await self.establish_connection()
            if not connection_id:
                logger.error("❌ 无法建立连接，测试终止")
                return False
            
            # 步骤3: 发送跨链VC提供
            vc_result = await self.send_cross_chain_vc_offer(connection_id)
            if not vc_result:
                logger.error("❌ VC提供发送失败，测试终止")
                return False
            
            # 步骤4: 处理VC流程
            await self.process_vc_flow(vc_result['credential_exchange_id'])
            
            # 步骤5: 验证最终结果
            success = await self.verify_final_result()
            
            return success
            
        except Exception as e:
            logger.error(f"端到端测试过程中出错: {e}")
            return False
    
    async def check_services_status(self):
        """检查服务状态"""
        logger.info("🔍 检查服务状态...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # 检查发行者服务
                async with session.get(f"{self.issuer_url}/status") as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"✅ 发行者服务正常: {data['label']}")
                    else:
                        logger.error(f"❌ 发行者服务异常: {response.status}")
                
                # 检查持有者服务
                async with session.get(f"{self.holder_url}/status") as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"✅ 持有者服务正常: {data['label']}")
                    else:
                        logger.error(f"❌ 持有者服务异常: {response.status}")
        
        except Exception as e:
            logger.error(f"检查服务状态时出错: {e}")
    
    async def establish_connection(self):
        """建立连接"""
        logger.info("🔗 建立连接...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # 检查现有连接
                async with session.get(f"{self.issuer_url}/connections") as response:
                    if response.status == 200:
                        connections = await response.json()
                        active_connections = [c for c in connections.get('results', []) if c.get('state') == 'active']
                        
                        if active_connections:
                            connection_id = active_connections[0]['connection_id']
                            logger.info(f"✅ 使用现有连接: {connection_id}")
                            return connection_id
                
                # 创建新连接
                logger.info("创建新连接...")
                async with session.post(f"{self.issuer_url}/connections/create-invitation") as response:
                    if response.status == 200:
                        invitation = await response.json()
                        invitation_url = invitation["invitation_url"]
                        connection_id = invitation["connection_id"]
                        
                        logger.info(f"✅ 发行者创建邀请: {connection_id}")
                        
                        # 持有者接收邀请
                        async with session.post(
                            f"{self.holder_url}/connections/receive-invitation",
                            json={"invitation_url": invitation_url}
                        ) as holder_response:
                            if holder_response.status == 200:
                                holder_conn = await holder_response.json()
                                logger.info(f"✅ 持有者接收邀请: {holder_conn['connection_id']}")
                                
                                # 等待连接建立
                                await asyncio.sleep(3)
                                return connection_id
                            else:
                                error_text = await holder_response.text()
                                logger.error(f"❌ 持有者接收邀请失败: {holder_response.status} - {error_text}")
                                return None
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ 发行者创建邀请失败: {response.status} - {error_text}")
                        return None
        
        except Exception as e:
            logger.error(f"建立连接时出错: {e}")
            return None
    
    async def send_cross_chain_vc_offer(self, connection_id: str):
        """发送跨链VC提供"""
        logger.info("📋 发送跨链VC提供...")
        
        try:
            # 准备跨链VC数据
            expiry_time = datetime.now() + timedelta(hours=24)
            
            credential_preview = {
                "attributes": [
                    {"name": "sourceChain", "value": "chain_a"},
                    {"name": "targetChain", "value": "chain_b"},
                    {"name": "amount", "value": "1000000000000000000"},
                    {"name": "tokenAddress", "value": "0x0000000000000000000000000000000000000000"},
                    {"name": "lockId", "value": f"e2e_test_{int(datetime.now().timestamp())}"},
                    {"name": "transactionHash", "value": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"},
                    {"name": "expiry", "value": expiry_time.isoformat()}
                ]
            }
            
            credential_offer = {
                "connection_id": connection_id,
                "credential_preview": credential_preview,
                "cred_def_id": "DPvobytTtKvmyeRTJZYjsg:3:CL:11:cross-chain-lock",
                "auto_issue": True,
                "auto_remove": True,
                "credential_proposal": credential_preview
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.issuer_url}/issue-credential/send",
                    json=credential_offer
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ 跨链VC提供发送成功: {result['credential_exchange_id']}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ 跨链VC提供发送失败: {response.status} - {error_text}")
                        return None
        
        except Exception as e:
            logger.error(f"发送跨链VC提供时出错: {e}")
            return None
    
    async def process_vc_flow(self, cred_ex_id: str):
        """处理VC流程"""
        logger.info(f"🔄 处理VC流程: {cred_ex_id}")
        
        try:
            # 等待一下让异步操作完成
            await asyncio.sleep(2)
            
            # 检查发行者端状态
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.issuer_url}/issue-credential/records/{cred_ex_id}") as response:
                    if response.status == 200:
                        record = await response.json()
                        logger.info(f"📊 发行者端状态: {record['state']}")
                        
                        # 如果状态是request_received，则颁发凭证
                        if record['state'] == 'request_received':
                            await self.issue_credential(cred_ex_id)
                    else:
                        logger.warning(f"无法获取发行者端记录: {response.status}")
                
                # 检查持有者端状态
                async with session.get(f"{self.holder_url}/issue-credential/records") as response:
                    if response.status == 200:
                        records = await response.json()
                        for record in records.get('results', []):
                            if record.get('credential_exchange_id') == cred_ex_id:
                                logger.info(f"📊 持有者端状态: {record['state']}")
                                break
        
        except Exception as e:
            logger.error(f"处理VC流程时出错: {e}")
    
    async def issue_credential(self, cred_ex_id: str):
        """颁发凭证"""
        logger.info(f"🎓 颁发凭证: {cred_ex_id}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.issuer_url}/issue-credential/records/{cred_ex_id}/issue",
                    json={}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ 凭证颁发成功: {result}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ 凭证颁发失败: {response.status} - {error_text}")
                        return None
        
        except Exception as e:
            logger.error(f"颁发凭证时出错: {e}")
            return None
    
    async def verify_final_result(self):
        """验证最终结果"""
        logger.info("🔍 验证最终结果...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # 检查发行者端最终状态
                async with session.get(f"{self.issuer_url}/issue-credential/records") as response:
                    if response.status == 200:
                        records = await response.json()
                        issued_count = len([r for r in records.get('results', []) if r.get('state') == 'credential_issued'])
                        logger.info(f"📊 发行者端已颁发凭证数: {issued_count}")
                
                # 检查持有者端最终状态
                async with session.get(f"{self.holder_url}/issue-credential/records") as response:
                    if response.status == 200:
                        records = await response.json()
                        received_count = len([r for r in records.get('results', []) if r.get('state') == 'credential_received'])
                        logger.info(f"📊 持有者端已接收凭证数: {received_count}")
                        
                        if received_count > 0:
                            logger.info("✅ 端到端跨链VC流程测试成功！")
                            return True
                        else:
                            logger.warning("⚠️  持有者端未接收到凭证")
                            return False
                    else:
                        logger.error(f"❌ 无法获取持有者端记录: {response.status}")
                        return False
        
        except Exception as e:
            logger.error(f"验证最终结果时出错: {e}")
            return False

async def main():
    """主测试函数"""
    logger.info("=" * 60)
    logger.info("🚀 开始端到端跨链交易流程测试")
    logger.info("=" * 60)
    
    test = EndToEndCrossChainTest()
    success = await test.test_complete_workflow()
    
    logger.info("\n" + "=" * 60)
    if success:
        logger.info("🎉 端到端跨链交易流程测试成功完成！")
        logger.info("✅ 跨链VC系统功能正常")
    else:
        logger.info("❌ 端到端跨链交易流程测试失败")
        logger.info("⚠️  请检查系统配置和连接状态")
    logger.info("=" * 60)
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    if success:
        print("\n🎉 测试成功！跨链VC系统运行正常！")
    else:
        print("\n❌ 测试失败！请检查系统状态！")
        sys.exit(1)
