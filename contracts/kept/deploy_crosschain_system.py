#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨链系统部署脚本
支持在多个Besu链上部署完整的跨链交易系统
"""

import json
import time
import os
from web3 import Web3
from typing import Dict, List, Any

class CrossChainDeployer:
    def __init__(self, config_file: str = None):
        """初始化部署器"""
        self.config = self.load_config(config_file)
        self.chains = {}
        self.deployed_contracts = {}
        
    def load_config(self, config_file: str = None) -> Dict:
        """加载配置文件"""
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # 默认配置
        return {
            "chains": [
                {
                    "name": "Besu Chain A",
                    "rpc_url": "http://localhost:8545",
                    "chain_id": "chain_a",
                    "chain_type": 2,  # 0=source, 1=destination, 2=both
                    "private_key": "0x...",  # 需要替换为实际私钥
                    "gas_price": 1000000000,  # 1 gwei
                    "gas_limit": 3000000
                },
                {
                    "name": "Besu Chain B",
                    "rpc_url": "http://localhost:8555",
                    "chain_id": "chain_b", 
                    "chain_type": 2,  # 0=source, 1=destination, 2=both
                    "private_key": "0x...",  # 需要替换为实际私钥
                    "gas_price": 1000000000,  # 1 gwei
                    "gas_limit": 3000000
                }
            ],
            "tokens": [
                {
                    "name": "CrossChain Token A",
                    "symbol": "CCTA",
                    "decimals": 18,
                    "initial_supply": 1000000 * 10**18
                },
                {
                    "name": "CrossChain Token B", 
                    "symbol": "CCTB",
                    "decimals": 18,
                    "initial_supply": 1000000 * 10**18
                }
            ]
        }
    
    def connect_to_chains(self):
        """连接到所有配置的链"""
        print("🔗 连接到Besu链...")
        
        for chain_config in self.config['chains']:
            try:
                w3 = Web3(Web3.HTTPProvider(chain_config['rpc_url']))
                if w3.is_connected():
                    self.chains[chain_config['chain_id']] = {
                        'w3': w3,
                        'config': chain_config
                    }
                    print(f"✅ 已连接到 {chain_config['name']} ({chain_config['rpc_url']})")
                else:
                    print(f"❌ 无法连接到 {chain_config['name']} ({chain_config['rpc_url']})")
            except Exception as e:
                print(f"❌ 连接 {chain_config['name']} 时出错: {e}")
    
    def load_contract_artifacts(self):
        """加载合约编译产物"""
        artifacts = {}
        contract_files = [
            'CrossChainDIDVerifier',
            'CrossChainBridge', 
            'CrossChainToken',
            'AssetManager'
        ]
        
        for contract_name in contract_files:
            artifact_file = f"{contract_name}.json"
            if os.path.exists(artifact_file):
                with open(artifact_file, 'r', encoding='utf-8') as f:
                    artifacts[contract_name] = json.load(f)
                print(f"✅ 已加载 {contract_name} 合约")
            else:
                print(f"⚠️  未找到 {contract_name} 合约文件")
        
        return artifacts
    
    def deploy_contract(self, w3: Web3, contract_artifact: Dict, constructor_args: List = None) -> str:
        """部署单个合约"""
        try:
            contract = w3.eth.contract(
                abi=contract_artifact['abi'],
                bytecode=contract_artifact['bytecode']
            )
            
            if constructor_args:
                constructor = contract.constructor(*constructor_args)
            else:
                constructor = contract.constructor()
            
            # 构建交易
            transaction = constructor.build_transaction({
                'from': w3.eth.accounts[0],
                'gas': 3000000,
                'gasPrice': w3.to_wei('1', 'gwei')
            })
            
            # 发送交易
            tx_hash = w3.eth.send_transaction(transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            
            return receipt.contractAddress
            
        except Exception as e:
            print(f"❌ 部署合约失败: {e}")
            return None
    
    def deploy_chain_system(self, chain_id: str, artifacts: Dict):
        """在单条链上部署完整系统"""
        print(f"\n🚀 开始在 {chain_id} 上部署系统...")
        
        chain_info = self.chains[chain_id]
        w3 = chain_info['w3']
        config = chain_info['config']
        
        deployed = {}
        
        # 1. 部署CrossChainDIDVerifier
        print("📋 部署 CrossChainDIDVerifier...")
        verifier_address = self.deploy_contract(w3, artifacts['CrossChainDIDVerifier'])
        if verifier_address:
            deployed['verifier'] = verifier_address
            print(f"✅ CrossChainDIDVerifier: {verifier_address}")
        else:
            print("❌ CrossChainDIDVerifier 部署失败")
            return None
        
        # 2. 部署CrossChainBridge
        print("🌉 部署 CrossChainBridge...")
        bridge_address = self.deploy_contract(
            w3, 
            artifacts['CrossChainBridge'],
            [verifier_address, config['chain_id'], config['chain_type']]
        )
        if bridge_address:
            deployed['bridge'] = bridge_address
            print(f"✅ CrossChainBridge: {bridge_address}")
        else:
            print("❌ CrossChainBridge 部署失败")
            return None
        
        # 3. 部署CrossChainToken
        print("🪙 部署 CrossChainToken...")
        token_config = self.config['tokens'][0] if chain_id == 'chain_a' else self.config['tokens'][1]
        token_address = self.deploy_contract(
            w3,
            artifacts['CrossChainToken'],
            [
                token_config['name'],
                token_config['symbol'], 
                token_config['decimals'],
                token_config['initial_supply'],
                verifier_address
            ]
        )
        if token_address:
            deployed['token'] = token_address
            print(f"✅ CrossChainToken: {token_address}")
        else:
            print("❌ CrossChainToken 部署失败")
            return None
        
        # 4. 部署AssetManager
        print("💼 部署 AssetManager...")
        asset_manager_address = self.deploy_contract(
            w3,
            artifacts['AssetManager'],
            [verifier_address, bridge_address]
        )
        if asset_manager_address:
            deployed['asset_manager'] = asset_manager_address
            print(f"✅ AssetManager: {asset_manager_address}")
        else:
            print("❌ AssetManager 部署失败")
            return None
        
        # 5. 配置合约
        print("⚙️  配置合约...")
        self.configure_contracts(w3, deployed, config)
        
        return deployed
    
    def configure_contracts(self, w3: Web3, contracts: Dict, config: Dict):
        """配置已部署的合约"""
        try:
            # 配置DIDVerifier
            verifier_contract = w3.eth.contract(
                address=contracts['verifier'],
                abi=self.load_contract_artifacts()['CrossChainDIDVerifier']['abi']
            )
            
            # 添加支持的链
            for chain_config in self.config['chains']:
                tx_hash = verifier_contract.functions.addSupportedChain(chain_config['chain_id']).transact({
                    'from': w3.eth.accounts[0],
                    'gas': 200000
                })
                w3.eth.wait_for_transaction_receipt(tx_hash)
                print(f"✅ 添加支持链: {chain_config['chain_id']}")
            
            # 设置桥合约为Oracle
            tx_hash = verifier_contract.functions.setCrossChainOracle(contracts['bridge']).transact({
                'from': w3.eth.accounts[0],
                'gas': 200000
            })
            w3.eth.wait_for_transaction_receipt(tx_hash)
            print("✅ 设置桥合约为Oracle")
            
            # 配置桥合约
            bridge_contract = w3.eth.contract(
                address=contracts['bridge'],
                abi=self.load_contract_artifacts()['CrossChainBridge']['abi']
            )
            
            # 添加支持的代币
            token_config = self.config['tokens'][0] if config['chain_id'] == 'chain_a' else self.config['tokens'][1]
            tx_hash = bridge_contract.functions.addSupportedToken(
                contracts['token'],
                token_config['name'],
                token_config['symbol'],
                token_config['decimals']
            ).transact({
                'from': w3.eth.accounts[0],
                'gas': 200000
            })
            w3.eth.wait_for_transaction_receipt(tx_hash)
            print(f"✅ 添加支持代币: {token_config['symbol']}")
            
            # 配置代币合约
            token_contract = w3.eth.contract(
                address=contracts['token'],
                abi=self.load_contract_artifacts()['CrossChainToken']['abi']
            )
            
            # 设置桥合约为铸造者
            tx_hash = token_contract.functions.setMinter(contracts['bridge']).transact({
                'from': w3.eth.accounts[0],
                'gas': 200000
            })
            w3.eth.wait_for_transaction_receipt(tx_hash)
            print("✅ 设置桥合约为铸造者")
            
            # 授权桥合约
            tx_hash = token_contract.functions.setCrossChainBridge(contracts['bridge'], True).transact({
                'from': w3.eth.accounts[0],
                'gas': 200000
            })
            w3.eth.wait_for_transaction_receipt(tx_hash)
            print("✅ 授权桥合约")
            
        except Exception as e:
            print(f"❌ 配置合约时出错: {e}")
    
    def deploy_all_chains(self):
        """部署所有链的系统"""
        print("🚀 开始部署跨链系统...")
        
        # 连接链
        self.connect_to_chains()
        
        if not self.chains:
            print("❌ 没有可用的链连接")
            return False
        
        # 加载合约
        artifacts = self.load_contract_artifacts()
        if not artifacts:
            print("❌ 没有可用的合约文件")
            return False
        
        # 部署每条链
        for chain_id in self.chains:
            deployed = self.deploy_chain_system(chain_id, artifacts)
            if deployed:
                self.deployed_contracts[chain_id] = deployed
                print(f"✅ {chain_id} 部署完成")
            else:
                print(f"❌ {chain_id} 部署失败")
        
        # 保存部署结果
        self.save_deployment_results()
        
        return len(self.deployed_contracts) > 0
    
    def save_deployment_results(self):
        """保存部署结果"""
        results = {
            "deployment_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "chains": self.deployed_contracts,
            "config": self.config
        }
        
        with open('cross_chain_deployment.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 部署结果已保存到 cross_chain_deployment.json")
        print("=" * 50)
        print("🎉 跨链系统部署完成！")
        print("=" * 50)
        
        for chain_id, contracts in self.deployed_contracts.items():
            print(f"\n📋 {chain_id.upper()}:")
            for name, address in contracts.items():
                print(f"  {name}: {address}")

def main():
    """主函数"""
    print("🌐 跨链系统部署工具")
    print("=" * 50)
    
    deployer = CrossChainDeployer()
    success = deployer.deploy_all_chains()
    
    if success:
        print("\n✅ 所有链部署成功！")
        print("\n📖 使用说明:")
        print("1. 确保两条Besu链都在运行")
        print("2. 使用部署的合约地址进行跨链交易")
        print("3. 通过AssetManager合约管理资产")
        print("4. 使用CrossChainBridge进行跨链转移")
    else:
        print("\n❌ 部署失败，请检查配置和链连接")

if __name__ == "__main__":
    main()
