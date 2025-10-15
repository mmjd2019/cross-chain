#!/usr/bin/env python3
"""
修复的资产锁定测试
测试在BesuA上锁定资产的基本功能
"""

import json
import logging
import time
from web3 import Web3
from eth_account import Account

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FixedAssetLockingTest:
    """修复的资产锁定测试"""
    
    def __init__(self):
        # 链配置
        self.chain_a = {
            'name': 'Besu Chain A',
            'rpc_url': 'http://localhost:8545',
            'bridge_address': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af',
            'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
        }
        
        # 测试账户
        self.test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
        self.test_amount = 1000000000000000000  # 1 ETH (18 decimals)
        
        # 初始化Web3连接
        self.w3 = Web3(Web3.HTTPProvider(self.chain_a['rpc_url'], request_kwargs={'timeout': 30}))
        
        # 加载合约ABI
        self.load_contract_abis()
        
        # 创建合约实例
        self.create_contract_instances()
    
    def load_contract_abis(self):
        """加载合约ABI"""
        try:
            # 加载桥合约ABI
            with open('CrossChainBridge.json', 'r') as f:
                bridge_data = json.load(f)
                self.bridge_abi = bridge_data['abi']
            
            # 加载验证器合约ABI
            with open('CrossChainDIDVerifier.json', 'r') as f:
                verifier_data = json.load(f)
                self.verifier_abi = verifier_data['abi']
            
            logger.info("合约ABI加载成功")
        except Exception as e:
            logger.error(f"合约ABI加载失败: {e}")
            raise
    
    def create_contract_instances(self):
        """创建合约实例"""
        self.bridge_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.chain_a['bridge_address']),
            abi=self.bridge_abi
        )
        
        self.verifier_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.chain_a['verifier_address']),
            abi=self.verifier_abi
        )
    
    def test_chain_connection(self):
        """测试链连接"""
        logger.info("🔍 测试Besu链A连接...")
        
        if not self.w3.is_connected():
            logger.error("❌ 链连接失败")
            return False
        
        block_number = self.w3.eth.block_number
        logger.info(f"✅ 链连接成功，当前区块: {block_number}")
        return True
    
    def test_account_balance(self):
        """测试账户余额"""
        logger.info("💰 检查测试账户余额...")
        
        balance = self.w3.eth.get_balance(self.test_account.address)
        balance_eth = self.w3.from_wei(balance, 'ether')
        
        logger.info(f"账户地址: {self.test_account.address}")
        logger.info(f"账户余额: {balance_eth} ETH")
        
        if balance < self.test_amount:
            logger.error(f"❌ 账户余额不足，需要至少 {self.w3.from_wei(self.test_amount, 'ether')} ETH")
            return False
        
        logger.info("✅ 账户余额充足")
        return True
    
    def test_contract_functions(self):
        """测试合约函数调用"""
        logger.info("🔧 测试合约函数调用...")
        
        try:
            # 测试桥合约的owner函数
            owner = self.bridge_contract.functions.owner().call()
            logger.info(f"桥合约所有者: {owner}")
            
            # 测试桥合约的chainId函数
            chain_id = self.bridge_contract.functions.chainId().call()
            logger.info(f"桥合约链ID: {chain_id}")
            
            # 测试验证器合约的owner函数
            verifier_owner = self.verifier_contract.functions.owner().call()
            logger.info(f"验证器合约所有者: {verifier_owner}")
            
            logger.info("✅ 合约函数调用成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 合约函数调用失败: {e}")
            return False
    
    def test_did_verification(self):
        """测试DID验证状态"""
        logger.info("🔐 检查DID验证状态...")
        
        try:
            is_verified = self.verifier_contract.functions.isVerified(self.test_account.address).call()
            logger.info(f"DID验证状态: {is_verified}")
            
            if not is_verified:
                logger.warning("⚠️  账户未验证，需要先注册DID")
                return False
            
            logger.info("✅ DID验证通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 检查DID验证状态失败: {e}")
            return False
    
    def register_did(self):
        """注册DID"""
        logger.info("📝 注册DID...")
        
        try:
            # 构建注册DID的交易
            transaction = self.verifier_contract.functions.registerDID(
                'YL2HDxkVL8qMrssaZbvtfH',  # 用户DID
                self.test_account.address
            ).build_transaction({
                'from': self.test_account.address,
                'gas': 200000,
                'gasPrice': self.w3.to_wei('50', 'gwei'),
                'nonce': self.w3.eth.get_transaction_count(self.test_account.address)
            })
            
            # 签名并发送交易
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.test_account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"📝 DID注册交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                logger.info("✅ DID注册成功")
                return True
            else:
                logger.error("❌ DID注册失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ DID注册过程中出错: {e}")
            return False
    
    def test_asset_locking(self):
        """测试资产锁定"""
        logger.info("🔒 测试资产锁定...")
        
        try:
            # 构建锁定交易
            transaction = self.bridge_contract.functions.lockAssets(
                self.test_amount,
                '0x0000000000000000000000000000000000000000',  # ETH地址
                'chain_b'  # 目标链
            ).build_transaction({
                'from': self.test_account.address,
                'gas': 300000,
                'gasPrice': self.w3.to_wei('50', 'gwei'),
                'value': self.test_amount,  # 锁定ETH
                'nonce': self.w3.eth.get_transaction_count(self.test_account.address)
            })
            
            logger.info(f"锁定金额: {self.w3.from_wei(self.test_amount, 'ether')} ETH")
            logger.info(f"目标链: chain_b")
            
            # 签名并发送交易
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.test_account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"🔒 锁定交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                logger.info("✅ 资产锁定成功")
                
                # 查找AssetLocked事件
                lock_events = self.bridge_contract.events.AssetLocked().process_receipt(receipt)
                if lock_events:
                    event = lock_events[0]
                    lock_id = event['args']['lockId']
                    logger.info(f"🔑 锁定ID: {lock_id.hex()}")
                    logger.info(f"用户: {event['args']['user']}")
                    logger.info(f"金额: {event['args']['amount']}")
                    logger.info(f"目标链: {event['args']['targetChain']}")
                    
                    return {
                        'success': True,
                        'tx_hash': tx_hash.hex(),
                        'lock_id': lock_id.hex(),
                        'amount': event['args']['amount'],
                        'user': event['args']['user'],
                        'target_chain': event['args']['targetChain']
                    }
                else:
                    logger.error("❌ 未找到AssetLocked事件")
                    return {'success': False, 'error': '未找到AssetLocked事件'}
            else:
                logger.error("❌ 锁定交易失败")
                return {'success': False, 'error': '锁定交易失败'}
                
        except Exception as e:
            logger.error(f"❌ 资产锁定过程中出错: {e}")
            return {'success': False, 'error': str(e)}
    
    def run_complete_test(self):
        """运行完整测试"""
        logger.info("🚀 开始修复的资产锁定测试")
        logger.info("=" * 50)
        
        test_results = {}
        
        # 1. 测试链连接
        test_results['chain_connection'] = self.test_chain_connection()
        if not test_results['chain_connection']:
            logger.error("❌ 链连接测试失败，停止测试")
            return False
        
        # 2. 测试账户余额
        test_results['account_balance'] = self.test_account_balance()
        if not test_results['account_balance']:
            logger.error("❌ 账户余额测试失败，停止测试")
            return False
        
        # 3. 测试合约函数
        test_results['contract_functions'] = self.test_contract_functions()
        if not test_results['contract_functions']:
            logger.error("❌ 合约函数测试失败，停止测试")
            return False
        
        # 4. 测试DID验证状态
        test_results['did_verification'] = self.test_did_verification()
        if not test_results['did_verification']:
            logger.warning("⚠️  DID验证失败，尝试注册DID...")
            test_results['did_registration'] = self.register_did()
            if not test_results['did_registration']:
                logger.error("❌ DID注册失败，停止测试")
                return False
        
        # 5. 测试资产锁定
        test_results['asset_locking'] = self.test_asset_locking()
        
        # 生成测试报告
        self.generate_test_report(test_results)
        
        return test_results['asset_locking'].get('success', False)
    
    def generate_test_report(self, test_results):
        """生成测试报告"""
        logger.info("\n" + "=" * 50)
        logger.info("📊 测试结果汇总")
        logger.info("=" * 50)
        
        for test_name, result in test_results.items():
            if isinstance(result, bool):
                status = "✅ 成功" if result else "❌ 失败"
            elif isinstance(result, dict):
                status = "✅ 成功" if result.get('success', False) else "❌ 失败"
            else:
                status = "❓ 未知"
            
            logger.info(f"  {test_name}: {status}")
        
        # 保存详细结果
        with open('fixed_asset_locking_test_results.json', 'w') as f:
            json.dump(test_results, f, indent=2, default=str)
        
        logger.info("📄 详细结果已保存到: fixed_asset_locking_test_results.json")

def main():
    """主函数"""
    test = FixedAssetLockingTest()
    success = test.run_complete_test()
    
    if success:
        print("\n🎉 资产锁定测试成功！")
        return 0
    else:
        print("\n❌ 资产锁定测试失败！")
        return 1

if __name__ == "__main__":
    exit(main())
