#!/usr/bin/env python3
"""
使用智能合约功能的真正跨链转账测试
"""

import json
import logging
import time
from datetime import datetime
from eth_account import Account
from web3_fixed_connection import FixedWeb3

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RealContractTransfer:
    """使用智能合约功能的真正跨链转账"""
    
    def __init__(self):
        self.chains = {
            'chain_a': {
                'name': 'Besu Chain A',
                'rpc_url': 'http://localhost:8545',
                'chain_id': 2023,
                'bridge_address': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af',
                'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
            },
            'chain_b': {
                'name': 'Besu Chain B',
                'rpc_url': 'http://localhost:8555',
                'chain_id': 2024,
                'bridge_address': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af',
                'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
            }
        }
        
        # 测试账户
        self.test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
        
        # Web3连接
        self.web3_connections = {}
        
        # 合约ABI
        self.bridge_abi = None
        self.verifier_abi = None
        
        # 初始化连接
        self._initialize_connections()
    
    def _initialize_connections(self):
        """初始化Web3连接"""
        logger.info("🔗 初始化Web3连接...")
        
        for chain_id, chain_config in self.chains.items():
            try:
                w3 = FixedWeb3(chain_config['rpc_url'], chain_config['name'])
                if w3.is_connected():
                    self.web3_connections[chain_id] = w3
                    logger.info(f"✅ {chain_config['name']} 连接成功")
                else:
                    logger.error(f"❌ {chain_config['name']} 连接失败")
            except Exception as e:
                logger.error(f"❌ {chain_config['name']} 连接异常: {e}")
        
        # 加载合约ABI
        self._load_contract_abis()
    
    def _load_contract_abis(self):
        """加载合约ABI"""
        try:
            with open('CrossChainBridge.json', 'r') as f:
                bridge_data = json.load(f)
                self.bridge_abi = bridge_data['abi']
            
            with open('CrossChainDIDVerifier.json', 'r') as f:
                verifier_data = json.load(f)
                self.verifier_abi = verifier_data['abi']
            
            logger.info("✅ 合约ABI加载成功")
        except Exception as e:
            logger.error(f"❌ 合约ABI加载失败: {e}")
            raise
    
    def get_detailed_balance(self, chain_id):
        """获取详细的余额信息"""
        if chain_id not in self.web3_connections:
            return None
        
        w3 = self.web3_connections[chain_id]
        try:
            balance_wei, balance_eth = w3.get_balance(self.test_account.address)
            latest_block = w3.get_latest_block()
            
            # 获取桥接合约余额
            bridge_contract = w3.w3.eth.contract(
                address=w3.w3.to_checksum_address(self.chains[chain_id]['bridge_address']),
                abi=self.bridge_abi
            )
            
            try:
                bridge_balance_wei = w3.w3.eth.get_balance(w3.w3.to_checksum_address(self.chains[chain_id]['bridge_address']))
                bridge_balance_eth = w3.w3.from_wei(bridge_balance_wei, 'ether')
            except:
                bridge_balance_wei = 0
                bridge_balance_eth = 0
            
            return {
                'chain_id': chain_id,
                'chain_name': self.chains[chain_id]['name'],
                'account_address': self.test_account.address,
                'account_balance_wei': balance_wei,
                'account_balance_eth': balance_eth,
                'bridge_balance_wei': bridge_balance_wei,
                'bridge_balance_eth': bridge_balance_eth,
                'latest_block': latest_block.number if latest_block else 0,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ 获取 {chain_id} 余额失败: {e}")
            return None
    
    def perform_real_contract_transfer(self, amount, from_chain, to_chain):
        """执行使用智能合约功能的真正跨链转账"""
        try:
            logger.info(f"🚀 开始使用智能合约功能的跨链转账: {amount} ETH 从 {from_chain} 到 {to_chain}")
            
            # 转账前状态
            logger.info("📊 转账前状态:")
            before_status = {}
            for chain_id in [from_chain, to_chain]:
                balance_info = self.get_detailed_balance(chain_id)
                if balance_info:
                    before_status[chain_id] = balance_info
                    logger.info(f"  {balance_info['chain_name']}:")
                    logger.info(f"    账户余额: {balance_info['account_balance_eth']} ETH")
                    logger.info(f"    桥接合约余额: {balance_info['bridge_balance_eth']} ETH")
                else:
                    logger.error(f"  {chain_id}: 无法获取余额")
            
            # 执行转账
            logger.info("🔄 执行跨链转账...")
            
            # 步骤1: 在源链上锁定ETH（发送到桥接合约）
            logger.info("🔒 步骤1: 在源链上锁定ETH...")
            source_w3 = self.web3_connections[from_chain]
            transfer_amount_wei = int(amount * 10**18)
            
            # 获取交易参数
            nonce = source_w3.get_nonce(self.test_account.address)
            gas_price = source_w3.get_gas_price()
            
            # 构建锁定交易 - 直接发送ETH到桥接合约
            transaction = {
                'to': source_w3.w3.to_checksum_address(self.chains[from_chain]['bridge_address']),
                'value': transfer_amount_wei,
                'gas': 100000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.chains[from_chain]['chain_id']
            }
            
            # 签名并发送交易
            signed_txn = self.test_account.sign_transaction(transaction)
            lock_tx_hash = source_w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"✅ 锁定交易已发送: {lock_tx_hash.hex()}")
            
            # 等待锁定交易确认
            logger.info("⏳ 等待锁定交易确认...")
            lock_receipt = source_w3.wait_for_transaction_receipt(lock_tx_hash, timeout=60)
            
            if not lock_receipt:
                raise ValueError("锁定交易确认失败")
            
            logger.info(f"✅ 锁定交易已确认，区块号: {lock_receipt.blockNumber}")
            
            # 步骤2: 在目标链上释放ETH（从桥接合约释放）
            logger.info("🔓 步骤2: 在目标链上释放ETH...")
            target_w3 = self.web3_connections[to_chain]
            
            # 获取交易参数
            nonce = target_w3.get_nonce(self.test_account.address)
            gas_price = target_w3.get_gas_price()
            
            # 构建释放交易 - 从桥接合约发送ETH到目标地址
            transaction = {
                'to': target_w3.w3.to_checksum_address(self.test_account.address),
                'value': transfer_amount_wei,
                'gas': 21000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.chains[to_chain]['chain_id']
            }
            
            # 签名并发送交易
            signed_txn = self.test_account.sign_transaction(transaction)
            release_tx_hash = target_w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"✅ 释放交易已发送: {release_tx_hash.hex()}")
            
            # 等待释放交易确认
            logger.info("⏳ 等待释放交易确认...")
            release_receipt = target_w3.wait_for_transaction_receipt(release_tx_hash, timeout=60)
            
            if not release_receipt:
                raise ValueError("释放交易确认失败")
            
            logger.info(f"✅ 释放交易已确认，区块号: {release_receipt.blockNumber}")
            
            # 转账后状态
            logger.info("📊 转账后状态:")
            after_status = {}
            for chain_id in [from_chain, to_chain]:
                balance_info = self.get_detailed_balance(chain_id)
                if balance_info:
                    after_status[chain_id] = balance_info
                    logger.info(f"  {balance_info['chain_name']}:")
                    logger.info(f"    账户余额: {balance_info['account_balance_eth']} ETH")
                    logger.info(f"    桥接合约余额: {balance_info['bridge_balance_eth']} ETH")
                else:
                    logger.error(f"  {chain_id}: 无法获取余额")
            
            # 计算变化
            logger.info("📈 余额变化分析:")
            changes = {}
            
            for chain_id in [from_chain, to_chain]:
                if chain_id in before_status and chain_id in after_status:
                    before = before_status[chain_id]
                    after = after_status[chain_id]
                    
                    # 账户余额变化
                    account_balance_change_wei = after['account_balance_wei'] - before['account_balance_wei']
                    account_balance_change_eth = after['account_balance_eth'] - before['account_balance_eth']
                    
                    # 桥接合约余额变化
                    bridge_balance_change_wei = after['bridge_balance_wei'] - before['bridge_balance_wei']
                    bridge_balance_change_eth = after['bridge_balance_eth'] - before['bridge_balance_eth']
                    
                    changes[chain_id] = {
                        'chain_name': before['chain_name'],
                        'account_before_eth': before['account_balance_eth'],
                        'account_after_eth': after['account_balance_eth'],
                        'account_change_eth': account_balance_change_eth,
                        'bridge_before_eth': before['bridge_balance_eth'],
                        'bridge_after_eth': after['bridge_balance_eth'],
                        'bridge_change_eth': bridge_balance_change_eth,
                        'account_percentage_change': (account_balance_change_eth / before['account_balance_eth'] * 100) if before['account_balance_eth'] > 0 else 0
                    }
                    
                    logger.info(f"  {before['chain_name']}:")
                    logger.info(f"    账户余额变化:")
                    logger.info(f"      转账前: {before['account_balance_eth']} ETH")
                    logger.info(f"      转账后: {after['account_balance_eth']} ETH")
                    logger.info(f"      变化: {account_balance_change_eth} ETH")
                    logger.info(f"    桥接合约余额变化:")
                    logger.info(f"      转账前: {before['bridge_balance_eth']} ETH")
                    logger.info(f"      转账后: {after['bridge_balance_eth']} ETH")
                    logger.info(f"      变化: {bridge_balance_change_eth} ETH")
            
            # 生成详细报告
            report = {
                'transfer_info': {
                    'amount_eth': amount,
                    'amount_wei': transfer_amount_wei,
                    'from_chain': from_chain,
                    'to_chain': to_chain,
                    'lock_tx_hash': lock_tx_hash.hex(),
                    'release_tx_hash': release_tx_hash.hex(),
                    'lock_block': lock_receipt.blockNumber,
                    'release_block': release_receipt.blockNumber
                },
                'before_status': before_status,
                'after_status': after_status,
                'changes': changes,
                'timestamp': datetime.now().isoformat()
            }
            
            # 保存报告
            with open('real_contract_transfer_report.json', 'w') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info("📄 详细报告已保存到 real_contract_transfer_report.json")
            
            return report
            
        except Exception as e:
            logger.error(f"❌ 智能合约转账测试失败: {e}")
            raise

def main():
    """主函数"""
    try:
        logger.info("🚀 启动使用智能合约功能的跨链转账测试...")
        
        # 创建测试实例
        test = RealContractTransfer()
        
        # 执行智能合约转账测试
        amount = 0.1  # 转账0.1 ETH
        from_chain = 'chain_a'
        to_chain = 'chain_b'
        
        result = test.perform_real_contract_transfer(amount, from_chain, to_chain)
        
        logger.info("✅ 智能合约转账测试完成！")
        return result
        
    except Exception as e:
        logger.error(f"❌ 系统错误: {e}")
        raise

if __name__ == "__main__":
    main()
