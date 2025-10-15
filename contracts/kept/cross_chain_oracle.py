#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨链交易Oracle服务
基于DID和可验证凭证的跨链协调服务
"""

import asyncio
import json
import logging
import requests
import time
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
        logging.FileHandler('oracle.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CrossChainOracle:
    """跨链Oracle服务"""
    
    def __init__(self, config_file: str = "cross_chain_config.json"):
        """初始化Oracle服务"""
        self.config = self.load_config(config_file)
        self.chains: Dict[str, Web3] = {}
        self.contracts: Dict[str, Dict] = {}
        self.event_queue = Queue()
        self.running = False
        
        # 初始化各链连接
        self.setup_chains()
        
        # 初始化ACA-Py连接
        self.setup_acapy()
        
        logger.info("跨链Oracle服务初始化完成")
    
    def load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"配置文件加载成功: {config_file}")
            return config
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            # 使用默认配置
            return self.get_default_config()
    
    def get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "oracle": {
                "admin_url": "http://localhost:8001",
                "oracle_did": "did:indy:testnet:oracle#key-1",
                "oracle_address": "0x19E7E376E7C213B7E7e7e46cc70A5dD086DAff2A",
                "oracle_private_key": "0x" + "1" * 64,
                "description": "跨链Oracle服务配置"
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
            ],
            "bridge": {
                "proof_validity_period": 86400,
                "max_supported_chains": 10,
                "description": "跨链桥配置参数"
            }
        }
    
    def setup_chains(self):
        """初始化多链连接"""
        logger.info("初始化多链连接...")
        
        for chain_config in self.config['chains']:
            chain_id = chain_config['chain_id']
            try:
                # 创建Web3连接
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
        self.acapy_url = self.config['oracle']['admin_url']
        self.oracle_did = self.config['oracle']['oracle_did']
        
        # 测试ACA-Py连接
        try:
            response = requests.get(f"{self.acapy_url}/status", timeout=10)
            if response.status_code == 200:
                logger.info("ACA-Py连接成功")
            else:
                logger.warning(f"ACA-Py连接异常: {response.status_code}")
        except Exception as e:
            logger.error(f"ACA-Py连接失败: {e}")
    
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
                
                await asyncio.sleep(5)  # 每5秒检查一次
                
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
            
            # 颁发VC给用户
            await self.issue_cross_chain_vc(user_did, vc_data)
            
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
    
    async def issue_cross_chain_vc(self, user_did: str, vc_data: Dict):
        """通过ACA-Py颁发VC给用户"""
        try:
            # 这里简化处理，实际应该通过ACA-Py的API颁发VC
            # 由于ACA-Py的复杂性，这里只是记录日志
            logger.info(f"为DID {user_did} 颁发跨链VC")
            logger.info(f"VC内容: {json.dumps(vc_data, indent=2)}")
            
            # 实际实现中，这里应该调用ACA-Py的API
            # await self.call_acapy_issue_credential(user_did, vc_data)
            
        except Exception as e:
            logger.error(f"颁发跨链VC时出错: {e}")
    
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
    
    async def stop(self):
        """停止Oracle服务"""
        logger.info("正在停止Oracle服务...")
        self.running = False
    
    def get_status(self) -> Dict:
        """获取Oracle服务状态"""
        status = {
            "running": self.running,
            "chains_connected": len(self.chains),
            "acapy_connected": False,
            "timestamp": datetime.now().isoformat()
        }
        
        # 检查ACA-Py连接
        try:
            response = requests.get(f"{self.acapy_url}/status", timeout=5)
            status["acapy_connected"] = response.status_code == 200
        except:
            pass
        
        return status

async def main():
    """主函数"""
    logger.info("启动跨链Oracle服务...")
    
    # 创建Oracle实例
    oracle = CrossChainOracle()
    
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
