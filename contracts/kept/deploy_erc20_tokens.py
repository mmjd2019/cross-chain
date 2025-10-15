#!/usr/bin/env python3
"""
部署ERC20代币合约
为跨链转账准备代币合约
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

class ERC20TokenDeployer:
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
        
        # 代币配置
        self.token_config = {
            'name': 'CrossChain Token',
            'symbol': 'CCT',
            'decimals': 18,
            'initial_supply': 1000000  # 100万个代币
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
    
    def deploy_token_contract(self, chain_id):
        """部署ERC20代币合约"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        
        print(f"🚀 在 {config['name']} 上部署ERC20代币合约...")
        
        try:
            # 加载合约ABI
            with open('CrossChainToken.json', 'r') as f:
                token_abi = json.load(f)['abi']
            
            # 编译合约字节码
            with open('CrossChainToken.json', 'r') as f:
                token_data = json.load(f)
                bytecode = token_data['bytecode']
            
            # 准备构造函数参数
            initial_supply_wei = w3.w3.to_wei(self.token_config['initial_supply'], 'ether')
            constructor_args = [
                self.token_config['name'],
                self.token_config['symbol'],
                self.token_config['decimals'],
                initial_supply_wei,
                w3.w3.to_checksum_address(config['verifier_address'])
            ]
            
            # 构建合约
            contract = w3.w3.eth.contract(abi=token_abi, bytecode=bytecode)
            
            # 构建部署交易
            nonce = w3.w3.eth.get_transaction_count(self.test_account.address)
            gas_price = w3.w3.eth.gas_price
            
            transaction = contract.constructor(*constructor_args).build_transaction({
                'from': self.test_account.address,
                'gas': 2000000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': config['chain_id']
            })
            
            # 签名并发送交易
            signed_txn = w3.w3.eth.account.sign_transaction(transaction, self.test_account.key)
            tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            print(f"✅ 部署交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            print("⏳ 等待交易确认...")
            receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                contract_address = receipt.contractAddress
                print(f"✅ 代币合约部署成功!")
                print(f"   合约地址: {contract_address}")
                print(f"   交易哈希: {tx_hash.hex()}")
                print(f"   区块号: {receipt.blockNumber}")
                print(f"   Gas使用: {receipt.gasUsed}")
                
                return {
                    'address': contract_address,
                    'tx_hash': tx_hash.hex(),
                    'block_number': receipt.blockNumber,
                    'gas_used': receipt.gasUsed
                }
            else:
                print(f"❌ 代币合约部署失败")
                return None
                
        except Exception as e:
            print(f"❌ 代币合约部署错误: {e}")
            return None
    
    def deploy_all_tokens(self):
        """部署所有链上的代币合约"""
        print("🚀 开始部署ERC20代币合约...")
        print("=" * 50)
        
        deployment_results = {}
        
        for chain_id, config in self.chains.items():
            print(f"\n🔗 处理 {config['name']}...")
            
            if chain_id not in self.web3_connections:
                print(f"❌ {config['name']} 连接失败，跳过")
                continue
            
            result = self.deploy_token_contract(chain_id)
            if result:
                deployment_results[chain_id] = {
                    'chain_name': config['name'],
                    'token_name': self.token_config['name'],
                    'token_symbol': self.token_config['symbol'],
                    'token_decimals': self.token_config['decimals'],
                    'initial_supply': self.token_config['initial_supply'],
                    **result
                }
            else:
                print(f"❌ {config['name']} 代币合约部署失败")
        
        # 保存部署结果
        with open('erc20_deployment.json', 'w') as f:
            json.dump(deployment_results, f, indent=2)
        
        print(f"\n📄 部署结果已保存到 erc20_deployment.json")
        
        return deployment_results
    
    def test_token_contracts(self, deployment_results):
        """测试代币合约功能"""
        print("\n🧪 测试代币合约功能...")
        print("=" * 50)
        
        for chain_id, result in deployment_results.items():
            print(f"\n🔍 测试 {result['chain_name']} 上的代币合约...")
            
            w3 = self.web3_connections[chain_id]
            contract_address = result['address']
            
            try:
                # 加载合约ABI
                with open('CrossChainToken.json', 'r') as f:
                    token_abi = json.load(f)['abi']
                
                # 创建合约实例
                token_contract = w3.w3.eth.contract(
                    address=w3.w3.to_checksum_address(contract_address),
                    abi=token_abi
                )
                
                # 测试基本功能
                name = token_contract.functions.name().call()
                symbol = token_contract.functions.symbol().call()
                decimals = token_contract.functions.decimals().call()
                total_supply = token_contract.functions.totalSupply().call()
                balance = token_contract.functions.balanceOf(self.test_account.address).call()
                
                print(f"   代币名称: {name}")
                print(f"   代币符号: {symbol}")
                print(f"   小数位数: {decimals}")
                print(f"   总供应量: {w3.w3.from_wei(total_supply, 'ether')} {symbol}")
                print(f"   测试账户余额: {w3.w3.from_wei(balance, 'ether')} {symbol}")
                
                print(f"✅ {result['chain_name']} 代币合约测试成功")
                
            except Exception as e:
                print(f"❌ {result['chain_name']} 代币合约测试失败: {e}")

def main():
    print("🚀 启动ERC20代币合约部署...")
    
    deployer = ERC20TokenDeployer()
    
    if len(deployer.web3_connections) != 2:
        print("❌ Web3连接失败，无法进行部署")
        return
    
    # 部署代币合约
    deployment_results = deployer.deploy_all_tokens()
    
    if deployment_results:
        print(f"\n✅ 成功部署 {len(deployment_results)} 个代币合约")
        
        # 测试代币合约
        deployer.test_token_contracts(deployment_results)
        
        print(f"\n🎉 ERC20代币合约部署完成!")
        print("现在可以使用这些代币进行跨链转账了")
    else:
        print("❌ 代币合约部署失败")

if __name__ == "__main__":
    main()
