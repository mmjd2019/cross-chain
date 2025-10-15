#!/usr/bin/env python3
"""
查找合约所有者私钥
尝试从部署记录中找到合约所有者的私钥
"""

import json
import os
import glob
from web3_fixed_connection import FixedWeb3
from eth_account import Account

class ContractOwnerFinder:
    def __init__(self):
        self.target_owner = "0x19E7E376E7C213B7E7e7e46cc70A5dD086DAff2A"
        self.test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
        
        # 链配置
        self.chains = {
            'chain_a': {
                'name': 'Besu Chain A',
                'rpc_url': 'http://localhost:8545',
                'chain_id': 2023
            },
            'chain_b': {
                'name': 'Besu Chain B', 
                'rpc_url': 'http://localhost:8555',
                'chain_id': 2024
            }
        }
        
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
    
    def search_deployment_files(self):
        """搜索部署文件中的私钥信息"""
        print("🔍 搜索部署文件中的私钥信息...")
        
        # 搜索所有JSON文件
        json_files = glob.glob("*.json")
        print(f"找到 {len(json_files)} 个JSON文件")
        
        found_keys = []
        
        for file_path in json_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                # 递归搜索私钥
                keys = self.extract_private_keys(data, file_path)
                found_keys.extend(keys)
                
            except Exception as e:
                print(f"⚠️  读取文件 {file_path} 失败: {e}")
        
        return found_keys
    
    def extract_private_keys(self, data, file_path):
        """从数据中提取私钥"""
        keys = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and value.startswith('0x') and len(value) == 66:
                    # 可能是私钥
                    try:
                        account = Account.from_key(value)
                        if account.address.lower() == self.target_owner.lower():
                            keys.append({
                                'file': file_path,
                                'key': value,
                                'address': account.address,
                                'context': key
                            })
                            print(f"✅ 在 {file_path} 中找到匹配的私钥: {value}")
                    except:
                        pass
                
                elif isinstance(value, (dict, list)):
                    # 递归搜索
                    keys.extend(self.extract_private_keys(value, file_path))
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                keys.extend(self.extract_private_keys(item, file_path))
        
        return keys
    
    def test_private_key(self, private_key):
        """测试私钥是否有效"""
        try:
            account = Account.from_key(private_key)
            print(f"🔑 测试私钥: {private_key}")
            print(f"   地址: {account.address}")
            print(f"   目标地址: {self.target_owner}")
            print(f"   匹配: {account.address.lower() == self.target_owner.lower()}")
            
            if account.address.lower() == self.target_owner.lower():
                return True
        except Exception as e:
            print(f"❌ 私钥无效: {e}")
        
        return False
    
    def check_contract_ownership(self, chain_id, private_key):
        """检查私钥是否是合约所有者"""
        w3 = self.web3_connections[chain_id]
        config = self.chains[chain_id]
        
        try:
            account = Account.from_key(private_key)
            
            # 检查验证器合约所有者
            verifier_address = "0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf"
            
            with open('CrossChainDIDVerifier.json', 'r') as f:
                verifier_abi = json.load(f)['abi']
            
            verifier_contract = w3.w3.eth.contract(
                address=w3.w3.to_checksum_address(verifier_address),
                abi=verifier_abi
            )
            
            owner = verifier_contract.functions.owner().call()
            is_owner = owner.lower() == account.address.lower()
            
            print(f"🔍 {config['name']} 验证器合约所有者检查:")
            print(f"   合约所有者: {owner}")
            print(f"   私钥地址: {account.address}")
            print(f"   是否匹配: {is_owner}")
            
            return is_owner
            
        except Exception as e:
            print(f"❌ 检查合约所有者失败: {e}")
            return False
    
    def find_owner_private_key(self):
        """查找合约所有者的私钥"""
        print("🚀 开始查找合约所有者私钥...")
        print("=" * 50)
        
        # 搜索部署文件
        found_keys = self.search_deployment_files()
        
        if not found_keys:
            print("❌ 未在部署文件中找到匹配的私钥")
            return None
        
        print(f"\n📋 找到 {len(found_keys)} 个可能的私钥:")
        for i, key_info in enumerate(found_keys):
            print(f"   {i+1}. 文件: {key_info['file']}")
            print(f"      上下文: {key_info['context']}")
            print(f"      地址: {key_info['address']}")
            print(f"      私钥: {key_info['key']}")
            print()
        
        # 测试每个私钥
        for i, key_info in enumerate(found_keys):
            print(f"🧪 测试私钥 {i+1}...")
            
            if self.test_private_key(key_info['key']):
                print(f"✅ 私钥 {i+1} 地址匹配!")
                
                # 检查合约所有者权限
                for chain_id, config in self.chains.items():
                    if chain_id in self.web3_connections:
                        is_owner = self.check_contract_ownership(chain_id, key_info['key'])
                        if is_owner:
                            print(f"✅ 私钥 {i+1} 是 {config['name']} 的合约所有者!")
                            return key_info['key']
                
                print(f"⚠️  私钥 {i+1} 地址匹配但不是合约所有者")
            else:
                print(f"❌ 私钥 {i+1} 地址不匹配")
        
        print("❌ 未找到有效的合约所有者私钥")
        return None
    
    def create_owner_account_file(self, private_key):
        """创建所有者账户文件"""
        if not private_key:
            return
        
        owner_info = {
            "private_key": private_key,
            "address": Account.from_key(private_key).address,
            "description": "合约所有者账户",
            "usage": "用于管理合约权限和配置"
        }
        
        with open('contract_owner_account.json', 'w') as f:
            json.dump(owner_info, f, indent=2)
        
        print(f"📄 所有者账户信息已保存到 contract_owner_account.json")
        print(f"   地址: {owner_info['address']}")
        print(f"   私钥: {owner_info['private_key']}")

def main():
    print("🚀 启动合约所有者私钥查找...")
    
    finder = ContractOwnerFinder()
    
    if len(finder.web3_connections) != 2:
        print("❌ Web3连接失败，无法进行查找")
        return
    
    # 查找私钥
    private_key = finder.find_owner_private_key()
    
    if private_key:
        print(f"\n✅ 找到合约所有者私钥!")
        finder.create_owner_account_file(private_key)
        print("现在可以使用这个私钥来管理合约权限了")
    else:
        print(f"\n❌ 未找到合约所有者私钥")
        print("建议使用方案3创建简化的跨链转账系统")

if __name__ == "__main__":
    main()

