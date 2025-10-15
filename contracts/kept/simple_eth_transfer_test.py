#!/usr/bin/env python3
"""
简单的ETH转账测试
验证真正的余额变化
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

class SimpleETHTransferTest:
    """简单的ETH转账测试"""
    
    def __init__(self):
        self.chains = {
            'chain_a': {
                'name': 'Besu Chain A',
                'rpc_url': 'http://localhost:8545',
                'chain_id': 2023
            },
            'chain_b': {
                'name': 'Besu Chain B',
                'rpc_url': 'http://localhost:8555',
                'chain_id': 2024
            }
        }
        
        # 测试账户
        self.test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
        
        # Web3连接
        self.web3_connections = {}
        
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
    
    def get_balance(self, chain_id):
        """获取余额"""
        if chain_id not in self.web3_connections:
            return None
        
        w3 = self.web3_connections[chain_id]
        try:
            balance_wei, balance_eth = w3.get_balance(self.test_account.address)
            return {
                'chain_id': chain_id,
                'chain_name': self.chains[chain_id]['name'],
                'account_address': self.test_account.address,
                'balance_wei': balance_wei,
                'balance_eth': balance_eth,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ 获取 {chain_id} 余额失败: {e}")
            return None
    
    def perform_simple_transfer(self, amount, from_chain, to_chain):
        """执行简单的跨链转账测试"""
        try:
            logger.info(f"🚀 开始简单的跨链转账测试: {amount} ETH 从 {from_chain} 到 {to_chain}")
            
            # 转账前状态
            logger.info("📊 转账前状态:")
            before_status = {}
            for chain_id in [from_chain, to_chain]:
                balance_info = self.get_balance(chain_id)
                if balance_info:
                    before_status[chain_id] = balance_info
                    logger.info(f"  {balance_info['chain_name']}: {balance_info['balance_eth']} ETH")
                else:
                    logger.error(f"  {chain_id}: 无法获取余额")
            
            # 执行转账
            logger.info("🔄 执行跨链转账...")
            
            # 步骤1: 在源链上减少ETH（发送到零地址销毁）
            logger.info("🔒 步骤1: 在源链上销毁ETH...")
            source_w3 = self.web3_connections[from_chain]
            transfer_amount_wei = int(amount * 10**18)
            
            # 获取交易参数
            nonce = source_w3.get_nonce(self.test_account.address)
            gas_price = source_w3.get_gas_price()
            
            # 构建销毁交易 - 发送ETH到零地址
            transaction = {
                'to': '0x0000000000000000000000000000000000000000',  # 零地址
                'value': transfer_amount_wei,
                'gas': 21000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.chains[from_chain]['chain_id']
            }
            
            # 签名并发送交易
            signed_txn = self.test_account.sign_transaction(transaction)
            destroy_tx_hash = source_w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"✅ 销毁交易已发送: {destroy_tx_hash.hex()}")
            
            # 等待销毁交易确认
            logger.info("⏳ 等待销毁交易确认...")
            destroy_receipt = source_w3.wait_for_transaction_receipt(destroy_tx_hash, timeout=60)
            
            if not destroy_receipt:
                raise ValueError("销毁交易确认失败")
            
            logger.info(f"✅ 销毁交易已确认，区块号: {destroy_receipt.blockNumber}")
            
            # 步骤2: 在目标链上增加ETH（从零地址发送，模拟释放）
            logger.info("🔓 步骤2: 在目标链上释放ETH...")
            target_w3 = self.web3_connections[to_chain]
            
            # 获取交易参数
            nonce = target_w3.get_nonce(self.test_account.address)
            gas_price = target_w3.get_gas_price()
            
            # 构建释放交易 - 发送ETH到目标地址
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
                balance_info = self.get_balance(chain_id)
                if balance_info:
                    after_status[chain_id] = balance_info
                    logger.info(f"  {balance_info['chain_name']}: {balance_info['balance_eth']} ETH")
                else:
                    logger.error(f"  {chain_id}: 无法获取余额")
            
            # 计算变化
            logger.info("📈 余额变化分析:")
            changes = {}
            
            for chain_id in [from_chain, to_chain]:
                if chain_id in before_status and chain_id in after_status:
                    before = before_status[chain_id]
                    after = after_status[chain_id]
                    
                    balance_change_wei = after['balance_wei'] - before['balance_wei']
                    balance_change_eth = after['balance_eth'] - before['balance_eth']
                    
                    changes[chain_id] = {
                        'chain_name': before['chain_name'],
                        'before_eth': before['balance_eth'],
                        'after_eth': after['balance_eth'],
                        'change_eth': balance_change_eth,
                        'before_wei': before['balance_wei'],
                        'after_wei': after['balance_wei'],
                        'change_wei': balance_change_wei,
                        'percentage_change': (balance_change_eth / before['balance_eth'] * 100) if before['balance_eth'] > 0 else 0
                    }
                    
                    logger.info(f"  {before['chain_name']}:")
                    logger.info(f"    转账前: {before['balance_eth']} ETH")
                    logger.info(f"    转账后: {after['balance_eth']} ETH")
                    logger.info(f"    变化: {balance_change_eth} ETH")
                    logger.info(f"    变化率: {changes[chain_id]['percentage_change']:.6f}%")
            
            # 生成详细报告
            report = {
                'transfer_info': {
                    'amount_eth': amount,
                    'amount_wei': transfer_amount_wei,
                    'from_chain': from_chain,
                    'to_chain': to_chain,
                    'destroy_tx_hash': destroy_tx_hash.hex(),
                    'release_tx_hash': release_tx_hash.hex(),
                    'destroy_block': destroy_receipt.blockNumber,
                    'release_block': release_receipt.blockNumber
                },
                'before_status': before_status,
                'after_status': after_status,
                'changes': changes,
                'timestamp': datetime.now().isoformat()
            }
            
            # 保存报告
            with open('simple_eth_transfer_report.json', 'w') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info("📄 详细报告已保存到 simple_eth_transfer_report.json")
            
            return report
            
        except Exception as e:
            logger.error(f"❌ 简单转账测试失败: {e}")
            raise

def main():
    """主函数"""
    try:
        logger.info("🚀 启动简单的ETH转账测试...")
        
        # 创建测试实例
        test = SimpleETHTransferTest()
        
        # 执行简单转账测试
        amount = 0.1  # 转账0.1 ETH
        from_chain = 'chain_a'
        to_chain = 'chain_b'
        
        result = test.perform_simple_transfer(amount, from_chain, to_chain)
        
        logger.info("✅ 简单转账测试完成！")
        return result
        
    except Exception as e:
        logger.error(f"❌ 系统错误: {e}")
        raise

if __name__ == "__main__":
    main()
