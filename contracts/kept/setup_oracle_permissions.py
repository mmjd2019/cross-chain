#!/usr/bin/env python3
"""
设置Oracle权限
为测试账户设置Oracle权限，以便进行身份验证
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

class OraclePermissionSetup:
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
        
        # 初始化Web3连接
        self.web3_connections = {}
        self.verifier_contracts = {}
        self.init_connections()
    
    def init_connections(self):
        """初始化Web3连接和合约"""
        print("🔗 初始化Web3连接和验证器合约...")
        
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
                        print(f"❌ {config['name']} 验证器合约加载失败: {e}")
                        self.verifier_contracts[chain_id] = None
                else:
                    print(f"❌ {config['name']} 连接失败")
            except Exception as e:
                print(f"❌ {config['name']} 连接错误: {e}")
    
    def check_verifier_owner(self, chain_id):
        """检查验证器合约的所有者"""
        w3 = self.web3_connections[chain_id]
        verifier_contract = self.verifier_contracts[chain_id]
        
        try:
            owner = verifier_contract.functions.owner().call()
            print(f"🔍 {self.chains[chain_id]['name']} 验证器合约所有者: {owner}")
            print(f"   测试账户: {self.test_account.address}")
            print(f"   是否匹配: {owner.lower() == self.test_account.address.lower()}")
            return owner.lower() == self.test_account.address.lower()
        except Exception as e:
            print(f"❌ 检查所有者失败: {e}")
            return False
    
    def set_authorized_oracle(self, chain_id, oracle_address, authorized=True):
        """设置授权的Oracle"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        verifier_contract = self.verifier_contracts[chain_id]
        
        if not verifier_contract:
            raise Exception("验证器合约未加载")
        
        print(f"🔧 在 {config['name']} 上设置授权Oracle...")
        print(f"   Oracle地址: {oracle_address}")
        print(f"   授权状态: {authorized}")
        
        try:
            nonce = w3.w3.eth.get_transaction_count(self.test_account.address)
            gas_price = w3.w3.eth.gas_price
            
            # 构建交易
            transaction = verifier_contract.functions.setAuthorizedOracle(
                w3.w3.to_checksum_address(oracle_address),
                authorized
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
            
            print(f"✅ 设置Oracle交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            print("⏳ 等待交易确认...")
            receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                print(f"✅ Oracle设置成功!")
                print(f"   交易哈希: {tx_hash.hex()}")
                print(f"   区块号: {receipt.blockNumber}")
                print(f"   Gas使用: {receipt.gasUsed}")
                return True
            else:
                print(f"❌ Oracle设置失败")
                return False
                
        except Exception as e:
            print(f"❌ 设置Oracle失败: {e}")
            return False
    
    def verify_identity(self, chain_id, user_address, user_did):
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
    
    def setup_all_chains(self):
        """设置所有链的Oracle权限"""
        print("🚀 开始设置Oracle权限...")
        print("=" * 50)
        
        setup_results = {}
        
        for chain_id, config in self.chains.items():
            print(f"\n🔗 处理 {config['name']}...")
            
            if chain_id not in self.web3_connections:
                print(f"❌ {config['name']} 连接失败，跳过")
                continue
            
            if not self.verifier_contracts[chain_id]:
                print(f"❌ {config['name']} 验证器合约未加载，跳过")
                continue
            
            # 检查所有者权限
            is_owner = self.check_verifier_owner(chain_id)
            if not is_owner:
                print(f"❌ {config['name']} 测试账户不是验证器合约所有者，跳过")
                setup_results[chain_id] = {'status': 'failed', 'reason': 'not_owner'}
                continue
            
            # 设置授权Oracle
            success = self.set_authorized_oracle(chain_id, self.test_account.address, True)
            if success:
                # 验证用户身份
                user_did = f"did:example:{self.test_account.address}"
                verify_success = self.verify_identity(chain_id, self.test_account.address, user_did)
                
                setup_results[chain_id] = {
                    'status': 'success' if verify_success else 'partial',
                    'oracle_set': success,
                    'identity_verified': verify_success
                }
            else:
                setup_results[chain_id] = {'status': 'failed', 'reason': 'oracle_set_failed'}
        
        # 保存设置结果
        with open('oracle_permission_setup.json', 'w') as f:
            json.dump(setup_results, f, indent=2)
        
        print(f"\n📄 设置结果已保存到 oracle_permission_setup.json")
        
        return setup_results

def main():
    print("🚀 启动Oracle权限设置...")
    
    setup = OraclePermissionSetup()
    
    if len(setup.web3_connections) != 2:
        print("❌ Web3连接失败，无法进行设置")
        return
    
    if not setup.verifier_contracts['chain_a'] or not setup.verifier_contracts['chain_b']:
        print("❌ 验证器合约加载失败，无法进行设置")
        return
    
    # 设置Oracle权限
    setup_results = setup.setup_all_chains()
    
    success_count = sum(1 for result in setup_results.values() if result['status'] == 'success')
    
    if success_count > 0:
        print(f"\n✅ 成功设置 {success_count} 个链的Oracle权限")
        print("现在可以进行身份验证和代币转账了")
    else:
        print("❌ Oracle权限设置失败")

if __name__ == "__main__":
    main()

