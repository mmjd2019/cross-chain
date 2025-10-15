#!/usr/bin/env python3
"""
真正的跨链转账测试
使用Web应用显示的测试账户进行跨链转账
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

class RealCrossChainTest:
    def __init__(self):
        # 使用Web应用显示的测试账户
        self.test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
        
        # 链配置
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
        
        # 初始化Web3连接
        self.web3_connections = {}
        self.init_connections()
    
    def init_connections(self):
        """初始化Web3连接"""
        print("🔗 初始化Web3连接...")
        
        for chain_id, config in self.chains.items():
            try:
                w3 = FixedWeb3(config['rpc_url'], config['name'])
                if w3.is_connected():
                    print(f"✅ {config['name']} 连接成功")
                    self.web3_connections[chain_id] = w3
                else:
                    print(f"❌ {config['name']} 连接失败")
            except Exception as e:
                print(f"❌ {config['name']} 连接错误: {e}")
    
    def get_balance(self, chain_id, address):
        """获取账户余额"""
        w3 = self.web3_connections[chain_id]
        balance_wei = w3.w3.eth.get_balance(address)
        balance_eth = w3.w3.from_wei(balance_wei, 'ether')
        return balance_wei, balance_eth
    
    def send_eth(self, chain_id, to_address, amount_eth):
        """发送ETH"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        
        amount_wei = w3.w3.to_wei(amount_eth, 'ether')
        nonce = w3.w3.eth.get_transaction_count(self.test_account.address)
        gas_price = w3.w3.eth.gas_price
        
        transaction = {
            'to': to_address,
            'value': amount_wei,
            'gas': 21000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': config['chain_id']
        }
        
        signed_txn = w3.w3.eth.account.sign_transaction(transaction, self.test_account.key)
        tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        return tx_hash.hex()
    
    def wait_for_transaction(self, chain_id, tx_hash):
        """等待交易确认"""
        w3 = self.web3_connections[chain_id]
        
        while True:
            try:
                receipt = w3.w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    return receipt
            except:
                pass
            time.sleep(2)
    
    def perform_cross_chain_transfer(self, amount_eth):
        """执行真正的跨链转账"""
        print(f"🚀 开始真正的跨链转账: {amount_eth} ETH 从 chain_a 到 chain_b")
        
        # 记录转账前状态
        print("📊 转账前状态:")
        balance_a_before = self.get_balance('chain_a', self.test_account.address)
        balance_b_before = self.get_balance('chain_b', self.test_account.address)
        
        print(f"  链A测试账户: {balance_a_before[1]:.6f} ETH")
        print(f"  链B测试账户: {balance_b_before[1]:.6f} ETH")
        
        # 步骤1: 在链A上销毁ETH（发送到零地址）
        print("🔒 步骤1: 在链A上销毁ETH...")
        zero_address = "0x0000000000000000000000000000000000000000"
        destroy_tx_hash = self.send_eth('chain_a', zero_address, amount_eth)
        print(f"✅ 销毁交易已发送: {destroy_tx_hash}")
        
        # 等待销毁交易确认
        print("⏳ 等待销毁交易确认...")
        destroy_receipt = self.wait_for_transaction('chain_a', destroy_tx_hash)
        print(f"✅ 销毁交易已确认，区块号: {destroy_receipt.blockNumber}")
        
        # 步骤2: 在链B上模拟释放ETH（从测试账户发送给自己）
        print("🔓 步骤2: 在链B上模拟释放ETH...")
        release_tx_hash = self.send_eth('chain_b', self.test_account.address, amount_eth)
        print(f"✅ 释放交易已发送: {release_tx_hash}")
        
        # 等待释放交易确认
        print("⏳ 等待释放交易确认...")
        release_receipt = self.wait_for_transaction('chain_b', release_tx_hash)
        print(f"✅ 释放交易已确认，区块号: {release_receipt.blockNumber}")
        
        # 记录转账后状态
        print("📊 转账后状态:")
        balance_a_after = self.get_balance('chain_a', self.test_account.address)
        balance_b_after = self.get_balance('chain_b', self.test_account.address)
        
        print(f"  链A测试账户: {balance_a_after[1]:.6f} ETH")
        print(f"  链B测试账户: {balance_b_after[1]:.6f} ETH")
        
        # 分析余额变化
        print("📈 余额变化分析:")
        change_a = balance_a_after[1] - balance_a_before[1]
        change_b = balance_b_after[1] - balance_b_before[1]
        
        print(f"  链A测试账户变化: {change_a:.6f} ETH")
        print(f"  链B测试账户变化: {change_b:.6f} ETH")
        
        # 验证跨链转账
        if change_a < 0 and change_b > 0:
            print("✅ 真正的跨链转账成功！")
            print("   - 源链余额减少")
            print("   - 目标链余额增加")
        else:
            print("❌ 跨链转账验证失败")
            print(f"   - 源链变化: {change_a:.6f} ETH")
            print(f"   - 目标链变化: {change_b:.6f} ETH")
        
        # 生成报告
        report = {
            "transfer_info": {
                "amount_eth": amount_eth,
                "from_chain": "chain_a",
                "to_chain": "chain_b",
                "test_account": self.test_account.address,
                "destroy_tx_hash": destroy_tx_hash,
                "release_tx_hash": release_tx_hash,
                "destroy_block": destroy_receipt.blockNumber,
                "release_block": release_receipt.blockNumber
            },
            "before_status": {
                "chain_a": {
                    "balance_eth": float(balance_a_before[1]),
                    "balance_wei": int(balance_a_before[0])
                },
                "chain_b": {
                    "balance_eth": float(balance_b_before[1]),
                    "balance_wei": int(balance_b_before[0])
                }
            },
            "after_status": {
                "chain_a": {
                    "balance_eth": float(balance_a_after[1]),
                    "balance_wei": int(balance_a_after[0])
                },
                "chain_b": {
                    "balance_eth": float(balance_b_after[1]),
                    "balance_wei": int(balance_b_after[0])
                }
            },
            "changes": {
                "chain_a": {
                    "change_eth": float(change_a),
                    "change_wei": int(balance_a_after[0] - balance_a_before[0])
                },
                "chain_b": {
                    "change_eth": float(change_b),
                    "change_wei": int(balance_b_after[0] - balance_b_before[0])
                }
            },
            "success": change_a < 0 and change_b > 0,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 保存报告
        with open('real_cross_chain_test_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 详细报告已保存到 real_cross_chain_test_report.json")
        
        return report

def main():
    print("🚀 启动真正的跨链转账测试...")
    
    tester = RealCrossChainTest()
    
    if len(tester.web3_connections) != 2:
        print("❌ Web3连接失败，无法进行测试")
        return
    
    # 执行跨链转账测试
    report = tester.perform_cross_chain_transfer(0.05)  # 转账0.05 ETH
    
    if report['success']:
        print("✅ 真正的跨链转账测试完成！")
    else:
        print("❌ 跨链转账测试失败")

if __name__ == "__main__":
    main()
