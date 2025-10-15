#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版跨链Oracle服务
支持完整的ACA-Py集成和DID管理
"""

import asyncio
import json
import logging
import requests
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from web3 import Web3
from eth_account import Account
import threading
from queue import Queue

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enhanced_oracle.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EnhancedCrossChainOracle:
    """增强版跨链Oracle服务"""
    
    def __init__(self, config_file: str = "cross_chain_config.json"):
        """初始化Oracle服务"""
        self.config = self.load_config(config_file)
        self.chains: Dict[str, Web3] = {}
        self.contracts: Dict[str, Dict] = {}
        self.event_queue = Queue()
        self.running = False
        self.connections: Dict[str, str] = {}  # 存储DID连接
        
        # 初始化各链连接
        self.setup_chains()
        
        # 初始化ACA-Py连接
        self.setup_acapy()
        
        logger.info("增强版跨链Oracle服务初始化完成")
    
    def load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"配置文件加载成功: {config_file}")
            return config
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            return self.get_default_config()
    
    def get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "oracle": {
                "admin_url": "http://localhost:8001",
                "oracle_did": "DPvobytTtKvmyeRTJZYjsg",
                "oracle_address": "0x81be24626338695584b5beaebf51e09879a0ecc6",
                "oracle_private_key": "0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a"
            },
            "chains": [
                {
                    "name": "Besu Chain A",
                    "rpc_url": "http://localhost:8545",
                    "chain_id": "chain_a",
                    "bridge_address": "0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af",
                    "verifier_address": "0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf"
                },
                {
                    "name": "Besu Chain B",
                    "rpc_url": "http://localhost:8555",
                    "chain_id": "chain_b",
                    "bridge_address": "0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af",
                    "verifier_address": "0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf"
                }
            ]
        }
    
    def setup_chains(self):
        """初始化多链连接"""
        logger.info("初始化多链连接...")
        
        for chain_config in self.config['chains']:
            chain_id = chain_config['chain_id']
            try:
                w3 = Web3(Web3.HTTPProvider(chain_config['rpc_url']))
                
                if not w3.is_connected():
                    logger.error(f"无法连接到链 {chain_id}: {chain_config['rpc_url']}")
                    continue
                
                self.chains[chain_id] = w3
                logger.info(f"成功连接到链 {chain_id}")
                
                # 加载合约ABI
                self.load_contract_abis(chain_id, chain_config)
                
            except Exception as e:
                logger.error(f"初始化链 {chain_id} 失败: {e}")
    
    def load_contract_abis(self, chain_id: str, chain_config: Dict):
        """加载合约ABI"""
        try:
            # 加载桥合约ABI
            with open('CrossChainBridgeSimple.json', 'r') as f:
                bridge_abi = json.load(f)['abi']
            
            # 加载DID验证器ABI
            with open('CrossChainDIDVerifier.json', 'r') as f:
                verifier_abi = json.load(f)['abi']
            
            # 创建合约实例
            bridge_contract = self.chains[chain_id].eth.contract(
                address=chain_config['bridge_address'],
                abi=bridge_abi
            )
            
            verifier_contract = self.chains[chain_id].eth.contract(
                address=chain_config['verifier_address'],
                abi=verifier_abi
            )
            
            self.contracts[chain_id] = {
                'bridge': bridge_contract,
                'verifier': verifier_contract
            }
            
            logger.info(f"链 {chain_id} 合约ABI加载成功")
            
        except Exception as e:
            logger.error(f"加载链 {chain_id} 合约ABI失败: {e}")
    
    def setup_acapy(self):
        """初始化ACA-Py连接"""
        self.acapy_admin_url = self.config['oracle']['admin_url']
        self.oracle_did = self.config['oracle']['oracle_did']
        
        # 测试ACA-Py连接
        try:
            response = requests.get(f"{self.acapy_admin_url}/status", timeout=10)
            if response.status_code == 200:
                logger.info("ACA-Py连接成功")
                self.acapy_connected = True
            else:
                logger.warning(f"ACA-Py连接异常: {response.status_code}")
                self.acapy_connected = False
        except Exception as e:
            logger.error(f"ACA-Py连接失败: {e}")
            self.acapy_connected = False
    
    async def start_monitoring(self):
        """开始监控跨链事件"""
        logger.info("开始监控跨链事件...")
        self.running = True
        
        # 启动事件监控任务
        tasks = []
        for chain_id in self.chains.keys():
            task = asyncio.create_task(self.monitor_chain_events(chain_id))
            tasks.append(task)
        
        # 启动事件处理任务
        process_task = asyncio.create_task(self.process_events())
        tasks.append(process_task)
        
        # 启动健康检查任务
        health_task = asyncio.create_task(self.health_check())
        tasks.append(health_task)
        
        # 等待所有任务
        await asyncio.gather(*tasks)
    
    async def monitor_chain_events(self, chain_id: str):
        """监控单链事件"""
        logger.info(f"开始监控链 {chain_id} 的事件...")
        
        last_block = self.chains[chain_id].eth.block_number
        
        while self.running:
            try:
                current_block = self.chains[chain_id].eth.block_number
                
                if current_block > last_block:
                    # 处理新区块
                    await self.process_new_blocks(chain_id, last_block + 1, current_block)
                    last_block = current_block
                
                await asyncio.sleep(self.config.get('bridge', {}).get('monitor_interval', 5))
                
            except Exception as e:
                logger.error(f"监控链 {chain_id} 事件时出错: {e}")
                await asyncio.sleep(10)
    
    async def process_new_blocks(self, chain_id: str, from_block: int, to_block: int):
        """处理新区块中的事件"""
        try:
            bridge_contract = self.contracts[chain_id]['bridge']
            
            # 监听AssetLocked事件
            locked_events = bridge_contract.events.AssetLocked.get_logs(
                fromBlock=from_block,
                toBlock=to_block
            )
            
            for event in locked_events:
                await self.handle_asset_locked(chain_id, event)
            
            # 监听AssetUnlocked事件
            unlocked_events = bridge_contract.events.AssetUnlocked.get_logs(
                fromBlock=from_block,
                toBlock=to_block
            )
            
            for event in unlocked_events:
                await self.handle_asset_unlocked(chain_id, event)
                
        except Exception as e:
            logger.error(f"处理链 {chain_id} 新区块时出错: {e}")
    
    async def handle_asset_locked(self, source_chain: str, event):
        """处理资产锁定事件"""
        try:
            event_args = event['args']
            logger.info(f"检测到资产锁定事件: 链 {source_chain}, 用户 {event_args['user']}")
            
            # 获取用户DID
            user_did = await self.get_user_did(source_chain, event_args['user'])
            if not user_did:
                logger.warning(f"未找到用户 {event_args['user']} 在链 {source_chain} 的DID")
                return
            
            # 生成跨链VC
            vc_data = await self.generate_cross_chain_vc(
                source_chain=source_chain,
                target_chain=event_args['targetChain'],
                user_did=user_did,
                amount=event_args['amount'],
                token_address=event_args['token'],
                lock_id=event_args['lockId'].hex() if hasattr(event_args['lockId'], 'hex') else str(event_args['lockId']),
                tx_hash=event['transactionHash'].hex()
            )
            
            # 通过ACA-Py颁发VC
            if self.acapy_connected:
                await self.issue_cross_chain_vc_via_acapy(user_did, vc_data)
            else:
                logger.warning("ACA-Py未连接，跳过VC颁发")
            
            # 在目标链上记录证明
            await self.record_proof_on_target_chain(
                source_chain=source_chain,
                target_chain=event_args['targetChain'],
                user_did=user_did,
                tx_hash=event['transactionHash'].hex(),
                amount=event_args['amount'],
                token_address=event_args['token']
            )
            
        except Exception as e:
            logger.error(f"处理资产锁定事件时出错: {e}")
    
    async def handle_asset_unlocked(self, chain_id: str, event):
        """处理资产解锁事件"""
        try:
            event_args = event['args']
            logger.info(f"检测到资产解锁事件: 链 {chain_id}, 用户 {event_args['user']}")
            
            # 这里可以添加解锁后的处理逻辑
            # 比如通知其他服务、更新统计信息等
            
        except Exception as e:
            logger.error(f"处理资产解锁事件时出错: {e}")
    
    async def get_user_did(self, chain_id: str, user_address: str) -> Optional[str]:
        """获取用户DID"""
        try:
            verifier_contract = self.contracts[chain_id]['verifier']
            
            # 调用合约获取DID
            did = verifier_contract.functions.didOfAddress(user_address).call()
            
            if did and did != "":
                return did
            else:
                logger.warning(f"用户 {user_address} 在链 {chain_id} 上没有注册的DID")
                return None
                
        except Exception as e:
            logger.error(f"获取用户DID时出错: {e}")
            return None
    
    async def generate_cross_chain_vc(self, **kwargs) -> Dict:
        """生成跨链可验证凭证"""
        try:
            vc_template = {
                "@context": [
                    "https://www.w3.org/2018/credentials/v1",
                    "https://example.org/cross-chain/v1"
                ],
                "type": ["VerifiableCredential", "CrossChainLockCredential"],
                "issuer": self.oracle_did,
                "issuanceDate": datetime.now().isoformat(),
                "credentialSubject": {
                    "id": kwargs['user_did'],
                    "crossChainLock": {
                        "sourceChain": kwargs['source_chain'],
                        "targetChain": kwargs['target_chain'],
                        "amount": str(kwargs['amount']),
                        "tokenAddress": kwargs['token_address'],
                        "lockId": kwargs['lock_id'],
                        "transactionHash": kwargs['tx_hash'],
                        "expiry": (datetime.now() + timedelta(hours=24)).isoformat()
                    }
                }
            }
            
            logger.info(f"生成跨链VC: {kwargs['user_did']} -> {kwargs['target_chain']}")
            return vc_template
            
        except Exception as e:
            logger.error(f"生成跨链VC时出错: {e}")
            return {}
    
    async def issue_cross_chain_vc_via_acapy(self, user_did: str, vc_data: Dict):
        """通过ACA-Py颁发VC给用户"""
        try:
            # 检查是否已有连接
            if user_did not in self.connections:
                # 创建连接
                connection_id = await self.create_connection(user_did)
                if not connection_id:
                    logger.error(f"无法为用户 {user_did} 创建连接")
                    return
                self.connections[user_did] = connection_id
            
            connection_id = self.connections[user_did]
            
            # 创建凭证提议
            credential_preview = {
                "@type": "issue-credential/1.0/credential-preview",
                "attributes": [
                    {"name": "sourceChain", "value": vc_data['credentialSubject']['crossChainLock']['sourceChain']},
                    {"name": "targetChain", "value": vc_data['credentialSubject']['crossChainLock']['targetChain']},
                    {"name": "amount", "value": vc_data['credentialSubject']['crossChainLock']['amount']},
                    {"name": "tokenAddress", "value": vc_data['credentialSubject']['crossChainLock']['tokenAddress']},
                    {"name": "lockId", "value": vc_data['credentialSubject']['crossChainLock']['lockId']},
                    {"name": "transactionHash", "value": vc_data['credentialSubject']['crossChainLock']['transactionHash']}
                ]
            }
            
            # 发送凭证提议
            credential_offer = {
                "connection_id": connection_id,
                "credential_preview": credential_preview,
                "auto_issue": True,
                "auto_remove": True
            }
            
            response = requests.post(
                f"{self.acapy_admin_url}/issue-credential/send",
                json=credential_offer,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info(f"成功为用户 {user_did} 颁发跨链VC")
            else:
                logger.error(f"颁发VC失败: {response.text}")
            
        except Exception as e:
            logger.error(f"通过ACA-Py颁发VC时出错: {e}")
    
    async def create_connection(self, user_did: str) -> Optional[str]:
        """创建与用户的连接"""
        try:
            # 创建邀请
            invite_request = {
                "auto_accept": True,
                "multi_use": False
            }
            
            response = requests.post(
                f"{self.acapy_admin_url}/connections/create-invitation",
                json=invite_request,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                invite_data = response.json()
                connection_id = invite_data['connection_id']
                logger.info(f"为用户 {user_did} 创建连接: {connection_id}")
                return connection_id
            else:
                logger.error(f"创建连接失败: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"创建连接时出错: {e}")
            return None
    
    async def record_proof_on_target_chain(self, **kwargs):
        """在目标链上记录跨链证明"""
        try:
            target_chain = kwargs['target_chain']
            if target_chain not in self.contracts:
                logger.error(f"目标链 {target_chain} 未配置")
                return
            
            verifier_contract = self.contracts[target_chain]['verifier']
            
            # 构建交易
            transaction = verifier_contract.functions.recordCrossChainProof(
                kwargs['user_did'],
                kwargs['source_chain'],
                target_chain,
                Web3.to_bytes(hexstr=kwargs['tx_hash']),
                kwargs['amount'],
                kwargs['token_address']
            ).build_transaction({
                'from': self.config['oracle']['oracle_address'],
                'nonce': self.chains[target_chain].eth.get_transaction_count(
                    self.config['oracle']['oracle_address']
                ),
                'gas': 300000,
                'gasPrice': self.chains[target_chain].to_wei('1', 'gwei')
            })
            
            # 签名并发送
            account = Account.from_key(self.config['oracle']['oracle_private_key'])
            signed_txn = account.sign_transaction(transaction)
            tx_hash = self.chains[target_chain].eth.send_raw_transaction(signed_txn.rawTransaction)
            receipt = self.chains[target_chain].eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"跨链证明已记录到链 {target_chain}: {tx_hash.hex()}")
            
        except Exception as e:
            logger.error(f"在目标链记录证明时出错: {e}")
    
    async def process_events(self):
        """处理事件队列"""
        while self.running:
            try:
                if not self.event_queue.empty():
                    event = self.event_queue.get()
                    await self.handle_event(event)
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"处理事件时出错: {e}")
                await asyncio.sleep(5)
    
    async def handle_event(self, event: Dict):
        """处理单个事件"""
        try:
            event_type = event.get('type')
            if event_type == 'asset_locked':
                await self.handle_asset_locked(event['chain_id'], event['data'])
            elif event_type == 'asset_unlocked':
                await self.handle_asset_unlocked(event['chain_id'], event['data'])
        except Exception as e:
            logger.error(f"处理事件时出错: {e}")
    
    async def health_check(self):
        """健康检查"""
        while self.running:
            try:
                # 检查链连接
                for chain_id, w3 in self.chains.items():
                    if not w3.is_connected():
                        logger.warning(f"链 {chain_id} 连接异常")
                
                # 检查ACA-Py连接
                if self.acapy_connected:
                    try:
                        response = requests.get(f"{self.acapy_admin_url}/status", timeout=5)
                        if response.status_code != 200:
                            logger.warning("ACA-Py连接异常")
                            self.acapy_connected = False
                    except:
                        logger.warning("ACA-Py连接丢失")
                        self.acapy_connected = False
                
                await asyncio.sleep(60)  # 每分钟检查一次
                
            except Exception as e:
                logger.error(f"健康检查时出错: {e}")
                await asyncio.sleep(60)
    
    async def stop(self):
        """停止Oracle服务"""
        logger.info("正在停止Oracle服务...")
        self.running = False
    
    def get_status(self) -> Dict:
        """获取Oracle服务状态"""
        status = {
            "running": self.running,
            "chains_connected": len(self.chains),
            "acapy_connected": self.acapy_connected,
            "connections": len(self.connections),
            "timestamp": datetime.now().isoformat()
        }
        
        # 检查各链状态
        status["chains"] = {}
        for chain_id, w3 in self.chains.items():
            try:
                block_number = w3.eth.block_number
                status["chains"][chain_id] = {
                    "connected": True,
                    "block_number": block_number
                }
            except:
                status["chains"][chain_id] = {
                    "connected": False,
                    "block_number": None
                }
        
        return status

async def main():
    """主函数"""
    logger.info("启动增强版跨链Oracle服务...")
    
    # 创建Oracle实例
    oracle = EnhancedCrossChainOracle()
    
    # 显示状态
    status = oracle.get_status()
    logger.info(f"Oracle服务状态: {json.dumps(status, indent=2)}")
    
    try:
        # 开始监控
        await oracle.start_monitoring()
    except KeyboardInterrupt:
        logger.info("收到停止信号...")
    finally:
        await oracle.stop()
        logger.info("Oracle服务已停止")

if __name__ == "__main__":
    asyncio.run(main())
