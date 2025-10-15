#!/usr/bin/env python3
"""
增强版跨链Oracle服务 - 集成VC功能 (修复版)
支持基于DID和可验证凭证的跨链交易管理
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import aiohttp
import requests
from web3 import Web3
from eth_account import Account
import os
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('oracle_with_vc_fixed.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EnhancedOracleWithVCFixed:
    """增强版跨链Oracle服务 - 集成VC功能 (修复版)"""
    
    def __init__(self, config_file: str = "cross_chain_config.json"):
        """初始化Oracle服务"""
        self.config = self.load_config(config_file)
        self.vc_config = self.load_vc_config()
        self.running = False
        self.chains = {}
        self.connections = {}
        self.issued_vcs = {}  # 存储已颁发的VC
        
        # 初始化Web3连接
        self.init_web3_connections()
        
        # 初始化ACA-Py连接
        self.init_acapy_connections()
        
        logger.info("增强版跨链Oracle服务初始化完成")
    
    def load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"配置文件 {config_file} 加载成功")
            return config
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            raise
    
    def load_vc_config(self) -> Dict:
        """加载VC配置文件"""
        try:
            with open("cross_chain_vc_config.json", 'r', encoding='utf-8') as f:
                vc_config = json.load(f)
            logger.info("VC配置文件加载成功")
            return vc_config
        except Exception as e:
            logger.error(f"VC配置文件加载失败: {e}")
            return {}
    
    def init_web3_connections(self):
        """初始化Web3连接"""
        for chain_config in self.config.get('chains', []):
            try:
                # 使用更兼容的Web3初始化方式
                w3 = Web3(Web3.HTTPProvider(chain_config['rpc_url'], request_kwargs={'timeout': 10}))
                
                # 测试连接
                try:
                    block_number = w3.eth.block_number
                    logger.info(f"链 {chain_config['name']} 连接成功，当前区块: {block_number}")
                    
                    self.chains[chain_config['chain_id']] = {
                        'web3': w3,
                        'config': chain_config,
                        'bridge_contract': None,
                        'verifier_contract': None,
                        'last_block': block_number
                    }
                except Exception as e:
                    logger.warning(f"链 {chain_config['name']} 连接测试失败: {e}")
                    # 即使连接测试失败，也保留配置用于后续重试
                    self.chains[chain_config['chain_id']] = {
                        'web3': w3,
                        'config': chain_config,
                        'bridge_contract': None,
                        'verifier_contract': None,
                        'last_block': 0
                    }
                    
            except Exception as e:
                logger.error(f"链 {chain_config['name']} 初始化失败: {e}")
    
    def init_acapy_connections(self):
        """初始化ACA-Py连接"""
        self.acapy_issuer_url = self.vc_config.get('acapy_services', {}).get('issuer', {}).get('admin_url', 'http://192.168.230.178:8080')
        self.acapy_holder_url = self.vc_config.get('acapy_services', {}).get('holder', {}).get('admin_url', 'http://192.168.230.178:8081')
        
        # 获取DID信息
        self.oracle_did = self.config.get('oracle', {}).get('oracle_did', 'DPvobytTtKvmyeRTJZYjsg')
        self.holder_did = 'YL2HDxkVL8qMrssaZbvtfH'  # 从之前的配置中获取
        
        logger.info(f"ACA-Py连接初始化完成 - 发行者: {self.acapy_issuer_url}, 持有者: {self.acapy_holder_url}")
    
    async def start(self):
        """启动Oracle服务"""
        self.running = True
        logger.info("增强版跨链Oracle服务启动")
        
        # 启动事件监控任务
        tasks = []
        for chain_id in self.chains.keys():
            task = asyncio.create_task(self.monitor_chain_events(chain_id))
            tasks.append(task)
        
        # 启动VC管理任务
        vc_task = asyncio.create_task(self.manage_vc_connections())
        tasks.append(vc_task)
        
        # 等待所有任务
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("收到停止信号，正在关闭服务...")
            self.running = False
    
    async def monitor_chain_events(self, chain_id: str):
        """监控链事件"""
        chain_info = self.chains[chain_id]
        last_block = chain_info.get('last_block', 0)
        
        logger.info(f"开始监控链 {chain_id} 的事件")
        
        while self.running:
            try:
                # 尝试获取当前区块号
                try:
                    current_block = chain_info['web3'].eth.block_number
                    chain_info['last_block'] = current_block
                except Exception as e:
                    logger.warning(f"获取链 {chain_id} 区块号失败: {e}")
                    await asyncio.sleep(10)
                    continue
                
                if current_block > last_block:
                    await self.process_new_blocks(chain_id, last_block + 1, current_block)
                    last_block = current_block
                
                await asyncio.sleep(5)  # 每5秒检查一次
            except Exception as e:
                logger.error(f"监控链 {chain_id} 时出错: {e}")
                await asyncio.sleep(10)
    
    async def process_new_blocks(self, chain_id: str, from_block: int, to_block: int):
        """处理新区块中的事件"""
        chain_info = self.chains[chain_id]
        
        try:
            logger.info(f"处理链 {chain_id} 区块 {from_block}-{to_block}")
            
            # 模拟检测到锁定事件（每10个区块模拟一个事件）
            if to_block % 10 == 0:
                await self.handle_asset_locked_event(chain_id, {
                    'user': '0x1234567890123456789012345678901234567890',
                    'amount': '1000000000000000000',  # 1 ETH
                    'token': '0x0000000000000000000000000000000000000000',
                    'lockId': f'lock_{chain_id}_{to_block}',
                    'txHash': f'0x{to_block:064x}'
                })
        
        except Exception as e:
            logger.error(f"处理区块事件时出错: {e}")
    
    async def handle_asset_locked_event(self, chain_id: str, event_data: Dict):
        """处理资产锁定事件"""
        logger.info(f"检测到链 {chain_id} 的资产锁定事件: {event_data}")
        
        try:
            # 生成跨链VC
            vc_data = await self.generate_cross_chain_vc(chain_id, event_data)
            
            # 颁发VC给用户
            vc_result = await self.issue_cross_chain_vc(vc_data)
            
            if vc_result:
                logger.info(f"成功颁发跨链VC: {vc_result}")
                self.issued_vcs[event_data['lockId']] = vc_result
            else:
                logger.error("VC颁发失败")
        
        except Exception as e:
            logger.error(f"处理资产锁定事件时出错: {e}")
    
    async def generate_cross_chain_vc(self, source_chain: str, event_data: Dict) -> Dict:
        """生成跨链可验证凭证数据"""
        # 确定目标链
        target_chain = "chain_b" if source_chain == "chain_a" else "chain_a"
        
        # 计算过期时间（24小时后）
        expiry_time = datetime.now() + timedelta(hours=24)
        
        vc_data = {
            "source_chain": source_chain,
            "target_chain": target_chain,
            "amount": event_data['amount'],
            "token_address": event_data['token'],
            "lock_id": event_data['lockId'],
            "transaction_hash": event_data['txHash'],
            "user_address": event_data['user'],
            "expiry": expiry_time.isoformat(),
            "user_did": self.holder_did  # 使用持有者DID
        }
        
        logger.info(f"生成跨链VC数据: {vc_data}")
        return vc_data
    
    async def issue_cross_chain_vc(self, vc_data: Dict) -> Optional[Dict]:
        """颁发跨链可验证凭证"""
        try:
            # 检查连接状态
            connection_id = await self.get_or_create_connection()
            if not connection_id:
                logger.error("无法建立连接")
                return None
            
            # 准备凭证数据
            credential_preview = {
                "attributes": [
                    {"name": "sourceChain", "value": vc_data["source_chain"]},
                    {"name": "targetChain", "value": vc_data["target_chain"]},
                    {"name": "amount", "value": vc_data["amount"]},
                    {"name": "tokenAddress", "value": vc_data["token_address"]},
                    {"name": "lockId", "value": vc_data["lock_id"]},
                    {"name": "transactionHash", "value": vc_data["transaction_hash"]},
                    {"name": "expiry", "value": vc_data["expiry"]},
                    {"name": "userAddress", "value": vc_data["user_address"]}
                ]
            }
            
            # 发送凭证提供
            credential_offer = {
                "connection_id": connection_id,
                "credential_preview": credential_preview,
                "cred_def_id": "DPvobytTtKvmyeRTJZYjsg:3:CL:11:cross-chain-lock",
                "auto_issue": True,
                "auto_remove": True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.acapy_issuer_url}/issue-credential/send",
                    json=credential_offer
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"凭证提供发送成功: {result}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"凭证提供发送失败: {response.status} - {error_text}")
                        return None
        
        except Exception as e:
            logger.error(f"颁发跨链VC时出错: {e}")
            return None
    
    async def get_or_create_connection(self) -> Optional[str]:
        """获取或创建连接"""
        try:
            # 检查现有连接
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.acapy_issuer_url}/connections") as response:
                    if response.status == 200:
                        connections = await response.json()
                        for conn in connections.get('results', []):
                            if conn.get('state') == 'active' and conn.get('their_did') == self.holder_did:
                                logger.info(f"找到现有连接: {conn['connection_id']}")
                                return conn['connection_id']
            
            # 如果没有找到连接，创建新连接
            logger.info("未找到现有连接，创建新连接...")
            return await self.create_new_connection()
        
        except Exception as e:
            logger.error(f"获取连接时出错: {e}")
            return None
    
    async def create_new_connection(self) -> Optional[str]:
        """创建新连接"""
        try:
            async with aiohttp.ClientSession() as session:
                # 发行者创建邀请
                async with session.post(f"{self.acapy_issuer_url}/connections/create-invitation") as response:
                    if response.status == 200:
                        invitation = await response.json()
                        invitation_url = invitation["invitation_url"]
                        connection_id = invitation["connection_id"]
                        
                        logger.info(f"发行者创建邀请成功: {connection_id}")
                        
                        # 持有者接收邀请
                        async with session.post(
                            f"{self.acapy_holder_url}/connections/receive-invitation",
                            json={"invitation_url": invitation_url}
                        ) as holder_response:
                            if holder_response.status == 200:
                                holder_conn = await holder_response.json()
                                logger.info(f"持有者接收邀请成功: {holder_conn['connection_id']}")
                                
                                # 等待连接建立
                                await asyncio.sleep(2)
                                return connection_id
                            else:
                                error_text = await holder_response.text()
                                logger.error(f"持有者接收邀请失败: {holder_response.status} - {error_text}")
                                return None
                    else:
                        error_text = await response.text()
                        logger.error(f"发行者创建邀请失败: {response.status} - {error_text}")
                        return None
        
        except Exception as e:
            logger.error(f"创建连接时出错: {e}")
            return None
    
    async def manage_vc_connections(self):
        """管理VC连接"""
        while self.running:
            try:
                # 检查连接状态
                await self.check_connection_status()
                
                # 处理待处理的VC
                await self.process_pending_vcs()
                
                await asyncio.sleep(30)  # 每30秒检查一次
            
            except Exception as e:
                logger.error(f"管理VC连接时出错: {e}")
                await asyncio.sleep(10)
    
    async def check_connection_status(self):
        """检查连接状态"""
        try:
            async with aiohttp.ClientSession() as session:
                # 检查发行者连接
                async with session.get(f"{self.acapy_issuer_url}/connections") as response:
                    if response.status == 200:
                        connections = await response.json()
                        active_connections = [c for c in connections.get('results', []) if c.get('state') == 'active']
                        logger.info(f"发行者端活跃连接数: {len(active_connections)}")
                
                # 检查持有者连接
                async with session.get(f"{self.acapy_holder_url}/connections") as response:
                    if response.status == 200:
                        connections = await response.json()
                        active_connections = [c for c in connections.get('results', []) if c.get('state') == 'active']
                        logger.info(f"持有者端活跃连接数: {len(active_connections)}")
        
        except Exception as e:
            logger.error(f"检查连接状态时出错: {e}")
    
    async def process_pending_vcs(self):
        """处理待处理的VC"""
        try:
            # 检查发行者端的凭证记录
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.acapy_issuer_url}/issue-credential/records") as response:
                    if response.status == 200:
                        records = await response.json()
                        for record in records.get('results', []):
                            if record.get('state') == 'request_received':
                                await self.issue_credential(record['credential_exchange_id'])
        
        except Exception as e:
            logger.error(f"处理待处理VC时出错: {e}")
    
    async def issue_credential(self, cred_ex_id: str):
        """颁发凭证"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.acapy_issuer_url}/issue-credential/records/{cred_ex_id}/issue",
                    json={}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"凭证颁发成功: {cred_ex_id}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"凭证颁发失败: {response.status} - {error_text}")
                        return None
        
        except Exception as e:
            logger.error(f"颁发凭证时出错: {e}")
            return None
    
    async def get_vc_status(self, lock_id: str) -> Optional[Dict]:
        """获取VC状态"""
        return self.issued_vcs.get(lock_id)
    
    async def verify_cross_chain_proof(self, vc_data: Dict) -> bool:
        """验证跨链证明"""
        try:
            # 这里应该实现VC验证逻辑
            # 目前返回True表示验证通过
            logger.info(f"验证跨链证明: {vc_data}")
            return True
        
        except Exception as e:
            logger.error(f"验证跨链证明时出错: {e}")
            return False

async def main():
    """主函数"""
    oracle = EnhancedOracleWithVCFixed()
    await oracle.start()

if __name__ == "__main__":
    asyncio.run(main())
