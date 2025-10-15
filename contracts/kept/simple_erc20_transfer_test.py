#!/usr/bin/env python3
"""
简化的ERC20代币转账测试
先验证用户身份，然后进行代币转账
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

class SimpleERC20TransferTest:
    def __init__(self):
        # 使用测试账户
        self.test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
        
        # 链配置
        self.chains = {
            'chain_a': {
                'name': 'Besu Chain A',
                'rpc_url': 'http://localhost:8545',
                'chain_id': 2023,
                'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
            },
            'chain_b': {
                'name': 'Besu Chain B', 
                'rpc_url': 'http://localhost:8555',
                'chain_id': 2024,
                'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
            }
        }
        
        # 代币合约地址
        self.token_addresses = {
            'chain_a': '0x14D83c34ba0E1caC363039699d495e733B8A1182',
            'chain_b': '0x8Ce489412b110427695f051dAE4055d565BC7cF4'
        }
        
        # 初始化Web3连接
        self.web3_connections = {}
        self.verifier_contracts = {}
        self.token_contracts = {}
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
                    
                    # 加载验证器合约ABI
                    try:
                        with open('CrossChainDIDVerifier.json', 'r') as f:
                            verifier_abi = json.load(f)['abi']
                        
                        # 创建验证器合约实例
                        verifier_contract = w3.w3.eth.contract(
                            address=w3.w3.to_checksum_address(config['verifier_address']),
                            abi=verifier_abi
                        )
                        self.verifier_contracts[chain_id] = verifier_contract
                        print(f"✅ {config['name']} 验证器合约加载成功")
                        
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
                        self.verifier_contracts[chain_id] = None
                        self.token_contracts[chain_id] = None
                else:
                    print(f"❌ {config['name']} 连接失败")
            except Exception as e:
                print(f"❌ {config['name']} 连接错误: {e}")
    
    def verify_user_identity(self, chain_id, user_address, user_did):
        """验证用户身份"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        verifier_contract = self.verifier_contracts[chain_id]
        
        if not verifier_contract:
            raise Exception("验证器合约未加载")
        
        print(f"🔐 在 {config['name']} 上验证用户身份...")
        print(f"   用户地址: {user_address}")
        print(f"   用户DID: {user_did}")
        
        try:
            nonce = w3.w3.eth.get_transaction_count(self.test_account.address)
            gas_price = w3.w3.eth.gas_price
            
            # 构建交易
            transaction = verifier_contract.functions.verifyIdentity(
                w3.w3.to_checksum_address(user_address),
                user_did
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
            
            print(f"✅ 身份验证交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            print("⏳ 等待交易确认...")
            receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                print(f"✅ 身份验证成功!")
                print(f"   交易哈希: {tx_hash.hex()}")
                print(f"   区块号: {receipt.blockNumber}")
                return True
            else:
                print(f"❌ 身份验证失败")
                return False
                
        except Exception as e:
            print(f"❌ 身份验证错误: {e}")
            return False
    
    def get_token_balance(self, chain_id, address):
        """获取代币余额"""
        w3 = self.web3_connections[chain_id]
        token_contract = self.token_contracts[chain_id]
        
        balance_wei = token_contract.functions.balanceOf(address).call()
        balance_tokens = w3.w3.from_wei(balance_wei, 'ether')
        return balance_wei, balance_tokens
    
    def test_simple_token_transfer(self, chain_id, amount_tokens):
        """测试简单的代币转账"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        token_contract = self.token_contracts[chain_id]
        
        print(f"🧪 在 {config['name']} 上测试代币转账...")
        print(f"   转账金额: {amount_tokens} CCT")
        
        # 记录转账前余额
        balance_before = self.get_token_balance(chain_id, self.test_account.address)
        print(f"   转账前余额: {balance_before[1]:.6f} CCT")
        
        try:
            # 尝试转账给自己（测试基本功能）
            amount_wei = w3.w3.to_wei(amount_tokens, 'ether')
            
            nonce = w3.w3.eth.get_transaction_count(self.test_account.address)
            gas_price = w3.w3.eth.gas_price
            
            transaction = token_contract.functions.transfer(
                self.test_account.address,  # 转账给自己
                amount_wei
            ).build_transaction({
                'from': self.test_account.address,
                'gas': 100000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': config['chain_id']
            })
            
            # 签名并发送交易
            signed_txn = w3.w3.eth.account.sign_transaction(transaction, self.test_account.key)
            tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            print(f"✅ 转账交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            print("⏳ 等待交易确认...")
            receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                print(f"✅ 代币转账成功!")
                print(f"   交易哈希: {tx_hash.hex()}")
                print(f"   区块号: {receipt.blockNumber}")
                print(f"   Gas使用: {receipt.gasUsed}")
                
                # 记录转账后余额
                balance_after = self.get_token_balance(chain_id, self.test_account.address)
                print(f"   转账后余额: {balance_after[1]:.6f} CCT")
                print(f"   余额变化: {balance_after[1] - balance_before[1]:.6f} CCT")
                
                return True
            else:
                print(f"❌ 代币转账失败")
                return False
                
        except Exception as e:
            print(f"❌ 代币转账错误: {e}")
            return False
    
    def run_test(self):
        """运行完整测试"""
        print("🚀 开始简化的ERC20代币转账测试...")
        print("=" * 50)
        
        # 生成用户DID
        user_did = f"did:example:{self.test_account.address}"
        
        # 验证用户身份
        print("\n🔐 步骤1: 验证用户身份...")
        for chain_id, config in self.chains.items():
            if chain_id in self.web3_connections and self.verifier_contracts[chain_id]:
                success = self.verify_user_identity(chain_id, self.test_account.address, user_did)
                if not success:
                    print(f"❌ {config['name']} 身份验证失败")
                    return False
        
        # 测试代币转账
        print("\n🧪 步骤2: 测试代币转账...")
        for chain_id, config in self.chains.items():
            if chain_id in self.web3_connections and self.token_contracts[chain_id]:
                success = self.test_simple_token_transfer(chain_id, 10)  # 转账10个代币
                if not success:
                    print(f"❌ {config['name']} 代币转账失败")
                    return False
        
        print("\n✅ 所有测试通过！")
        print("现在可以进行跨链转账了")
        return True

def main():
    print("🚀 启动简化的ERC20代币转账测试...")
    
    tester = SimpleERC20TransferTest()
    
    if len(tester.web3_connections) != 2:
        print("❌ Web3连接失败，无法进行测试")
        return
    
    if not tester.verifier_contracts['chain_a'] or not tester.verifier_contracts['chain_b']:
        print("❌ 验证器合约加载失败，无法进行测试")
        return
    
    if not tester.token_contracts['chain_a'] or not tester.token_contracts['chain_b']:
        print("❌ 代币合约加载失败，无法进行测试")
        return
    
    # 运行测试
    success = tester.run_test()
    
    if success:
        print("✅ 简化ERC20代币转账测试完成！")
    else:
        print("❌ 简化ERC20代币转账测试失败")

if __name__ == "__main__":
    main()

