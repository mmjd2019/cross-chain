#!/usr/bin/env python3
"""
验证桥接合约地址
为桥接合约地址添加DID验证，使其能够接收代币授权
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

class BridgeContractVerifier:
    def __init__(self):
        # 使用测试账户（已授权的Oracle）
        self.test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
        
        # 链配置
        self.chains = {
            'chain_a': {
                'name': 'Besu Chain A',
                'rpc_url': 'http://localhost:8545',
                'chain_id': 2023,
                'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf',
                'bridge_address': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af'
            },
            'chain_b': {
                'name': 'Besu Chain B', 
                'rpc_url': 'http://localhost:8555',
                'chain_id': 2024,
                'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf',
                'bridge_address': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af'
            }
        }
        
        # 初始化Web3连接
        self.web3_connections = {}
        self.verifier_contracts = {}
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
                        
                    except Exception as e:
                        print(f"❌ {config['name']} 合约加载失败: {e}")
                        self.verifier_contracts[chain_id] = None
                else:
                    print(f"❌ {config['name']} 连接失败")
            except Exception as e:
                print(f"❌ {config['name']} 连接错误: {e}")
    
    def verify_contract_address(self, chain_id, contract_address, contract_did):
        """验证合约地址"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        verifier_contract = self.verifier_contracts[chain_id]
        
        if not verifier_contract:
            raise Exception("验证器合约未加载")
        
        print(f"🔐 在 {config['name']} 上验证合约地址...")
        print(f"   合约地址: {contract_address}")
        print(f"   合约DID: {contract_did}")
        
        try:
            nonce = w3.w3.eth.get_transaction_count(self.test_account.address)
            gas_price = w3.w3.eth.gas_price
            
            # 构建交易
            transaction = verifier_contract.functions.verifyIdentity(
                w3.w3.to_checksum_address(contract_address),
                contract_did
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
            
            print(f"✅ 合约验证交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            print("⏳ 等待交易确认...")
            receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                print(f"✅ 合约验证成功!")
                print(f"   交易哈希: {tx_hash.hex()}")
                print(f"   区块号: {receipt.blockNumber}")
                return True
            else:
                print(f"❌ 合约验证失败")
                return False
                
        except Exception as e:
            print(f"❌ 合约验证错误: {e}")
            return False
    
    def check_verification_status(self, chain_id, address):
        """检查验证状态"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        verifier_contract = self.verifier_contracts[chain_id]
        
        try:
            is_verified = verifier_contract.functions.isVerified(w3.w3.to_checksum_address(address)).call()
            print(f"🔍 {config['name']} 地址 {address} 验证状态: {is_verified}")
            return is_verified
        except Exception as e:
            print(f"❌ 检查验证状态失败: {e}")
            return False
    
    def verify_all_bridge_contracts(self):
        """验证所有桥接合约"""
        print("🚀 开始验证所有桥接合约...")
        print("=" * 50)
        
        results = {}
        
        for chain_id, config in self.chains.items():
            print(f"\n🔗 验证 {config['name']} 的桥接合约...")
            
            if chain_id not in self.web3_connections:
                print(f"❌ {config['name']} 连接失败，跳过")
                continue
            
            if not self.verifier_contracts[chain_id]:
                print(f"❌ {config['name']} 验证器合约未加载，跳过")
                continue
            
            # 检查当前验证状态
            print("   检查当前验证状态...")
            is_verified = self.check_verification_status(chain_id, config['bridge_address'])
            
            if is_verified:
                print(f"   ✅ 桥接合约已经验证")
                results[chain_id] = True
                continue
            
            # 验证桥接合约
            bridge_did = f"did:bridge:{config['bridge_address']}"
            success = self.verify_contract_address(chain_id, config['bridge_address'], bridge_did)
            results[chain_id] = success
            
            if success:
                # 再次检查验证状态
                print("   验证后状态检查...")
                is_verified_after = self.check_verification_status(chain_id, config['bridge_address'])
                if is_verified_after:
                    print(f"   ✅ 桥接合约验证成功")
                else:
                    print(f"   ❌ 桥接合约验证失败")
                    results[chain_id] = False
        
        # 保存结果
        with open('bridge_contract_verification_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 验证结果已保存到 bridge_contract_verification_results.json")
        
        success_count = sum(1 for result in results.values() if result)
        print(f"✅ 成功验证 {success_count} 个桥接合约")
        
        return results

def main():
    print("🚀 启动桥接合约验证...")
    
    verifier = BridgeContractVerifier()
    
    if len(verifier.web3_connections) != 2:
        print("❌ Web3连接失败，无法进行验证")
        return
    
    if not verifier.verifier_contracts['chain_a'] or not verifier.verifier_contracts['chain_b']:
        print("❌ 验证器合约加载失败，无法进行验证")
        return
    
    # 验证所有桥接合约
    results = verifier.verify_all_bridge_contracts()
    
    if all(results.values()):
        print("✅ 所有桥接合约验证成功！")
        print("现在可以进行ERC20代币跨链转账了!")
    else:
        print("❌ 部分桥接合约验证失败")

if __name__ == "__main__":
    main()

