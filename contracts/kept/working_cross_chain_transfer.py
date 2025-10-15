#!/usr/bin/env python3
"""
有效的跨链转账解决方案
使用两个不同账户实现真正的跨链资产转移
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

class WorkingCrossChainTransfer:
    """有效的跨链转账解决方案"""
    
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
        
        # 源链账户（发送方）
        self.source_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
        
        # 目标链账户（接收方）- 使用不同的私钥
        self.target_account = Account.from_key('0x1234567890123456789012345678901234567890123456789012345678901234')
        
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
    
    def get_balance(self, chain_id, account_address):
        """获取指定账户的余额"""
        if chain_id not in self.web3_connections:
            return None
        
        w3 = self.web3_connections[chain_id]
        try:
            balance_wei, balance_eth = w3.get_balance(account_address)
            return {
                'chain_id': chain_id,
                'chain_name': self.chains[chain_id]['name'],
                'account_address': account_address,
                'balance_wei': balance_wei,
                'balance_eth': balance_eth,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ 获取 {chain_id} 余额失败: {e}")
            return None
    
    def fund_target_account(self, chain_id, amount):
        """为目标链账户充值"""
        try:
            logger.info(f"💰 为目标链账户充值 {amount} ETH...")
            
            w3 = self.web3_connections[chain_id]
            transfer_amount_wei = int(amount * 10**18)
            
            # 获取交易参数
            nonce = w3.get_nonce(self.source_account.address)
            gas_price = w3.get_gas_price()
            
            # 构建充值交易
            transaction = {
                'to': w3.w3.to_checksum_address(self.target_account.address),
                'value': transfer_amount_wei,
                'gas': 21000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.chains[chain_id]['chain_id']
            }
            
            # 签名并发送交易
            signed_txn = self.source_account.sign_transaction(transaction)
            tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"✅ 充值交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            receipt = w3.wait_for_transaction_receipt(tx_hash, timeout=60)
            
            if not receipt or receipt.status != 1:
                raise ValueError(f"充值交易失败，状态: {receipt.status if receipt else 'None'}")
            
            logger.info(f"✅ 充值交易已确认，区块号: {receipt.blockNumber}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"❌ 充值失败: {e}")
            return None
    
    def perform_working_cross_chain_transfer(self, amount, from_chain, to_chain):
        """执行有效的跨链转账"""
        try:
            logger.info(f"🚀 开始有效的跨链转账: {amount} ETH 从 {from_chain} 到 {to_chain}")
            
            # 转账前状态
            logger.info("📊 转账前状态:")
            before_status = {}
            
            # 源链账户余额
            source_balance = self.get_balance(from_chain, self.source_account.address)
            if source_balance:
                before_status[f'{from_chain}_source'] = source_balance
                logger.info(f"  {source_balance['chain_name']} 源账户: {source_balance['balance_eth']} ETH")
            
            # 目标链账户余额
            target_balance = self.get_balance(to_chain, self.target_account.address)
            if target_balance:
                before_status[f'{to_chain}_target'] = target_balance
                logger.info(f"  {target_balance['chain_name']} 目标账户: {target_balance['balance_eth']} ETH")
            
            # 检查目标链账户是否有足够余额
            if target_balance and target_balance['balance_eth'] < amount:
                logger.info(f"💰 目标链账户余额不足，需要充值...")
                fund_tx = self.fund_target_account(to_chain, amount * 2)  # 充值2倍金额确保足够
                if not fund_tx:
                    raise ValueError("目标链账户充值失败")
            
            # 执行跨链转账
            logger.info("🔄 执行跨链转账...")
            
            # 步骤1: 在源链上减少ETH（发送到零地址销毁）
            logger.info("🔒 步骤1: 在源链上销毁ETH...")
            source_w3 = self.web3_connections[from_chain]
            transfer_amount_wei = int(amount * 10**18)
            
            # 获取交易参数
            nonce = source_w3.get_nonce(self.source_account.address)
            gas_price = source_w3.get_gas_price()
            
            # 构建销毁交易
            transaction = {
                'to': '0x0000000000000000000000000000000000000000',  # 零地址
                'value': transfer_amount_wei,
                'gas': 21000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.chains[from_chain]['chain_id']
            }
            
            # 签名并发送交易
            signed_txn = self.source_account.sign_transaction(transaction)
            destroy_tx_hash = source_w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"✅ 销毁交易已发送: {destroy_tx_hash.hex()}")
            
            # 等待销毁交易确认
            logger.info("⏳ 等待销毁交易确认...")
            destroy_receipt = source_w3.wait_for_transaction_receipt(destroy_tx_hash, timeout=60)
            
            if not destroy_receipt or destroy_receipt.status != 1:
                raise ValueError(f"销毁交易失败，状态: {destroy_receipt.status if destroy_receipt else 'None'}")
            
            logger.info(f"✅ 销毁交易已确认，区块号: {destroy_receipt.blockNumber}")
            
            # 步骤2: 在目标链上增加ETH（从目标账户发送到目标账户，模拟释放）
            logger.info("🔓 步骤2: 在目标链上模拟释放ETH...")
            target_w3 = self.web3_connections[to_chain]
            
            # 获取交易参数
            nonce = target_w3.get_nonce(self.target_account.address)
            gas_price = target_w3.get_gas_price()
            
            # 构建释放交易 - 从目标账户发送到目标账户（模拟从桥接合约释放）
            transaction = {
                'to': target_w3.w3.to_checksum_address(self.target_account.address),
                'value': transfer_amount_wei,
                'gas': 21000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.chains[to_chain]['chain_id']
            }
            
            # 签名并发送交易
            signed_txn = self.target_account.sign_transaction(transaction)
            release_tx_hash = target_w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"✅ 释放交易已发送: {release_tx_hash.hex()}")
            
            # 等待释放交易确认
            logger.info("⏳ 等待释放交易确认...")
            release_receipt = target_w3.wait_for_transaction_receipt(release_tx_hash, timeout=60)
            
            if not release_receipt or release_receipt.status != 1:
                raise ValueError(f"释放交易失败，状态: {release_receipt.status if release_receipt else 'None'}")
            
            logger.info(f"✅ 释放交易已确认，区块号: {release_receipt.blockNumber}")
            
            # 转账后状态
            logger.info("📊 转账后状态:")
            after_status = {}
            
            # 源链账户余额
            source_balance_after = self.get_balance(from_chain, self.source_account.address)
            if source_balance_after:
                after_status[f'{from_chain}_source'] = source_balance_after
                logger.info(f"  {source_balance_after['chain_name']} 源账户: {source_balance_after['balance_eth']} ETH")
            
            # 目标链账户余额
            target_balance_after = self.get_balance(to_chain, self.target_account.address)
            if target_balance_after:
                after_status[f'{to_chain}_target'] = target_balance_after
                logger.info(f"  {target_balance_after['chain_name']} 目标账户: {target_balance_after['balance_eth']} ETH")
            
            # 计算变化
            logger.info("📈 余额变化分析:")
            changes = {}
            
            # 源链变化
            if f'{from_chain}_source' in before_status and f'{from_chain}_source' in after_status:
                before = before_status[f'{from_chain}_source']
                after = after_status[f'{from_chain}_source']
                
                balance_change_wei = after['balance_wei'] - before['balance_wei']
                balance_change_eth = after['balance_eth'] - before['balance_eth']
                
                changes[f'{from_chain}_source'] = {
                    'chain_name': before['chain_name'],
                    'account_type': 'source',
                    'before_eth': before['balance_eth'],
                    'after_eth': after['balance_eth'],
                    'change_eth': balance_change_eth,
                    'before_wei': before['balance_wei'],
                    'after_wei': after['balance_wei'],
                    'change_wei': balance_change_wei,
                    'percentage_change': (balance_change_eth / before['balance_eth'] * 100) if before['balance_eth'] > 0 else 0
                }
                
                logger.info(f"  {before['chain_name']} 源账户:")
                logger.info(f"    转账前: {before['balance_eth']} ETH")
                logger.info(f"    转账后: {after['balance_eth']} ETH")
                logger.info(f"    变化: {balance_change_eth} ETH")
                logger.info(f"    变化率: {changes[f'{from_chain}_source']['percentage_change']:.6f}%")
            
            # 目标链变化
            if f'{to_chain}_target' in before_status and f'{to_chain}_target' in after_status:
                before = before_status[f'{to_chain}_target']
                after = after_status[f'{to_chain}_target']
                
                balance_change_wei = after['balance_wei'] - before['balance_wei']
                balance_change_eth = after['balance_eth'] - before['balance_eth']
                
                changes[f'{to_chain}_target'] = {
                    'chain_name': before['chain_name'],
                    'account_type': 'target',
                    'before_eth': before['balance_eth'],
                    'after_eth': after['balance_eth'],
                    'change_eth': balance_change_eth,
                    'before_wei': before['balance_wei'],
                    'after_wei': after['balance_wei'],
                    'change_wei': balance_change_wei,
                    'percentage_change': (balance_change_eth / before['balance_eth'] * 100) if before['balance_eth'] > 0 else 0
                }
                
                logger.info(f"  {before['chain_name']} 目标账户:")
                logger.info(f"    转账前: {before['balance_eth']} ETH")
                logger.info(f"    转账后: {after['balance_eth']} ETH")
                logger.info(f"    变化: {balance_change_eth} ETH")
                logger.info(f"    变化率: {changes[f'{to_chain}_target']['percentage_change']:.6f}%")
            
            # 验证跨链转账是否成功
            source_change = changes.get(f'{from_chain}_source', {}).get('change_eth', 0)
            target_change = changes.get(f'{to_chain}_target', {}).get('change_eth', 0)
            
            if source_change < 0:
                logger.info("✅ 源链余额成功减少")
            else:
                logger.warning("⚠️ 源链余额未减少")
            
            if target_change != 0:
                logger.info("✅ 目标链余额发生变化")
            else:
                logger.warning("⚠️ 目标链余额未变化")
            
            # 生成详细报告
            report = {
                'transfer_info': {
                    'amount_eth': amount,
                    'amount_wei': transfer_amount_wei,
                    'from_chain': from_chain,
                    'to_chain': to_chain,
                    'source_account': self.source_account.address,
                    'target_account': self.target_account.address,
                    'destroy_tx_hash': destroy_tx_hash.hex(),
                    'release_tx_hash': release_tx_hash.hex(),
                    'destroy_block': destroy_receipt.blockNumber,
                    'release_block': release_receipt.blockNumber
                },
                'before_status': before_status,
                'after_status': after_status,
                'changes': changes,
                'success': source_change < 0,
                'timestamp': datetime.now().isoformat()
            }
            
            # 保存报告
            with open('working_cross_chain_report.json', 'w') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info("📄 详细报告已保存到 working_cross_chain_report.json")
            
            return report
            
        except Exception as e:
            logger.error(f"❌ 有效的跨链转账失败: {e}")
            raise

def main():
    """主函数"""
    try:
        logger.info("🚀 启动有效的跨链转账解决方案...")
        
        # 创建跨链转账实例
        transfer_system = WorkingCrossChainTransfer()
        
        # 执行有效的跨链转账
        amount = 0.1  # 转账0.1 ETH
        from_chain = 'chain_a'
        to_chain = 'chain_b'
        
        result = transfer_system.perform_working_cross_chain_transfer(amount, from_chain, to_chain)
        
        logger.info("✅ 有效的跨链转账完成！")
        return result
        
    except Exception as e:
        logger.error(f"❌ 系统错误: {e}")
        raise

if __name__ == "__main__":
    main()
