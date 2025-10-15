#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨链系统测试脚本
测试跨链交易功能
"""

import json
import time
from web3 import Web3
from typing import Dict, Any

class CrossChainTester:
    def __init__(self, deployment_file: str = "cross_chain_deployment.json"):
        """初始化测试器"""
        self.deployment_file = deployment_file
        self.deployment_data = self.load_deployment_data()
        self.chains = {}
        self.contracts = {}
        
    def load_deployment_data(self) -> Dict:
        """加载部署数据"""
        try:
            with open(self.deployment_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ 未找到部署文件: {self.deployment_file}")
            return {}
        except Exception as e:
            print(f"❌ 加载部署文件失败: {e}")
            return {}
    
    def connect_to_chains(self):
        """连接到链"""
        print("🔗 连接到Besu链...")
        
        for chain_id, contracts in self.deployment_data.get('chains', {}).items():
            chain_config = None
            for config in self.deployment_data.get('config', {}).get('chains', []):
                if config['chain_id'] == chain_id:
                    chain_config = config
                    break
            
            if not chain_config:
                print(f"❌ 未找到链配置: {chain_id}")
                continue
            
            try:
                w3 = Web3(Web3.HTTPProvider(chain_config['rpc_url']))
                if w3.is_connected():
                    self.chains[chain_id] = w3
                    self.contracts[chain_id] = contracts
                    print(f"✅ 已连接到 {chain_id}")
                else:
                    print(f"❌ 无法连接到 {chain_id}")
            except Exception as e:
                print(f"❌ 连接 {chain_id} 时出错: {e}")
    
    def load_contract_abi(self, contract_name: str) -> Dict:
        """加载合约ABI"""
        try:
            with open(f"{contract_name}.json", 'r', encoding='utf-8') as f:
                artifact = json.load(f)
                return artifact['abi']
        except FileNotFoundError:
            print(f"❌ 未找到合约文件: {contract_name}.json")
            return {}
        except Exception as e:
            print(f"❌ 加载合约ABI失败: {e}")
            return {}
    
    def test_identity_verification(self):
        """测试身份验证功能"""
        print("\n🧪 测试身份验证功能...")
        
        for chain_id, w3 in self.chains.items():
            print(f"\n📋 测试链 {chain_id}:")
            
            try:
                # 获取合约
                verifier_address = self.contracts[chain_id]['verifier']
                verifier_abi = self.load_contract_abi('CrossChainDIDVerifier')
                verifier_contract = w3.eth.contract(
                    address=verifier_address,
                    abi=verifier_abi
                )
                
                # 测试用户地址
                test_user = w3.eth.accounts[0]
                test_did = f"did:indy:testnet:{test_user[:8]}"
                
                # 验证身份
                tx_hash = verifier_contract.functions.verifyIdentity(
                    test_user, test_did
                ).transact({
                    'from': w3.eth.accounts[0],
                    'gas': 200000
                })
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
                
                if receipt.status == 1:
                    print(f"✅ 身份验证成功: {test_did}")
                    
                    # 验证身份状态
                    is_verified = verifier_contract.functions.isUserVerified(test_user).call()
                    user_did = verifier_contract.functions.getUserDID(test_user).call()
                    
                    print(f"   验证状态: {is_verified}")
                    print(f"   用户DID: {user_did}")
                else:
                    print(f"❌ 身份验证失败")
                    
            except Exception as e:
                print(f"❌ 测试身份验证时出错: {e}")
    
    def test_token_operations(self):
        """测试代币操作"""
        print("\n🪙 测试代币操作...")
        
        for chain_id, w3 in self.chains.items():
            print(f"\n📋 测试链 {chain_id}:")
            
            try:
                # 获取合约
                token_address = self.contracts[chain_id]['token']
                token_abi = self.load_contract_abi('CrossChainToken')
                token_contract = w3.eth.contract(
                    address=token_address,
                    abi=token_abi
                )
                
                # 测试用户
                test_user = w3.eth.accounts[0]
                
                # 查询余额
                balance = token_contract.functions.balanceOf(test_user).call()
                print(f"✅ 用户余额: {balance / 10**18:.2f} tokens")
                
                # 查询代币信息
                name = token_contract.functions.name().call()
                symbol = token_contract.functions.symbol().call()
                decimals = token_contract.functions.decimals().call()
                
                print(f"   代币名称: {name}")
                print(f"   代币符号: {symbol}")
                print(f"   代币精度: {decimals}")
                
            except Exception as e:
                print(f"❌ 测试代币操作时出错: {e}")
    
    def test_asset_manager(self):
        """测试资产管理器"""
        print("\n💼 测试资产管理器...")
        
        for chain_id, w3 in self.chains.items():
            print(f"\n📋 测试链 {chain_id}:")
            
            try:
                # 获取合约
                asset_manager_address = self.contracts[chain_id]['asset_manager']
                asset_manager_abi = self.load_contract_abi('AssetManager')
                asset_manager_contract = w3.eth.contract(
                    address=asset_manager_address,
                    abi=asset_manager_abi
                )
                
                # 测试用户
                test_user = w3.eth.accounts[0]
                
                # 查询ETH余额
                eth_balance = asset_manager_contract.functions.getETHBalance(test_user).call()
                print(f"✅ ETH余额: {eth_balance / 10**18:.4f} ETH")
                
                # 查询用户DID
                user_did = asset_manager_contract.functions.getUserDID(test_user).call()
                print(f"   用户DID: {user_did}")
                
                # 查询验证状态
                is_verified = asset_manager_contract.functions.isUserVerified(test_user).call()
                print(f"   验证状态: {is_verified}")
                
                # 查询部署消息
                message = asset_manager_contract.functions.getDeploymentMessage().call()
                print(f"   部署消息: {message}")
                
            except Exception as e:
                print(f"❌ 测试资产管理器时出错: {e}")
    
    def test_cross_chain_bridge(self):
        """测试跨链桥功能"""
        print("\n🌉 测试跨链桥功能...")
        
        for chain_id, w3 in self.chains.items():
            print(f"\n📋 测试链 {chain_id}:")
            
            try:
                # 获取合约
                bridge_address = self.contracts[chain_id]['bridge']
                bridge_abi = self.load_contract_abi('CrossChainBridge')
                bridge_contract = w3.eth.contract(
                    address=bridge_address,
                    abi=bridge_abi
                )
                
                # 查询链信息
                chain_id_info = bridge_contract.functions.chainId().call()
                chain_type = bridge_contract.functions.getChainTypeString().call()
                
                print(f"✅ 链ID: {chain_id_info}")
                print(f"   链类型: {chain_type}")
                
                # 查询桥统计
                stats = bridge_contract.functions.getBridgeStats().call()
                print(f"   总锁定数: {stats[0]}")
                print(f"   总解锁数: {stats[1]}")
                print(f"   总交易量: {stats[2]}")
                
                # 查询支持的代币
                token_address = self.contracts[chain_id]['token']
                is_supported = bridge_contract.functions.isTokenSupported(token_address).call()
                print(f"   代币支持状态: {is_supported}")
                
                if is_supported:
                    token_info = bridge_contract.functions.getTokenInfo(token_address).call()
                    print(f"   代币信息: {token_info[0]} ({token_info[1]})")
                
            except Exception as e:
                print(f"❌ 测试跨链桥时出错: {e}")
    
    def test_cross_chain_transfer_simulation(self):
        """模拟跨链转移测试"""
        print("\n🔄 模拟跨链转移测试...")
        
        if len(self.chains) < 2:
            print("❌ 需要至少两条链才能测试跨链转移")
            return
        
        chain_ids = list(self.chains.keys())
        source_chain = chain_ids[0]
        target_chain = chain_ids[1]
        
        print(f"📤 源链: {source_chain}")
        print(f"📥 目标链: {target_chain}")
        
        try:
            # 在源链上锁定资产
            print("\n1️⃣ 在源链上锁定资产...")
            source_w3 = self.chains[source_chain]
            source_bridge_address = self.contracts[source_chain]['bridge']
            source_bridge_abi = self.load_contract_abi('CrossChainBridge')
            source_bridge_contract = source_w3.eth.contract(
                address=source_bridge_address,
                abi=source_bridge_abi
            )
            
            # 模拟锁定交易
            test_user = source_w3.eth.accounts[0]
            token_address = self.contracts[source_chain]['token']
            amount = 100 * 10**18  # 100 tokens
            
            print(f"   用户: {test_user}")
            print(f"   代币: {token_address}")
            print(f"   数量: {amount / 10**18} tokens")
            print(f"   目标链: {target_chain}")
            
            # 注意：这里只是模拟，实际需要先验证用户身份和授权代币
            print("   ⚠️  注意：实际测试需要先验证用户身份和授权代币")
            
            # 在目标链上验证证明
            print("\n2️⃣ 在目标链上验证证明...")
            target_w3 = self.chains[target_chain]
            target_verifier_address = self.contracts[target_chain]['verifier']
            target_verifier_abi = self.load_contract_abi('CrossChainDIDVerifier')
            target_verifier_contract = target_w3.eth.contract(
                address=target_verifier_address,
                abi=target_verifier_abi
            )
            
            test_did = f"did:indy:testnet:{test_user[:8]}"
            
            # 模拟记录跨链证明
            print("   模拟记录跨链证明...")
            # 注意：实际需要Oracle服务来记录证明
            
            print("   ⚠️  注意：实际测试需要Oracle服务记录跨链证明")
            
            print("✅ 跨链转移模拟完成")
            
        except Exception as e:
            print(f"❌ 模拟跨链转移时出错: {e}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🧪 开始跨链系统测试...")
        print("=" * 50)
        
        if not self.deployment_data:
            print("❌ 没有部署数据，无法进行测试")
            return False
        
        # 连接链
        self.connect_to_chains()
        
        if not self.chains:
            print("❌ 没有可用的链连接")
            return False
        
        # 运行测试
        self.test_identity_verification()
        self.test_token_operations()
        self.test_asset_manager()
        self.test_cross_chain_bridge()
        self.test_cross_chain_transfer_simulation()
        
        print("\n" + "=" * 50)
        print("🎉 测试完成！")
        print("\n📖 注意事项:")
        print("1. 实际跨链转移需要Oracle服务支持")
        print("2. 需要先验证用户身份才能进行交易")
        print("3. 需要授权代币才能进行跨链转移")
        print("4. 建议在生产环境前进行更全面的测试")
        
        return True

def main():
    """主函数"""
    print("🧪 跨链系统测试工具")
    print("=" * 50)
    
    tester = CrossChainTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()
