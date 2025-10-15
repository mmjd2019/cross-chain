#!/usr/bin/env python3
"""
使用合约所有者账户配置权限
设置Oracle授权、用户身份验证和桥接合约代币支持
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

class ContractConfigurator:
    def __init__(self):
        # 加载合约所有者账户
        self.owner_account = self.load_owner_account()
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
        
        # 代币地址
        self.token_addresses = {
            'chain_a': '0x14D83c34ba0E1caC363039699d495e733B8A1182',
            'chain_b': '0x8Ce489412b110427695f051dAE4055d565BC7cF4'
        }
        
        # 初始化Web3连接
        self.web3_connections = {}
        self.verifier_contracts = {}
        self.bridge_contracts = {}
        self.init_connections()
    
    def load_owner_account(self):
        """加载合约所有者账户"""
        try:
            with open('contract_owner_account.json', 'r') as f:
                owner_info = json.load(f)
            
            private_key = owner_info['private_key']
            account = Account.from_key(private_key)
            
            print(f"✅ 加载合约所有者账户:")
            print(f"   地址: {account.address}")
            print(f"   私钥: {private_key}")
            
            return account
            
        except FileNotFoundError:
            print("❌ 未找到合约所有者账户文件，请先运行 find_contract_owner.py")
            exit(1)
        except Exception as e:
            print(f"❌ 加载合约所有者账户失败: {e}")
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
                        
                        # 加载桥接合约ABI
                        with open('CrossChainBridge.json', 'r') as f:
                            bridge_abi = json.load(f)['abi']
                        
                        # 创建桥接合约实例
                        bridge_contract = w3.w3.eth.contract(
                            address=w3.w3.to_checksum_address(config['bridge_address']),
                            abi=bridge_abi
                        )
                        self.bridge_contracts[chain_id] = bridge_contract
                        print(f"✅ {config['name']} 桥接合约加载成功")
                        
                    except Exception as e:
                        print(f"❌ {config['name']} 合约加载失败: {e}")
                        self.verifier_contracts[chain_id] = None
                        self.bridge_contracts[chain_id] = None
                else:
                    print(f"❌ {config['name']} 连接失败")
            except Exception as e:
                print(f"❌ {config['name']} 连接错误: {e}")
    
    def send_transaction(self, chain_id, contract, function_name, args, value=0):
        """发送交易"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        
        try:
            nonce = w3.w3.eth.get_transaction_count(self.owner_account.address)
            gas_price = w3.w3.eth.gas_price
            
            # 构建交易
            transaction = getattr(contract.functions, function_name)(*args).build_transaction({
                'from': self.owner_account.address,
                'gas': 200000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': config['chain_id'],
                'value': value
            })
            
            # 签名并发送交易
            signed_txn = w3.w3.eth.account.sign_transaction(transaction, self.owner_account.key)
            tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            print(f"✅ {function_name} 交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            print("⏳ 等待交易确认...")
            receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                print(f"✅ {function_name} 交易成功!")
                print(f"   交易哈希: {tx_hash.hex()}")
                print(f"   区块号: {receipt.blockNumber}")
                print(f"   Gas使用: {receipt.gasUsed}")
                return True
            else:
                print(f"❌ {function_name} 交易失败")
                return False
                
        except Exception as e:
            print(f"❌ {function_name} 交易错误: {e}")
            return False
    
    def set_authorized_oracle(self, chain_id, oracle_address, authorized=True):
        """设置授权的Oracle"""
        print(f"🔧 在 {self.chains[chain_id]['name']} 上设置授权Oracle...")
        print(f"   Oracle地址: {oracle_address}")
        print(f"   授权状态: {authorized}")
        
        verifier_contract = self.verifier_contracts[chain_id]
        w3 = self.web3_connections[chain_id]
        return self.send_transaction(
            chain_id, 
            verifier_contract, 
            'setAuthorizedOracle', 
            [w3.w3.to_checksum_address(oracle_address), authorized]
        )
    
    def verify_user_identity(self, chain_id, user_address, user_did):
        """验证用户身份"""
        print(f"🔐 在 {self.chains[chain_id]['name']} 上验证用户身份...")
        print(f"   用户地址: {user_address}")
        print(f"   用户DID: {user_did}")
        
        verifier_contract = self.verifier_contracts[chain_id]
        w3 = self.web3_connections[chain_id]
        return self.send_transaction(
            chain_id, 
            verifier_contract, 
            'verifyIdentity', 
            [w3.w3.to_checksum_address(user_address), user_did]
        )
    
    def add_supported_token(self, chain_id, token_address, token_name, token_symbol, token_decimals):
        """添加支持的代币到桥接合约"""
        print(f"🔧 在 {self.chains[chain_id]['name']} 上添加代币支持...")
        print(f"   代币地址: {token_address}")
        print(f"   代币名称: {token_name}")
        print(f"   代币符号: {token_symbol}")
        print(f"   代币精度: {token_decimals}")
        
        bridge_contract = self.bridge_contracts[chain_id]
        w3 = self.web3_connections[chain_id]
        return self.send_transaction(
            chain_id, 
            bridge_contract, 
            'addSupportedToken', 
            [
                w3.w3.to_checksum_address(token_address),
                token_name,
                token_symbol,
                token_decimals
            ]
        )
    
    def configure_all_chains(self):
        """配置所有链"""
        print("🚀 开始配置所有链...")
        print("=" * 50)
        
        configuration_results = {}
        
        for chain_id, config in self.chains.items():
            print(f"\n🔗 配置 {config['name']}...")
            
            if chain_id not in self.web3_connections:
                print(f"❌ {config['name']} 连接失败，跳过")
                continue
            
            if not self.verifier_contracts[chain_id] or not self.bridge_contracts[chain_id]:
                print(f"❌ {config['name']} 合约未加载，跳过")
                continue
            
            chain_results = {
                'oracle_set': False,
                'identity_verified': False,
                'token_supported': False
            }
            
            # 1. 设置授权Oracle
            print("   步骤1: 设置授权Oracle...")
            oracle_success = self.set_authorized_oracle(chain_id, self.test_account.address, True)
            chain_results['oracle_set'] = oracle_success
            
            if oracle_success:
                # 2. 验证用户身份
                print("   步骤2: 验证用户身份...")
                user_did = f"did:example:{self.test_account.address}"
                identity_success = self.verify_user_identity(chain_id, self.test_account.address, user_did)
                chain_results['identity_verified'] = identity_success
                
                if identity_success:
                    # 3. 添加代币支持
                    print("   步骤3: 添加代币支持...")
                    token_address = self.token_addresses[chain_id]
                    token_success = self.add_supported_token(
                        chain_id, 
                        token_address, 
                        "CrossChain Token", 
                        "CCT", 
                        18
                    )
                    chain_results['token_supported'] = token_success
            
            configuration_results[chain_id] = {
                'chain_name': config['name'],
                **chain_results
            }
        
        # 保存配置结果
        with open('contract_configuration_results.json', 'w') as f:
            json.dump(configuration_results, f, indent=2)
        
        print(f"\n📄 配置结果已保存到 contract_configuration_results.json")
        
        return configuration_results
    
    def verify_configuration(self, configuration_results):
        """验证配置结果"""
        print("\n🧪 验证配置结果...")
        print("=" * 50)
        
        for chain_id, result in configuration_results.items():
            print(f"\n🔍 验证 {result['chain_name']} 的配置...")
            
            if not result['oracle_set']:
                print("   ❌ Oracle设置失败")
                continue
            
            if not result['identity_verified']:
                print("   ❌ 身份验证失败")
                continue
            
            if not result['token_supported']:
                print("   ❌ 代币支持添加失败")
                continue
            
            print("   ✅ 所有配置都成功!")
            
            # 验证代币支持
            try:
                w3 = self.web3_connections[chain_id]
                bridge_contract = self.bridge_contracts[chain_id]
                token_address = self.token_addresses[chain_id]
                
                is_supported = bridge_contract.functions.isTokenSupported(
                    w3.w3.to_checksum_address(token_address)
                ).call()
                
                if is_supported:
                    print("   ✅ 代币支持验证成功")
                else:
                    print("   ❌ 代币支持验证失败")
                    
            except Exception as e:
                print(f"   ❌ 验证代币支持失败: {e}")

def main():
    print("🚀 启动合约配置...")
    
    configurator = ContractConfigurator()
    
    if len(configurator.web3_connections) != 2:
        print("❌ Web3连接失败，无法进行配置")
        return
    
    if not configurator.verifier_contracts['chain_a'] or not configurator.verifier_contracts['chain_b']:
        print("❌ 验证器合约加载失败，无法进行配置")
        return
    
    if not configurator.bridge_contracts['chain_a'] or not configurator.bridge_contracts['chain_b']:
        print("❌ 桥接合约加载失败，无法进行配置")
        return
    
    # 配置所有链
    configuration_results = configurator.configure_all_chains()
    
    # 验证配置
    configurator.verify_configuration(configuration_results)
    
    success_count = sum(1 for result in configuration_results.values() 
                       if result['oracle_set'] and result['identity_verified'] and result['token_supported'])
    
    if success_count > 0:
        print(f"\n✅ 成功配置 {success_count} 个链")
        print("现在可以进行ERC20跨链转账了!")
    else:
        print("❌ 合约配置失败")

if __name__ == "__main__":
    main()
