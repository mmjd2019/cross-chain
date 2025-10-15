#!/usr/bin/env python3
"""
ERC20代币跨链转账实现
使用ERC20代币实现真正的跨链资产转移
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

class ERC20CrossChainTransfer:
    def __init__(self):
        # 使用测试账户
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
        
        # 代币合约地址（从部署结果中获取）
        self.token_addresses = {}
        self.load_token_addresses()
        
        # 初始化Web3连接
        self.web3_connections = {}
        self.bridge_contracts = {}
        self.token_contracts = {}
        self.init_connections()
    
    def load_token_addresses(self):
        """加载代币合约地址"""
        try:
            with open('erc20_deployment.json', 'r') as f:
                deployment = json.load(f)
            
            for chain_id, result in deployment.items():
                self.token_addresses[chain_id] = result['address']
                print(f"✅ 加载 {result['chain_name']} 代币地址: {result['address']}")
                
        except FileNotFoundError:
            print("❌ 未找到代币部署记录，请先运行 deploy_erc20_tokens.py")
            exit(1)
        except Exception as e:
            print(f"❌ 加载代币地址失败: {e}")
            exit(1)
    
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
                        
                        # 创建桥接合约实例
                        bridge_contract = w3.w3.eth.contract(
                            address=w3.w3.to_checksum_address(config['bridge_address']),
                            abi=bridge_abi
                        )
                        self.bridge_contracts[chain_id] = bridge_contract
                        print(f"✅ {config['name']} 桥接合约加载成功")
                        
                        # 加载代币合约ABI
                        with open('CrossChainToken.json', 'r') as f:
                            token_abi = json.load(f)['abi']
                        
                        # 创建代币合约实例
                        token_address = self.token_addresses[chain_id]
                        token_contract = w3.w3.eth.contract(
                            address=w3.w3.to_checksum_address(token_address),
                            abi=token_abi
                        )
                        self.token_contracts[chain_id] = token_contract
                        print(f"✅ {config['name']} 代币合约加载成功")
                        
                    except Exception as e:
                        print(f"❌ {config['name']} 合约加载失败: {e}")
                        self.bridge_contracts[chain_id] = None
                        self.token_contracts[chain_id] = None
                else:
                    print(f"❌ {config['name']} 连接失败")
            except Exception as e:
                print(f"❌ {config['name']} 连接错误: {e}")
    
    def get_token_balance(self, chain_id, address):
        """获取代币余额"""
        w3 = self.web3_connections[chain_id]
        token_contract = self.token_contracts[chain_id]
        
        balance_wei = token_contract.functions.balanceOf(address).call()
        balance_tokens = w3.w3.from_wei(balance_wei, 'ether')
        return balance_wei, balance_tokens
    
    def get_eth_balance(self, chain_id, address):
        """获取ETH余额"""
        w3 = self.web3_connections[chain_id]
        balance_wei = w3.w3.eth.get_balance(address)
        balance_eth = w3.w3.from_wei(balance_wei, 'ether')
        return balance_wei, balance_eth
    
    def approve_token(self, chain_id, spender_address, amount):
        """授权代币"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        token_contract = self.token_contracts[chain_id]
        
        nonce = w3.w3.eth.get_transaction_count(self.test_account.address)
        gas_price = w3.w3.eth.gas_price
        
        transaction = token_contract.functions.approve(
            spender_address,
            amount
        ).build_transaction({
            'from': self.test_account.address,
            'gas': 100000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': config['chain_id']
        })
        
        signed_txn = w3.w3.eth.account.sign_transaction(transaction, self.test_account.key)
        tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        return tx_hash.hex()
    
    def call_lock_assets(self, chain_id, amount, token_address, target_chain):
        """调用lockAssets函数锁定资产"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        bridge_contract = self.bridge_contracts[chain_id]
        
        if not bridge_contract:
            raise Exception("桥接合约未加载")
        
        nonce = w3.w3.eth.get_transaction_count(self.test_account.address)
        gas_price = w3.w3.eth.gas_price
        
        # 构建交易
        transaction = bridge_contract.functions.lockAssets(
            amount,
            w3.w3.to_checksum_address(token_address),
            target_chain
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
    
    def call_unlock_assets(self, chain_id, user_did, amount, token_address, source_chain, source_tx_hash):
        """调用unlockAssets函数解锁资产"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        bridge_contract = self.bridge_contracts[chain_id]
        
        if not bridge_contract:
            raise Exception("桥接合约未加载")
        
        nonce = w3.w3.eth.get_transaction_count(self.test_account.address)
        gas_price = w3.w3.eth.gas_price
        
        # 构建交易
        transaction = bridge_contract.functions.unlockAssets(
            user_did,
            amount,
            w3.w3.to_checksum_address(token_address),
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
    
    def perform_erc20_cross_chain_transfer(self, amount_tokens):
        """执行ERC20代币跨链转账"""
        print(f"🚀 开始ERC20代币跨链转账: {amount_tokens} 代币 从 chain_a 到 chain_b")
        print(f"📋 使用账户: {self.test_account.address}")
        print()
        
        # 记录转账前状态
        print("📊 转账前状态:")
        token_balance_a_before = self.get_token_balance('chain_a', self.test_account.address)
        token_balance_b_before = self.get_token_balance('chain_b', self.test_account.address)
        eth_balance_a_before = self.get_eth_balance('chain_a', self.test_account.address)
        eth_balance_b_before = self.get_eth_balance('chain_b', self.test_account.address)
        
        print(f"  链A代币余额: {token_balance_a_before[1]:.6f} CCT")
        print(f"  链B代币余额: {token_balance_b_before[1]:.6f} CCT")
        print(f"  链A ETH余额: {eth_balance_a_before[1]:.6f} ETH")
        print(f"  链B ETH余额: {eth_balance_b_before[1]:.6f} ETH")
        print()
        
        # 步骤1: 授权代币
        print("🔐 步骤1: 授权代币...")
        try:
            bridge_address = self.web3_connections['chain_a'].w3.to_checksum_address(self.chains['chain_a']['bridge_address'])
            amount_wei = self.web3_connections['chain_a'].w3.to_wei(amount_tokens, 'ether')
            
            approve_tx_hash = self.approve_token('chain_a', bridge_address, amount_wei)
            print(f"✅ 授权交易已发送: {approve_tx_hash}")
            
            # 等待授权交易确认
            print("⏳ 等待授权交易确认...")
            approve_receipt = self.wait_for_transaction('chain_a', approve_tx_hash)
            print(f"✅ 授权交易已确认，区块号: {approve_receipt.blockNumber}")
            print(f"   交易状态: {approve_receipt.status}")
            
            if approve_receipt.status == 0:
                print("❌ 授权交易失败")
                return False
                
        except Exception as e:
            print(f"❌ 授权代币失败: {e}")
            return False
        
        # 步骤2: 在链A上锁定资产
        print("🔒 步骤2: 在链A上锁定资产...")
        try:
            token_address = self.token_addresses['chain_a']
            amount_wei = self.web3_connections['chain_a'].w3.to_wei(amount_tokens, 'ether')
            
            lock_tx_hash = self.call_lock_assets('chain_a', amount_wei, token_address, 'chain_b')
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
        
        # 步骤3: 在链B上解锁资产
        print("🔓 步骤3: 在链B上解锁资产...")
        try:
            # 生成用户DID（简化版本）
            user_did = f"did:example:{self.test_account.address}"
            token_address = self.token_addresses['chain_b']
            amount_wei = self.web3_connections['chain_b'].w3.to_wei(amount_tokens, 'ether')
            
            unlock_tx_hash = self.call_unlock_assets(
                'chain_b', 
                user_did, 
                amount_wei, 
                token_address,
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
        token_balance_a_after = self.get_token_balance('chain_a', self.test_account.address)
        token_balance_b_after = self.get_token_balance('chain_b', self.test_account.address)
        eth_balance_a_after = self.get_eth_balance('chain_a', self.test_account.address)
        eth_balance_b_after = self.get_eth_balance('chain_b', self.test_account.address)
        
        print(f"  链A代币余额: {token_balance_a_after[1]:.6f} CCT")
        print(f"  链B代币余额: {token_balance_b_after[1]:.6f} CCT")
        print(f"  链A ETH余额: {eth_balance_a_after[1]:.6f} ETH")
        print(f"  链B ETH余额: {eth_balance_b_after[1]:.6f} ETH")
        print()
        
        # 分析余额变化
        print("📈 余额变化分析:")
        token_change_a = token_balance_a_after[1] - token_balance_a_before[1]
        token_change_b = token_balance_b_after[1] - token_balance_b_before[1]
        eth_change_a = eth_balance_a_after[1] - eth_balance_a_before[1]
        eth_change_b = eth_balance_b_after[1] - eth_balance_b_before[1]
        
        print(f"  链A代币变化: {token_change_a:.6f} CCT")
        print(f"  链B代币变化: {token_change_b:.6f} CCT")
        print(f"  链A ETH变化: {eth_change_a:.6f} ETH")
        print(f"  链B ETH变化: {eth_change_b:.6f} ETH")
        print()
        
        # 验证跨链转账
        print("🔍 跨链转账验证:")
        success = token_change_a < 0 and token_change_b > 0
        
        if success:
            print("✅ ERC20代币跨链转账成功！")
            print("   - 源链代币余额减少")
            print("   - 目标链代币余额增加")
            print("   - 这是真正的跨链转账！")
        else:
            print("❌ ERC20代币跨链转账失败")
            print(f"   - 源链代币变化: {token_change_a:.6f} CCT")
            print(f"   - 目标链代币变化: {token_change_b:.6f} CCT")
        
        # 生成报告
        report = {
            "transfer_info": {
                "amount_tokens": amount_tokens,
                "from_chain": "chain_a",
                "to_chain": "chain_b",
                "account_address": self.test_account.address,
                "approve_tx_hash": approve_tx_hash,
                "lock_tx_hash": lock_tx_hash,
                "unlock_tx_hash": unlock_tx_hash,
                "approve_block": approve_receipt.blockNumber,
                "lock_block": lock_receipt.blockNumber,
                "unlock_block": unlock_receipt.blockNumber
            },
            "before_status": {
                "chain_a_token": {
                    "balance_tokens": float(token_balance_a_before[1]),
                    "balance_wei": int(token_balance_a_before[0])
                },
                "chain_b_token": {
                    "balance_tokens": float(token_balance_b_before[1]),
                    "balance_wei": int(token_balance_b_before[0])
                },
                "chain_a_eth": {
                    "balance_eth": float(eth_balance_a_before[1]),
                    "balance_wei": int(eth_balance_a_before[0])
                },
                "chain_b_eth": {
                    "balance_eth": float(eth_balance_b_before[1]),
                    "balance_wei": int(eth_balance_b_before[0])
                }
            },
            "after_status": {
                "chain_a_token": {
                    "balance_tokens": float(token_balance_a_after[1]),
                    "balance_wei": int(token_balance_a_after[0])
                },
                "chain_b_token": {
                    "balance_tokens": float(token_balance_b_after[1]),
                    "balance_wei": int(token_balance_b_after[0])
                },
                "chain_a_eth": {
                    "balance_eth": float(eth_balance_a_after[1]),
                    "balance_wei": int(eth_balance_a_after[0])
                },
                "chain_b_eth": {
                    "balance_eth": float(eth_balance_b_after[1]),
                    "balance_wei": int(eth_balance_b_after[0])
                }
            },
            "changes": {
                "chain_a_token": {
                    "change_tokens": float(token_change_a),
                    "change_wei": int(token_balance_a_after[0] - token_balance_a_before[0])
                },
                "chain_b_token": {
                    "change_tokens": float(token_change_b),
                    "change_wei": int(token_balance_b_after[0] - token_balance_b_before[0])
                },
                "chain_a_eth": {
                    "change_eth": float(eth_change_a),
                    "change_wei": int(eth_balance_a_after[0] - eth_balance_a_before[0])
                },
                "chain_b_eth": {
                    "change_eth": float(eth_change_b),
                    "change_wei": int(eth_balance_b_after[0] - eth_balance_b_before[0])
                }
            },
            "cross_chain_verification": {
                "is_true_cross_chain": success,
                "source_chain_decreased": token_change_a < 0,
                "target_chain_increased": token_change_b > 0,
                "verification_result": "SUCCESS" if success else "FAILED"
            },
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 保存报告
        with open('erc20_cross_chain_transfer_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 详细报告已保存到 erc20_cross_chain_transfer_report.json")
        
        return success

def main():
    print("🚀 启动ERC20代币跨链转账...")
    
    transfer = ERC20CrossChainTransfer()
    
    if len(transfer.web3_connections) != 2:
        print("❌ Web3连接失败，无法进行转账")
        return
    
    if not transfer.bridge_contracts['chain_a'] or not transfer.bridge_contracts['chain_b']:
        print("❌ 桥接合约加载失败，无法进行转账")
        return
    
    if not transfer.token_contracts['chain_a'] or not transfer.token_contracts['chain_b']:
        print("❌ 代币合约加载失败，无法进行转账")
        return
    
    # 执行ERC20代币跨链转账
    success = transfer.perform_erc20_cross_chain_transfer(100)  # 转账100个代币
    
    if success:
        print("✅ ERC20代币跨链转账完成！")
    else:
        print("❌ ERC20代币跨链转账失败")

if __name__ == "__main__":
    main()
