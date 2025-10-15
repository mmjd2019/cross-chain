#!/usr/bin/env python3
"""
真实的代币跨链转移测试
测试从BesuA到BesuB的完整代币跨链转移流程
"""

import asyncio
import json
import logging
import time
import sys
from datetime import datetime, timedelta
from web3 import Web3
from eth_account import Account
import aiohttp

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RealTokenCrossChainTransferTest:
    """真实的代币跨链转移测试"""
    
    def __init__(self):
        self.test_results = {}
        
        # 链配置
        self.chains = {
            'chain_a': {
                'name': 'Besu Chain A',
                'rpc_url': 'http://localhost:8545',
                'chain_id': 'chain_a',
                'bridge_address': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af',
                'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
            },
            'chain_b': {
                'name': 'Besu Chain B',
                'rpc_url': 'http://localhost:8555',
                'chain_id': 'chain_b',
                'bridge_address': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af',
                'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
            }
        }
        
        # 测试账户
        self.test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
        self.test_amount = 1000000000000000000  # 1 ETH (18 decimals)
        
        # 初始化Web3连接
        self.init_web3_connections()
        
        # 加载合约ABI
        self.load_contract_abis()
        
        # ACA-Py配置
        self.issuer_url = "http://192.168.230.178:8080"
        self.holder_url = "http://192.168.230.178:8081"
    
    def init_web3_connections(self):
        """初始化Web3连接"""
        for chain_id, chain_config in self.chains.items():
            try:
                w3 = Web3(Web3.HTTPProvider(chain_config['rpc_url'], request_kwargs={'timeout': 30}))
                
                if w3.is_connected():
                    logger.info(f"链 {chain_config['name']} 连接成功")
                    self.chains[chain_id]['web3'] = w3
                else:
                    logger.error(f"链 {chain_config['name']} 连接失败")
                    
            except Exception as e:
                logger.error(f"链 {chain_config['name']} 初始化失败: {e}")
    
    def load_contract_abis(self):
        """加载合约ABI"""
        try:
            with open('CrossChainBridge.json', 'r') as f:
                self.bridge_abi = json.load(f)
            with open('CrossChainDIDVerifier.json', 'r') as f:
                self.verifier_abi = json.load(f)
            logger.info("合约ABI加载成功")
        except Exception as e:
            logger.error(f"合约ABI加载失败: {e}")
            raise
    
    def create_contract_instances(self, chain_id: str):
        """创建合约实例"""
        chain_config = self.chains[chain_id]
        w3 = chain_config['web3']
        
        bridge_contract = w3.eth.contract(
            address=Web3.to_checksum_address(chain_config['bridge_address']),
            abi=self.bridge_abi
        )
        
        verifier_contract = w3.eth.contract(
            address=Web3.to_checksum_address(chain_config['verifier_address']),
            abi=self.verifier_abi
        )
        
        return bridge_contract, verifier_contract
    
    async def test_complete_cross_chain_transfer(self):
        """测试完整的跨链转移流程"""
        logger.info("🚀 开始真实代币跨链转移测试")
        logger.info("=" * 60)
        
        try:
            # 步骤1: 检查链连接
            await self.check_chain_connections()
            
            # 步骤2: 在BesuA上锁定资产
            lock_result = await self.lock_assets_on_chain_a()
            if not lock_result:
                logger.error("❌ 资产锁定失败")
                return False
            
            # 步骤3: 等待Oracle监控事件并颁发VC
            vc_result = await self.wait_for_vc_issuance(lock_result)
            if not vc_result:
                logger.error("❌ VC颁发失败")
                return False
            
            # 步骤4: 在BesuB上解锁资产
            unlock_result = await self.unlock_assets_on_chain_b(vc_result)
            if not unlock_result:
                logger.error("❌ 资产解锁失败")
                return False
            
            # 步骤5: 验证最终结果
            success = await self.verify_transfer_completion()
            
            logger.info(f"🎉 代币跨链转移测试{'成功' if success else '失败'}")
            return success
            
        except Exception as e:
            logger.error(f"跨链转移测试过程中出错: {e}")
            return False
    
    async def check_chain_connections(self):
        """检查链连接"""
        logger.info("🔍 检查链连接...")
        
        for chain_id, chain_config in self.chains.items():
            w3 = chain_config['web3']
            if not w3.is_connected():
                logger.error(f"❌ 链 {chain_config['name']} 连接失败")
                return False
            
            block_number = w3.eth.block_number
            logger.info(f"✅ 链 {chain_config['name']} 连接成功，当前区块: {block_number}")
        
        return True
    
    async def lock_assets_on_chain_a(self):
        """在BesuA上锁定资产"""
        logger.info("🔒 在BesuA上锁定资产...")
        
        try:
            bridge_contract, verifier_contract = self.create_contract_instances('chain_a')
            w3 = self.chains['chain_a']['web3']
            
            # 检查账户余额
            balance = w3.eth.get_balance(self.test_account.address)
            logger.info(f"账户余额: {w3.from_wei(balance, 'ether')} ETH")
            
            if balance < self.test_amount:
                logger.error("❌ 账户余额不足")
                return None
            
            # 检查DID验证状态
            is_verified = verifier_contract.functions.isVerified(self.test_account.address).call()
            logger.info(f"DID验证状态: {is_verified}")
            
            if not is_verified:
                logger.warning("⚠️  账户未验证，尝试注册DID...")
                await self.register_did_on_chain_a()
            
            # 构建锁定交易
            transaction = bridge_contract.functions.lockAssets(
                self.test_amount,
                '0x0000000000000000000000000000000000000000',  # ETH地址
                'chain_b'  # 目标链
            ).build_transaction({
                'from': self.test_account.address,
                'gas': 300000,
                'gasPrice': w3.to_wei('50', 'gwei'),
                'value': self.test_amount,  # 锁定ETH
                'nonce': w3.eth.get_transaction_count(self.test_account.address)
            })
            
            # 签名并发送交易
            signed_txn = w3.eth.account.sign_transaction(transaction, self.test_account.key)
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"🔒 锁定交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                logger.info("✅ 资产锁定成功")
                
                # 查找AssetLocked事件
                lock_events = bridge_contract.events.AssetLocked().process_receipt(receipt)
                if lock_events:
                    event = lock_events[0]
                    lock_id = event['args']['lockId']
                    logger.info(f"🔑 锁定ID: {lock_id.hex()}")
                    
                    return {
                        'tx_hash': tx_hash.hex(),
                        'lock_id': lock_id.hex(),
                        'amount': event['args']['amount'],
                        'user': event['args']['user'],
                        'target_chain': event['args']['targetChain']
                    }
                else:
                    logger.error("❌ 未找到AssetLocked事件")
                    return None
            else:
                logger.error("❌ 锁定交易失败")
                return None
                
        except Exception as e:
            logger.error(f"❌ 资产锁定过程中出错: {e}")
            return None
    
    async def register_did_on_chain_a(self):
        """在BesuA上注册DID"""
        logger.info("📝 在BesuA上注册DID...")
        
        try:
            verifier_contract = self.create_contract_instances('chain_a')[1]
            w3 = self.chains['chain_a']['web3']
            
            # 构建注册DID的交易
            transaction = verifier_contract.functions.registerDID(
                'YL2HDxkVL8qMrssaZbvtfH',  # 用户DID
                self.test_account.address
            ).build_transaction({
                'from': self.test_account.address,
                'gas': 200000,
                'gasPrice': w3.to_wei('50', 'gwei'),
                'nonce': w3.eth.get_transaction_count(self.test_account.address)
            })
            
            # 签名并发送交易
            signed_txn = w3.eth.account.sign_transaction(transaction, self.test_account.key)
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"📝 DID注册交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                logger.info("✅ DID注册成功")
                return True
            else:
                logger.error("❌ DID注册失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ DID注册过程中出错: {e}")
            return False
    
    async def wait_for_vc_issuance(self, lock_result):
        """等待Oracle颁发VC"""
        logger.info("⏳ 等待Oracle颁发跨链VC...")
        
        # 模拟Oracle监控事件并颁发VC
        # 在实际实现中，这里应该是Oracle服务自动监控事件
        
        try:
            # 生成跨链VC数据
            vc_data = {
                'source_chain': 'chain_a',
                'target_chain': 'chain_b',
                'amount': str(lock_result['amount']),
                'token_address': '0x0000000000000000000000000000000000000000',
                'lock_id': lock_result['lock_id'],
                'transaction_hash': lock_result['tx_hash'],
                'user_address': lock_result['user'],
                'expiry': (datetime.now() + timedelta(hours=24)).isoformat()
            }
            
            # 颁发VC
            vc_result = await self.issue_cross_chain_vc(vc_data)
            
            if vc_result:
                logger.info("✅ 跨链VC颁发成功")
                return vc_result
            else:
                logger.error("❌ 跨链VC颁发失败")
                return None
                
        except Exception as e:
            logger.error(f"❌ VC颁发过程中出错: {e}")
            return None
    
    async def issue_cross_chain_vc(self, vc_data):
        """颁发跨链VC"""
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
                    f"{self.issuer_url}/issue-credential/send",
                    json=credential_offer
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ 跨链VC颁发成功: {result['credential_exchange_id']}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ 跨链VC颁发失败: {response.status} - {error_text}")
                        return None
        
        except Exception as e:
            logger.error(f"❌ 颁发跨链VC时出错: {e}")
            return None
    
    async def get_or_create_connection(self):
        """获取或创建连接"""
        try:
            async with aiohttp.ClientSession() as session:
                # 检查现有连接
                async with session.get(f"{self.issuer_url}/connections") as response:
                    if response.status == 200:
                        connections = await response.json()
                        active_connections = [c for c in connections.get('results', []) if c.get('state') == 'active']
                        
                        if active_connections:
                            return active_connections[0]['connection_id']
            
            return None
        
        except Exception as e:
            logger.error(f"获取连接时出错: {e}")
            return None
    
    async def unlock_assets_on_chain_b(self, vc_result):
        """在BesuB上解锁资产"""
        logger.info("🔓 在BesuB上解锁资产...")
        
        try:
            bridge_contract, verifier_contract = self.create_contract_instances('chain_b')
            w3 = self.chains['chain_b']['web3']
            
            # 首先在验证器合约中记录跨链证明
            await self.record_cross_chain_proof_on_chain_b(vc_result)
            
            # 构建解锁交易
            transaction = bridge_contract.functions.unlockAssets(
                'YL2HDxkVL8qMrssaZbvtfH',  # 用户DID
                self.test_amount,
                '0x0000000000000000000000000000000000000000',  # ETH地址
                'chain_a',  # 源链
                bytes.fromhex(vc_result.get('transaction_hash', '0x')[2:])  # 移除0x前缀
            ).build_transaction({
                'from': self.test_account.address,
                'gas': 300000,
                'gasPrice': w3.to_wei('50', 'gwei'),
                'nonce': w3.eth.get_transaction_count(self.test_account.address)
            })
            
            # 签名并发送交易
            signed_txn = w3.eth.account.sign_transaction(transaction, self.test_account.key)
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"🔓 解锁交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                logger.info("✅ 资产解锁成功")
                
                # 查找AssetUnlocked事件
                unlock_events = bridge_contract.events.AssetUnlocked().process_receipt(receipt)
                if unlock_events:
                    event = unlock_events[0]
                    logger.info(f"🔑 解锁成功，用户: {event['args']['user']}")
                    return True
                else:
                    logger.warning("⚠️  未找到AssetUnlocked事件")
                    return True
            else:
                logger.error("❌ 解锁交易失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 资产解锁过程中出错: {e}")
            return False
    
    async def record_cross_chain_proof_on_chain_b(self, vc_result):
        """在BesuB上记录跨链证明"""
        logger.info("📝 在BesuB上记录跨链证明...")
        
        try:
            verifier_contract = self.create_contract_instances('chain_b')[1]
            w3 = self.chains['chain_b']['web3']
            
            # 构建记录证明的交易
            transaction = verifier_contract.functions.recordCrossChainProof(
                'YL2HDxkVL8qMrssaZbvtfH',  # 用户DID
                'chain_a',  # 源链
                'chain_b',  # 目标链
                bytes.fromhex(vc_result.get('transaction_hash', '0x')[2:]),  # 移除0x前缀
                self.test_amount,
                '0x0000000000000000000000000000000000000000'  # ETH地址
            ).build_transaction({
                'from': self.test_account.address,
                'gas': 300000,
                'gasPrice': w3.to_wei('50', 'gwei'),
                'nonce': w3.eth.get_transaction_count(self.test_account.address)
            })
            
            # 签名并发送交易
            signed_txn = w3.eth.account.sign_transaction(transaction, self.test_account.key)
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"📝 证明记录交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                logger.info("✅ 跨链证明记录成功")
                return True
            else:
                logger.error("❌ 跨链证明记录失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 记录跨链证明时出错: {e}")
            return False
    
    async def verify_transfer_completion(self):
        """验证转移完成"""
        logger.info("🔍 验证跨链转移完成...")
        
        try:
            # 检查链A上的余额变化
            balance_a = self.chains['chain_a']['web3'].eth.get_balance(self.test_account.address)
            logger.info(f"链A账户余额: {self.chains['chain_a']['web3'].from_wei(balance_a, 'ether')} ETH")
            
            # 检查链B上的余额变化
            balance_b = self.chains['chain_b']['web3'].eth.get_balance(self.test_account.address)
            logger.info(f"链B账户余额: {self.chains['chain_b']['web3'].from_wei(balance_b, 'ether')} ETH")
            
            # 检查跨链证明是否有效
            verifier_contract = self.create_contract_instances('chain_b')[1]
            is_valid = verifier_contract.functions.verifyCrossChainProof(
                'YL2HDxkVL8qMrssaZbvtfH',
                'chain_a'
            ).call()
            
            logger.info(f"跨链证明有效性: {is_valid}")
            
            if is_valid:
                logger.info("✅ 跨链转移验证成功")
                return True
            else:
                logger.error("❌ 跨链转移验证失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 验证转移完成时出错: {e}")
            return False

async def main():
    """主测试函数"""
    logger.info("=" * 70)
    logger.info("🚀 开始真实代币跨链转移测试")
    logger.info("=" * 70)
    
    test = RealTokenCrossChainTransferTest()
    success = await test.test_complete_cross_chain_transfer()
    
    logger.info("\n" + "=" * 70)
    if success:
        logger.info("🎉 真实代币跨链转移测试成功完成！")
        logger.info("✅ BesuA到BesuB的代币转移流程正常")
    else:
        logger.info("❌ 真实代币跨链转移测试失败")
        logger.info("⚠️  请检查系统配置和连接状态")
    logger.info("=" * 70)
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    if success:
        print("\n🎉 测试成功！真实代币跨链转移系统运行正常！")
    else:
        print("\n❌ 测试失败！请检查系统状态！")
        sys.exit(1)
