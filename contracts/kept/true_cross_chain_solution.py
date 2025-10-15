#!/usr/bin/env python3
"""
真正的跨链转账解决方案
使用智能合约实现真正的跨链资产转移
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

class TrueCrossChainSolution:
    def __init__(self):
        # 使用Web应用显示的测试账户
        self.test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
        
        # 链配置
        self.chains = {
            'chain_a': {
                'name': 'Besu Chain A',
                'rpc_url': 'http://localhost:8545',
                'chain_id': 2023,
                'bridge_address': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af'
            },
            'chain_b': {
                'name': 'Besu Chain B', 
                'rpc_url': 'http://localhost:8555',
                'chain_id': 2024,
                'bridge_address': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af'
            }
        }
        
        # 初始化Web3连接
        self.web3_connections = {}
        self.bridge_contracts = {}
        self.init_connections()
    
    def init_connections(self):
        """初始化Web3连接和合约"""
        print("🔗 初始化Web3连接和智能合约...")
        
        for chain_id, config in self.chains.items():
            try:
                w3 = FixedWeb3(config['rpc_url'], config['name'])
                if w3.is_connected():
                    print(f"✅ {config['name']} 连接成功")
                    self.web3_connections[chain_id] = w3
                    
                    # 加载桥接合约ABI
                    try:
                        with open('CrossChainBridge.json', 'r') as f:
                            bridge_abi = json.load(f)['abi']
                        
                        # 创建合约实例
                        bridge_contract = w3.w3.eth.contract(
                            address=w3.w3.to_checksum_address(config['bridge_address']),
                            abi=bridge_abi
                        )
                        self.bridge_contracts[chain_id] = bridge_contract
                        print(f"✅ {config['name']} 桥接合约加载成功")
                        
                    except Exception as e:
                        print(f"❌ {config['name']} 桥接合约加载失败: {e}")
                        self.bridge_contracts[chain_id] = None
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
    
    def get_bridge_balance(self, chain_id):
        """获取桥接合约余额"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        bridge_address = w3.w3.to_checksum_address(config['bridge_address'])
        balance_wei = w3.w3.eth.get_balance(bridge_address)
        balance_eth = w3.w3.from_wei(balance_wei, 'ether')
        return balance_wei, balance_eth
    
    def call_lock_assets(self, chain_id, amount_eth, target_chain):
        """调用lockAssets函数锁定资产"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        bridge_contract = self.bridge_contracts[chain_id]
        
        if not bridge_contract:
            raise Exception("桥接合约未加载")
        
        amount_wei = w3.w3.to_wei(amount_eth, 'ether')
        nonce = w3.w3.eth.get_transaction_count(self.test_account.address)
        gas_price = w3.w3.eth.gas_price
        
        # 构建交易
        transaction = bridge_contract.functions.lockAssets(
            amount_wei,
            "0x0000000000000000000000000000000000000000",  # ETH地址
            target_chain
        ).build_transaction({
            'from': self.test_account.address,
            'gas': 200000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': config['chain_id'],
            'value': amount_wei  # 发送ETH到合约
        })
        
        # 签名并发送交易
        signed_txn = w3.w3.eth.account.sign_transaction(transaction, self.test_account.key)
        tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        return tx_hash.hex()
    
    def call_unlock_assets(self, chain_id, user_did, amount_eth, source_chain, source_tx_hash):
        """调用unlockAssets函数解锁资产"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        bridge_contract = self.bridge_contracts[chain_id]
        
        if not bridge_contract:
            raise Exception("桥接合约未加载")
        
        amount_wei = w3.w3.to_wei(amount_eth, 'ether')
        nonce = w3.w3.eth.get_transaction_count(self.test_account.address)
        gas_price = w3.w3.eth.gas_price
        
        # 构建交易
        transaction = bridge_contract.functions.unlockAssets(
            user_did,
            amount_wei,
            "0x0000000000000000000000000000000000000000",  # ETH地址
            source_chain,
            source_tx_hash
        ).build_transaction({
            'from': self.test_account.address,
            'gas': 200000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': config['chain_id']
        })
        
        # 签名并发送交易
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
    
    def perform_true_cross_chain_transfer(self, amount_eth):
        """执行真正的跨链转账"""
        print(f"🚀 开始真正的跨链转账: {amount_eth} ETH 从 chain_a 到 chain_b")
        
        # 记录转账前状态
        print("📊 转账前状态:")
        balance_a_before = self.get_balance('chain_a', self.test_account.address)
        balance_b_before = self.get_balance('chain_b', self.test_account.address)
        bridge_a_before = self.get_bridge_balance('chain_a')
        bridge_b_before = self.get_bridge_balance('chain_b')
        
        print(f"  链A测试账户: {balance_a_before[1]:.6f} ETH")
        print(f"  链B测试账户: {balance_b_before[1]:.6f} ETH")
        print(f"  链A桥接合约: {bridge_a_before[1]:.6f} ETH")
        print(f"  链B桥接合约: {bridge_b_before[1]:.6f} ETH")
        
        # 步骤1: 在链A上锁定资产
        print("🔒 步骤1: 在链A上锁定资产...")
        try:
            lock_tx_hash = self.call_lock_assets('chain_a', amount_eth, 'chain_b')
            print(f"✅ 锁定交易已发送: {lock_tx_hash}")
            
            # 等待锁定交易确认
            print("⏳ 等待锁定交易确认...")
            lock_receipt = self.wait_for_transaction('chain_a', lock_tx_hash)
            print(f"✅ 锁定交易已确认，区块号: {lock_receipt.blockNumber}")
            print(f"   交易状态: {lock_receipt.status}")
            
            if lock_receipt.status == 0:
                print("❌ 锁定交易失败")
                return False
                
        except Exception as e:
            print(f"❌ 锁定资产失败: {e}")
            return False
        
        # 步骤2: 在链B上解锁资产
        print("🔓 步骤2: 在链B上解锁资产...")
        try:
            # 生成用户DID（简化版本）
            user_did = f"did:example:{self.test_account.address}"
            
            unlock_tx_hash = self.call_unlock_assets(
                'chain_b', 
                user_did, 
                amount_eth, 
                'chain_a', 
                lock_tx_hash
            )
            print(f"✅ 解锁交易已发送: {unlock_tx_hash}")
            
            # 等待解锁交易确认
            print("⏳ 等待解锁交易确认...")
            unlock_receipt = self.wait_for_transaction('chain_b', unlock_tx_hash)
            print(f"✅ 解锁交易已确认，区块号: {unlock_receipt.blockNumber}")
            print(f"   交易状态: {unlock_receipt.status}")
            
            if unlock_receipt.status == 0:
                print("❌ 解锁交易失败")
                return False
                
        except Exception as e:
            print(f"❌ 解锁资产失败: {e}")
            return False
        
        # 记录转账后状态
        print("📊 转账后状态:")
        balance_a_after = self.get_balance('chain_a', self.test_account.address)
        balance_b_after = self.get_balance('chain_b', self.test_account.address)
        bridge_a_after = self.get_bridge_balance('chain_a')
        bridge_b_after = self.get_bridge_balance('chain_b')
        
        print(f"  链A测试账户: {balance_a_after[1]:.6f} ETH")
        print(f"  链B测试账户: {balance_b_after[1]:.6f} ETH")
        print(f"  链A桥接合约: {bridge_a_after[1]:.6f} ETH")
        print(f"  链B桥接合约: {bridge_b_after[1]:.6f} ETH")
        
        # 分析余额变化
        print("📈 余额变化分析:")
        change_a = balance_a_after[1] - balance_a_before[1]
        change_b = balance_b_after[1] - balance_b_before[1]
        change_bridge_a = bridge_a_after[1] - bridge_a_before[1]
        change_bridge_b = bridge_b_after[1] - bridge_b_before[1]
        
        print(f"  链A测试账户变化: {change_a:.6f} ETH")
        print(f"  链B测试账户变化: {change_b:.6f} ETH")
        print(f"  链A桥接合约变化: {change_bridge_a:.6f} ETH")
        print(f"  链B桥接合约变化: {change_bridge_b:.6f} ETH")
        
        # 验证跨链转账
        success = (change_a < 0 and change_b > 0) or (change_bridge_a > 0 and change_bridge_b < 0)
        
        if success:
            print("✅ 真正的跨链转账成功！")
            if change_a < 0 and change_b > 0:
                print("   - 源链账户余额减少")
                print("   - 目标链账户余额增加")
            elif change_bridge_a > 0 and change_bridge_b < 0:
                print("   - 源链桥接合约余额增加")
                print("   - 目标链桥接合约余额减少")
        else:
            print("❌ 跨链转账验证失败")
            print(f"   - 源链账户变化: {change_a:.6f} ETH")
            print(f"   - 目标链账户变化: {change_b:.6f} ETH")
            print(f"   - 源链桥接合约变化: {change_bridge_a:.6f} ETH")
            print(f"   - 目标链桥接合约变化: {change_bridge_b:.6f} ETH")
        
        # 生成报告
        report = {
            "transfer_info": {
                "amount_eth": amount_eth,
                "from_chain": "chain_a",
                "to_chain": "chain_b",
                "test_account": self.test_account.address,
                "lock_tx_hash": lock_tx_hash,
                "unlock_tx_hash": unlock_tx_hash,
                "lock_block": lock_receipt.blockNumber,
                "unlock_block": unlock_receipt.blockNumber,
                "lock_status": lock_receipt.status,
                "unlock_status": unlock_receipt.status
            },
            "before_status": {
                "chain_a_account": {
                    "balance_eth": float(balance_a_before[1]),
                    "balance_wei": int(balance_a_before[0])
                },
                "chain_b_account": {
                    "balance_eth": float(balance_b_before[1]),
                    "balance_wei": int(balance_b_before[0])
                },
                "chain_a_bridge": {
                    "balance_eth": float(bridge_a_before[1]),
                    "balance_wei": int(bridge_a_before[0])
                },
                "chain_b_bridge": {
                    "balance_eth": float(bridge_b_before[1]),
                    "balance_wei": int(bridge_b_before[0])
                }
            },
            "after_status": {
                "chain_a_account": {
                    "balance_eth": float(balance_a_after[1]),
                    "balance_wei": int(balance_a_after[0])
                },
                "chain_b_account": {
                    "balance_eth": float(balance_b_after[1]),
                    "balance_wei": int(balance_b_after[0])
                },
                "chain_a_bridge": {
                    "balance_eth": float(bridge_a_after[1]),
                    "balance_wei": int(bridge_a_after[0])
                },
                "chain_b_bridge": {
                    "balance_eth": float(bridge_b_after[1]),
                    "balance_wei": int(bridge_b_after[0])
                }
            },
            "changes": {
                "chain_a_account": {
                    "change_eth": float(change_a),
                    "change_wei": int(balance_a_after[0] - balance_a_before[0])
                },
                "chain_b_account": {
                    "change_eth": float(change_b),
                    "change_wei": int(balance_b_after[0] - balance_b_before[0])
                },
                "chain_a_bridge": {
                    "change_eth": float(change_bridge_a),
                    "change_wei": int(bridge_a_after[0] - bridge_a_before[0])
                },
                "chain_b_bridge": {
                    "change_eth": float(change_bridge_b),
                    "change_wei": int(bridge_b_after[0] - bridge_b_before[0])
                }
            },
            "success": success,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 保存报告
        with open('true_cross_chain_solution_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 详细报告已保存到 true_cross_chain_solution_report.json")
        
        return success

def main():
    print("🚀 启动真正的跨链转账解决方案...")
    
    solution = TrueCrossChainSolution()
    
    if len(solution.web3_connections) != 2:
        print("❌ Web3连接失败，无法进行测试")
        return
    
    if not solution.bridge_contracts['chain_a'] or not solution.bridge_contracts['chain_b']:
        print("❌ 桥接合约加载失败，无法进行测试")
        return
    
    # 执行真正的跨链转账
    success = solution.perform_true_cross_chain_transfer(0.03)  # 转账0.03 ETH
    
    if success:
        print("✅ 真正的跨链转账解决方案完成！")
    else:
        print("❌ 跨链转账解决方案失败")

if __name__ == "__main__":
    main()