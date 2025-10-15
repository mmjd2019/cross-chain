#!/usr/bin/env python3
"""
添加代币支持到桥接合约
使用合约所有者账户添加ERC20代币支持
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

class TokenSupportAdder:
    def __init__(self):
        # 加载合约所有者账户
        self.owner_account = self.load_owner_account()
        
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
        
        # 代币地址
        self.token_addresses = {
            'chain_a': '0x14D83c34ba0E1caC363039699d495e733B8A1182',
            'chain_b': '0x8Ce489412b110427695f051dAE4055d565BC7cF4'
        }
        
        # 初始化Web3连接
        self.web3_connections = {}
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
                        
                    except Exception as e:
                        print(f"❌ {config['name']} 合约加载失败: {e}")
                        self.bridge_contracts[chain_id] = None
                else:
                    print(f"❌ {config['name']} 连接失败")
            except Exception as e:
                print(f"❌ {config['name']} 连接错误: {e}")
    
    def add_supported_token(self, chain_id, token_address, token_name, token_symbol, token_decimals):
        """添加支持的代币到桥接合约"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        bridge_contract = self.bridge_contracts[chain_id]
        
        if not bridge_contract:
            raise Exception("桥接合约未加载")
        
        print(f"🔧 在 {config['name']} 上添加代币支持...")
        print(f"   代币地址: {token_address}")
        print(f"   代币名称: {token_name}")
        print(f"   代币符号: {token_symbol}")
        print(f"   代币精度: {token_decimals}")
        
        try:
            nonce = w3.w3.eth.get_transaction_count(self.owner_account.address)
            gas_price = w3.w3.eth.gas_price
            
            # 构建交易
            transaction = bridge_contract.functions.addSupportedToken(
                w3.w3.to_checksum_address(token_address),
                token_name,
                token_symbol,
                token_decimals
            ).build_transaction({
                'from': self.owner_account.address,
                'gas': 200000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': config['chain_id']
            })
            
            # 签名并发送交易
            signed_txn = w3.w3.eth.account.sign_transaction(transaction, self.owner_account.key)
            tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            print(f"✅ 添加代币支持交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            print("⏳ 等待交易确认...")
            receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                print(f"✅ 代币支持添加成功!")
                print(f"   交易哈希: {tx_hash.hex()}")
                print(f"   区块号: {receipt.blockNumber}")
                print(f"   Gas使用: {receipt.gasUsed}")
                return True
            else:
                print(f"❌ 代币支持添加失败")
                return False
                
        except Exception as e:
            print(f"❌ 添加代币支持错误: {e}")
            return False
    
    def check_token_support(self, chain_id, token_address):
        """检查代币是否被支持"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        bridge_contract = self.bridge_contracts[chain_id]
        
        try:
            is_supported = bridge_contract.functions.isTokenSupported(
                w3.w3.to_checksum_address(token_address)
            ).call()
            
            print(f"🔍 {config['name']} 代币 {token_address} 支持状态: {is_supported}")
            return is_supported
        except Exception as e:
            print(f"❌ 检查代币支持失败: {e}")
            return False
    
    def add_all_token_support(self):
        """添加所有代币支持"""
        print("🚀 开始添加所有代币支持...")
        print("=" * 50)
        
        results = {}
        
        for chain_id, config in self.chains.items():
            print(f"\n🔗 在 {config['name']} 上添加代币支持...")
            
            if chain_id not in self.web3_connections:
                print(f"❌ {config['name']} 连接失败，跳过")
                continue
            
            if not self.bridge_contracts[chain_id]:
                print(f"❌ {config['name']} 桥接合约未加载，跳过")
                continue
            
            # 检查当前支持状态
            print("   检查当前代币支持状态...")
            token_address = self.token_addresses[chain_id]
            is_supported = self.check_token_support(chain_id, token_address)
            
            if is_supported:
                print(f"   ✅ 代币已经支持")
                results[chain_id] = True
                continue
            
            # 添加代币支持
            success = self.add_supported_token(
                chain_id, 
                token_address, 
                "CrossChain Token", 
                "CCT", 
                18
            )
            results[chain_id] = success
            
            if success:
                # 再次检查支持状态
                print("   添加后状态检查...")
                is_supported_after = self.check_token_support(chain_id, token_address)
                if is_supported_after:
                    print(f"   ✅ 代币支持添加成功")
                else:
                    print(f"   ❌ 代币支持添加失败")
                    results[chain_id] = False
        
        # 保存结果
        with open('token_support_addition_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 添加结果已保存到 token_support_addition_results.json")
        
        success_count = sum(1 for result in results.values() if result)
        print(f"✅ 成功添加 {success_count} 个代币支持")
        
        return results

def main():
    print("🚀 启动代币支持添加...")
    
    adder = TokenSupportAdder()
    
    if len(adder.web3_connections) != 2:
        print("❌ Web3连接失败，无法进行添加")
        return
    
    if not adder.bridge_contracts['chain_a'] or not adder.bridge_contracts['chain_b']:
        print("❌ 桥接合约加载失败，无法进行添加")
        return
    
    # 添加所有代币支持
    results = adder.add_all_token_support()
    
    if all(results.values()):
        print("✅ 所有代币支持添加成功！")
        print("现在可以进行ERC20代币跨链转账了!")
    else:
        print("❌ 部分代币支持添加失败")

if __name__ == "__main__":
    main()

