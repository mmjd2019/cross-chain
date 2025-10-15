#!/usr/bin/env python3
"""
真实事件监控Oracle服务
监控Besu链上的AssetLocked事件并实现真正的代币跨链转移
"""

import asyncio
import json
import logging
import time
import aiohttp
from datetime import datetime, timedelta
from web3 import Web3
from eth_account import Account
from web3_fixed_connection import FixedWeb3
import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('real_oracle.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RealEventMonitoringOracle:
    """真实事件监控Oracle服务"""
    
    def __init__(self, config_file: str = "cross_chain_config.json"):
        """初始化Oracle服务"""
        self.config = self.load_config(config_file)
        self.vc_config = self.load_vc_config()
        self.running = False
        self.chains = {}
        self.contracts = {}
        self.monitored_events = {}
        
        # 初始化Web3连接
        self.init_web3_connections()
        
        # 初始化ACA-Py连接
        self.init_acapy_connections()
        
        logger.info("真实事件监控Oracle服务初始化完成")
    
    def load_config(self, config_file: str):
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"配置文件 {config_file} 加载成功")
            return config
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            raise
    
    def load_vc_config(self):
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
                # 使用修复的Web3连接
                w3 = FixedWeb3(chain_config['rpc_url'], chain_config['name'])
                
                if w3.is_connected():
                    logger.info(f"链 {chain_config['name']} 连接成功")
                    
                    # 加载合约ABI
                    bridge_abi = self.load_contract_abi('CrossChainBridge.json')
                    verifier_abi = self.load_contract_abi('CrossChainDIDVerifier.json')
                    
                    # 创建合约实例
                    bridge_contract = w3.w3.eth.contract(
                        address=Web3.to_checksum_address(chain_config['bridge_address']),
                        abi=bridge_abi
                    )
                    verifier_contract = w3.w3.eth.contract(
                        address=Web3.to_checksum_address(chain_config['verifier_address']),
                        abi=verifier_abi
                    )
                    
                    self.chains[chain_config['chain_id']] = {
                        'web3': w3,
                        'config': chain_config,
                        'last_block': w3.get_latest_block().number if w3.get_latest_block() else 0
                    }
                    
                    self.contracts[chain_config['chain_id']] = {
                        'bridge': bridge_contract,
                        'verifier': verifier_contract
                    }
                else:
                    logger.error(f"链 {chain_config['name']} 连接失败")
                    
            except Exception as e:
                logger.error(f"链 {chain_config['name']} 初始化失败: {e}")
    
    def load_contract_abi(self, abi_file: str):
        """加载合约ABI"""
        try:
            with open(abi_file, 'r') as f:
                abi = json.load(f)
            return abi
        except Exception as e:
            logger.error(f"加载ABI文件 {abi_file} 失败: {e}")
            return []
    
    def init_acapy_connections(self):
        """初始化ACA-Py连接"""
        self.acapy_issuer_url = self.vc_config.get('acapy_services', {}).get('issuer', {}).get('admin_url', 'http://192.168.230.178:8080')
        self.acapy_holder_url = self.vc_config.get('acapy_services', {}).get('holder', {}).get('admin_url', 'http://192.168.230.178:8081')
        
        # 获取DID信息
        self.oracle_did = self.config.get('oracle', {}).get('oracle_did', 'DPvobytTtKvmyeRTJZYjsg')
        self.holder_did = 'YL2HDxkVL8qMrssaZbvtfH'
        
        logger.info(f"ACA-Py连接初始化完成 - 发行者: {self.acapy_issuer_url}, 持有者: {self.acapy_holder_url}")
    
    async def start(self):
        """启动Oracle服务"""
        self.running = True
        logger.info("真实事件监控Oracle服务启动")
        
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
        last_block = chain_info['last_block']
        
        logger.info(f"开始监控链 {chain_id} 的事件")
        
        while self.running:
            try:
                current_block = chain_info['web3'].eth.block_number
                
                if current_block > last_block:
                    logger.info(f"检测到链 {chain_id} 新区块: {last_block + 1} - {current_block}")
                    await self.process_new_blocks(chain_id, last_block + 1, current_block)
                    last_block = current_block
                    chain_info['last_block'] = current_block
                
                await asyncio.sleep(5)  # 每5秒检查一次
                
            except Exception as e:
                logger.error(f"监控链 {chain_id} 时出错: {e}")
                await asyncio.sleep(10)
    
    async def process_new_blocks(self, chain_id: str, from_block: int, to_block: int):
        """处理新区块中的事件"""
        try:
            bridge_contract = self.contracts[chain_id]['bridge']
            
            # 获取AssetLocked事件
            events = bridge_contract.events.AssetLocked.get_logs(
                fromBlock=from_block,
                toBlock=to_block
            )
            
            for event in events:
                await self.handle_asset_locked_event(chain_id, event)
                
        except Exception as e:
            logger.error(f"处理链 {chain_id} 区块事件时出错: {e}")
    
    async def handle_asset_locked_event(self, source_chain: str, event):
        """处理资产锁定事件"""
        event_args = event['args']
        
        logger.info(f"检测到链 {source_chain} 的资产锁定事件:")
        logger.info(f"  - 用户: {event_args['user']}")
        logger.info(f"  - 金额: {event_args['amount']}")
        logger.info(f"  - 代币地址: {event_args['tokenAddress']}")
        logger.info(f"  - 目标链: {event_args['targetChain']}")
        logger.info(f"  - 锁定ID: {event_args['lockId'].hex()}")
        logger.info(f"  - 交易哈希: {event['transactionHash'].hex()}")
        
        try:
            # 获取用户DID
            user_did = await self.get_user_did(source_chain, event_args['user'])
            if not user_did:
                logger.warning(f"用户 {event_args['user']} 在链 {source_chain} 上没有DID")
                return
            
            # 生成跨链VC
            vc_data = await self.generate_cross_chain_vc(
                source_chain=source_chain,
                target_chain=event_args['targetChain'],
                user_did=user_did,
                amount=event_args['amount'],
                token_address=event_args['tokenAddress'],
                lock_id=event_args['lockId'].hex(),
                tx_hash=event['transactionHash'].hex()
            )
            
            # 颁发VC给用户
            vc_result = await self.issue_cross_chain_vc(vc_data)
            
            if vc_result:
                logger.info(f"成功颁发跨链VC: {vc_result}")
                
                # 在目标链上记录跨链证明
                await self.record_proof_on_target_chain(
                    source_chain=source_chain,
                    target_chain=event_args['targetChain'],
                    user_did=user_did,
                    tx_hash=event['transactionHash'].hex(),
                    amount=event_args['amount'],
                    token_address=event_args['tokenAddress']
                )
            else:
                logger.error("VC颁发失败")
                
        except Exception as e:
            logger.error(f"处理资产锁定事件时出错: {e}")
    
    async def get_user_did(self, chain_id: str, user_address: str):
        """获取用户DID"""
        try:
            verifier_contract = self.contracts[chain_id]['verifier']
            user_did = verifier_contract.functions.didOfAddress(user_address).call()
            return user_did if user_did else None
        except Exception as e:
            logger.error(f"获取用户DID失败: {e}")
            return None
    
    async def generate_cross_chain_vc(self, **kwargs):
        """生成跨链可验证凭证数据"""
        expiry_time = datetime.now() + timedelta(hours=24)
        
        vc_data = {
            "source_chain": kwargs['source_chain'],
            "target_chain": kwargs['target_chain'],
            "amount": str(kwargs['amount']),
            "token_address": kwargs['token_address'],
            "lock_id": kwargs['lock_id'],
            "transaction_hash": kwargs['tx_hash'],
            "user_address": kwargs.get('user_address', ''),
            "expiry": expiry_time.isoformat(),
            "user_did": kwargs['user_did']
        }
        
        logger.info(f"生成跨链VC数据: {vc_data}")
        return vc_data
    
    async def issue_cross_chain_vc(self, vc_data):
        """颁发跨链可验证凭证"""
        try:
            # 获取连接
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
                    {"name": "expiry", "value": vc_data["expiry"]}
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
                    f"{self.acapy_issuer_url}/issue-credential/send",
                    json=credential_offer
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"跨链VC颁发成功: {result['credential_exchange_id']}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"跨链VC颁发失败: {response.status} - {error_text}")
                        return None
        
        except Exception as e:
            logger.error(f"颁发跨链VC时出错: {e}")
            return None
    
    async def get_or_create_connection(self):
        """获取或创建连接"""
        try:
            async with aiohttp.ClientSession() as session:
                # 检查现有连接
                async with session.get(f"{self.acapy_issuer_url}/connections") as response:
                    if response.status == 200:
                        connections = await response.json()
                        active_connections = [c for c in connections.get('results', []) if c.get('state') == 'active']
                        
                        if active_connections:
                            return active_connections[0]['connection_id']
            
            return None
        
        except Exception as e:
            logger.error(f"获取连接时出错: {e}")
            return None
    
    async def record_proof_on_target_chain(self, **kwargs):
        """在目标链上记录跨链证明"""
        target_chain = kwargs['target_chain']
        
        if target_chain not in self.contracts:
            logger.error(f"目标链 {target_chain} 未配置")
            return False
        
        try:
            verifier_contract = self.contracts[target_chain]['verifier']
            w3 = self.chains[target_chain]['web3']
            
            # 获取Oracle账户
            oracle_account = Account.from_key(self.config.get('oracle', {}).get('oracle_private_key', '0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a'))
            
            # 构建交易
            transaction = verifier_contract.functions.recordCrossChainProof(
                kwargs['user_did'],
                kwargs['source_chain'],
                target_chain,
                bytes.fromhex(kwargs['tx_hash'][2:]),  # 移除0x前缀
                kwargs['amount'],
                kwargs['token_address']
            ).build_transaction({
                'from': oracle_account.address,
                'gas': 300000,
                'gasPrice': w3.to_wei('50', 'gwei'),
                'nonce': w3.eth.get_transaction_count(oracle_account.address)
            })
            
            # 签名并发送交易
            signed_txn = w3.eth.account.sign_transaction(transaction, oracle_account.key)
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"跨链证明记录交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                logger.info(f"跨链证明在链 {target_chain} 上记录成功")
                return True
            else:
                logger.error(f"跨链证明记录失败")
                return False
                
        except Exception as e:
            logger.error(f"在目标链上记录跨链证明时出错: {e}")
            return False
    
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

async def main():
    """主函数"""
    oracle = RealEventMonitoringOracle()
    await oracle.start()

if __name__ == "__main__":
    asyncio.run(main())
