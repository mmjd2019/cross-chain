#!/usr/bin/env python3
"""
配置桥接合约支持ERC20代币
将代币添加到桥接合约的支持列表中
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

class BridgeTokenConfigurator:
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
        
        # 加载代币部署结果
        self.token_addresses = {}
        self.load_token_addresses()
        
        # 初始化Web3连接
        self.web3_connections = {}
        self.bridge_contracts = {}
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
        print("🔗 初始化Web3连接和桥接合约...")
        
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
                        print(f"❌ {config['name']} 桥接合约加载失败: {e}")
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
            nonce = w3.w3.eth.get_transaction_count(self.test_account.address)
            gas_price = w3.w3.eth.gas_price
            
            # 构建交易
            transaction = bridge_contract.functions.addSupportedToken(
                w3.w3.to_checksum_address(token_address),
                token_name,
                token_symbol,
                token_decimals
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
            
            print(f"✅ 添加代币交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            print("⏳ 等待交易确认...")
            receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                print(f"✅ 代币添加成功!")
                print(f"   交易哈希: {tx_hash.hex()}")
                print(f"   区块号: {receipt.blockNumber}")
                print(f"   Gas使用: {receipt.gasUsed}")
                return True
            else:
                print(f"❌ 代币添加失败")
                return False
                
        except Exception as e:
            print(f"❌ 添加代币失败: {e}")
            return False
    
    def configure_all_bridges(self):
        """配置所有桥接合约支持代币"""
        print("🚀 开始配置桥接合约支持ERC20代币...")
        print("=" * 50)
        
        configuration_results = {}
        
        for chain_id, config in self.chains.items():
            print(f"\n🔗 配置 {config['name']}...")
            
            if chain_id not in self.web3_connections:
                print(f"❌ {config['name']} 连接失败，跳过")
                continue
            
            if not self.bridge_contracts[chain_id]:
                print(f"❌ {config['name']} 桥接合约未加载，跳过")
                continue
            
            token_address = self.token_addresses[chain_id]
            
            # 添加代币支持
            success = self.add_supported_token(
                chain_id,
                token_address,
                "CrossChain Token",
                "CCT",
                18
            )
            
            if success:
                configuration_results[chain_id] = {
                    'chain_name': config['name'],
                    'token_address': token_address,
                    'token_name': "CrossChain Token",
                    'token_symbol': "CCT",
                    'token_decimals': 18,
                    'status': 'success'
                }
            else:
                configuration_results[chain_id] = {
                    'chain_name': config['name'],
                    'token_address': token_address,
                    'status': 'failed'
                }
        
        # 保存配置结果
        with open('bridge_token_configuration.json', 'w') as f:
            json.dump(configuration_results, f, indent=2)
        
        print(f"\n📄 配置结果已保存到 bridge_token_configuration.json")
        
        return configuration_results
    
    def verify_token_support(self, configuration_results):
        """验证代币支持配置"""
        print("\n🧪 验证代币支持配置...")
        print("=" * 50)
        
        for chain_id, result in configuration_results.items():
            if result['status'] != 'success':
                print(f"⏭️  跳过 {result['chain_name']} (配置失败)")
                continue
            
            print(f"\n🔍 验证 {result['chain_name']} 上的代币支持...")
            
            w3 = self.web3_connections[chain_id]
            bridge_contract = self.bridge_contracts[chain_id]
            token_address = result['token_address']
            
            try:
                # 检查代币是否支持
                is_supported = bridge_contract.functions.isTokenSupported(
                    w3.w3.to_checksum_address(token_address)
                ).call()
                
                if is_supported:
                    # 获取代币信息
                    token_info = bridge_contract.functions.getTokenInfo(
                        w3.w3.to_checksum_address(token_address)
                    ).call()
                    
                    print(f"✅ 代币支持验证成功")
                    print(f"   代币地址: {token_address}")
                    print(f"   代币名称: {token_info[0]}")
                    print(f"   代币符号: {token_info[1]}")
                    print(f"   代币精度: {token_info[2]}")
                    print(f"   是否活跃: {token_info[3]}")
                else:
                    print(f"❌ 代币支持验证失败")
                    
            except Exception as e:
                print(f"❌ 验证代币支持失败: {e}")

def main():
    print("🚀 启动桥接合约代币配置...")
    
    configurator = BridgeTokenConfigurator()
    
    if len(configurator.web3_connections) != 2:
        print("❌ Web3连接失败，无法进行配置")
        return
    
    if not configurator.bridge_contracts['chain_a'] or not configurator.bridge_contracts['chain_b']:
        print("❌ 桥接合约加载失败，无法进行配置")
        return
    
    # 配置桥接合约
    configuration_results = configurator.configure_all_bridges()
    
    # 验证配置
    configurator.verify_token_support(configuration_results)
    
    success_count = sum(1 for result in configuration_results.values() if result['status'] == 'success')
    
    if success_count > 0:
        print(f"\n✅ 成功配置 {success_count} 个桥接合约")
        print("现在可以使用ERC20代币进行跨链转账了")
    else:
        print("❌ 桥接合约配置失败")

if __name__ == "__main__":
    main()

