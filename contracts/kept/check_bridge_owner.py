#!/usr/bin/env python3
"""
检查桥接合约所有者
查看桥接合约的所有者信息
"""

import json
from web3_fixed_connection import FixedWeb3

class BridgeOwnerChecker:
    def __init__(self):
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
        
        # 初始化Web3连接
        self.web3_connections = {}
        self.bridge_contracts = {}
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
    
    def check_bridge_owner(self, chain_id):
        """检查桥接合约所有者"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        bridge_contract = self.bridge_contracts[chain_id]
        
        if not bridge_contract:
            raise Exception("桥接合约未加载")
        
        print(f"🔍 检查 {config['name']} 桥接合约所有者...")
        
        try:
            # 获取所有者地址
            owner = bridge_contract.functions.owner().call()
            print(f"   所有者地址: {owner}")
            
            # 获取桥接操作员地址
            bridge_operator = bridge_contract.functions.bridgeOperator().call()
            print(f"   桥接操作员: {bridge_operator}")
            
            # 获取链ID
            chain_id_from_contract = bridge_contract.functions.chainId().call()
            print(f"   链ID: {chain_id_from_contract}")
            
            # 获取链类型
            chain_type = bridge_contract.functions.chainType().call()
            print(f"   链类型: {chain_type}")
            
            return {
                'owner': owner,
                'bridge_operator': bridge_operator,
                'chain_id': chain_id_from_contract,
                'chain_type': chain_type
            }
            
        except Exception as e:
            print(f"❌ 检查桥接合约所有者失败: {e}")
            return None
    
    def check_all_bridge_owners(self):
        """检查所有桥接合约所有者"""
        print("🚀 开始检查所有桥接合约所有者...")
        print("=" * 50)
        
        results = {}
        
        for chain_id, config in self.chains.items():
            print(f"\n🔗 检查 {config['name']} 的桥接合约...")
            
            if chain_id not in self.web3_connections:
                print(f"❌ {config['name']} 连接失败，跳过")
                continue
            
            if not self.bridge_contracts[chain_id]:
                print(f"❌ {config['name']} 桥接合约未加载，跳过")
                continue
            
            result = self.check_bridge_owner(chain_id)
            results[chain_id] = {
                'chain_name': config['name'],
                'bridge_info': result
            }
        
        # 保存结果
        with open('bridge_owner_check_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 检查结果已保存到 bridge_owner_check_results.json")
        
        return results

def main():
    print("🚀 启动桥接合约所有者检查...")
    
    checker = BridgeOwnerChecker()
    
    if len(checker.web3_connections) != 2:
        print("❌ Web3连接失败，无法进行检查")
        return
    
    if not checker.bridge_contracts['chain_a'] or not checker.bridge_contracts['chain_b']:
        print("❌ 桥接合约加载失败，无法进行检查")
        return
    
    # 检查所有桥接合约所有者
    results = checker.check_all_bridge_owners()
    
    print("\n📋 检查结果总结:")
    for chain_id, result in results.items():
        if result['bridge_info']:
            print(f"   {result['chain_name']}: 所有者 = {result['bridge_info']['owner']}")
        else:
            print(f"   {result['chain_name']}: 检查失败")

if __name__ == "__main__":
    main()

