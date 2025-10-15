#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web3 v6兼容的部署脚本
"""

import json
import time
from web3 import Web3
from pathlib import Path

def deploy_contract(w3, contract_name, constructor_args=None):
    """部署单个合约"""
    print(f"🔨 部署 {contract_name}...")
    
    # 加载合约JSON文件
    json_file = Path(f"{contract_name}.json")
    if not json_file.exists():
        print(f"❌ 未找到 {contract_name}.json")
        return None
    
    with open(json_file, 'r', encoding='utf-8') as f:
        contract_data = json.load(f)
    
    # 创建合约实例
    contract = w3.eth.contract(
        abi=contract_data['abi'],
        bytecode=contract_data['bytecode']
    )
    
    # 构建构造函数
    if constructor_args:
        constructor = contract.constructor(*constructor_args)
    else:
        constructor = contract.constructor()
    
    # 获取账户
    accounts = w3.eth.accounts
    if not accounts:
        print(f"❌ 没有可用账户")
        return None
    
    account = accounts[0]
    print(f"   使用账户: {account}")
    
    # 获取nonce
    nonce = w3.eth.get_transaction_count(account)
    print(f"   Nonce: {nonce}")
    
    # 构建交易
    transaction = constructor.build_transaction({
        'from': account,
        'nonce': nonce,
        'gas': 3000000,
        'gasPrice': w3.to_wei('1', 'gwei')
    })
    
    print(f"   交易详情: gas={transaction['gas']}, gasPrice={transaction['gasPrice']}")
    
    # 发送交易
    try:
        tx_hash = w3.eth.send_transaction(transaction)
        print(f"   交易哈希: {tx_hash.hex()}")
        
        # 等待确认
        print("   等待确认...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt.status == 1:
            print(f"✅ {contract_name} 部署成功: {receipt.contractAddress}")
            return receipt.contractAddress
        else:
            print(f"❌ {contract_name} 部署失败，交易状态: {receipt.status}")
            return None
            
    except Exception as e:
        print(f"❌ 部署 {contract_name} 时出错: {e}")
        return None

def test_web3_connection(w3, chain_name):
    """测试Web3连接"""
    print(f"🔍 测试 {chain_name} 连接...")
    
    try:
        # 检查连接
        is_connected = w3.is_connected()
        print(f"   连接状态: {is_connected}")
        
        if not is_connected:
            return False
        
        # 获取基本信息
        block_number = w3.eth.block_number
        print(f"   最新区块: {block_number}")
        
        accounts = w3.eth.accounts
        print(f"   账户数量: {len(accounts)}")
        
        if accounts:
            account = accounts[0]
            balance = w3.eth.get_balance(account)
            balance_eth = w3.from_wei(balance, 'ether')
            print(f"   第一个账户: {account}")
            print(f"   账户余额: {balance_eth} ETH")
            
            if balance == 0:
                print("   ⚠️  账户余额为0，可能无法部署合约")
                return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ 连接测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 Web3 v6兼容部署脚本")
    print("=" * 50)
    
    # 连接配置
    chains = [
        {
            'name': 'Besu Chain A',
            'url': 'http://localhost:8545',
            'chain_id': 'chain_a'
        },
        {
            'name': 'Besu Chain B', 
            'url': 'http://localhost:8555',
            'chain_id': 'chain_b'
        }
    ]
    
    deployment_results = {}
    
    for chain_config in chains:
        print(f"\n🔗 处理 {chain_config['name']}...")
        
        try:
            # 创建Web3实例
            w3 = Web3(Web3.HTTPProvider(chain_config['url']))
            
            # 测试连接
            if not test_web3_connection(w3, chain_config['name']):
                print(f"❌ 跳过 {chain_config['name']}")
                continue
            
            print(f"✅ {chain_config['name']} 连接成功")
            
            # 部署合约
            contracts = {}
            
            # 1. 部署CrossChainDIDVerifier
            verifier_address = deploy_contract(w3, 'CrossChainDIDVerifier')
            if not verifier_address:
                print(f"❌ 跳过 {chain_config['name']} 的后续部署")
                continue
            contracts['verifier'] = verifier_address
            
            # 2. 部署CrossChainBridge
            bridge_address = deploy_contract(w3, 'CrossChainBridge', [
                verifier_address,
                chain_config['chain_id'],
                2  # 支持锁定和解锁
            ])
            if not bridge_address:
                print(f"❌ 跳过 {chain_config['name']} 的后续部署")
                continue
            contracts['bridge'] = bridge_address
            
            # 3. 部署CrossChainToken
            token_name = f"CrossChain Token {chain_config['chain_id'].upper()}"
            token_symbol = f"CCT{chain_config['chain_id'][-1].upper()}"
            token_address = deploy_contract(w3, 'CrossChainToken', [
                token_name,
                token_symbol,
                18,  # decimals
                1000000 * 10**18,  # initial supply
                verifier_address
            ])
            if not token_address:
                print(f"❌ 跳过 {chain_config['name']} 的后续部署")
                continue
            contracts['token'] = token_address
            
            # 4. 部署AssetManager
            asset_manager_address = deploy_contract(w3, 'AssetManager', [
                verifier_address,
                bridge_address
            ])
            if not asset_manager_address:
                print(f"❌ 跳过 {chain_config['name']} 的后续部署")
                continue
            contracts['asset_manager'] = asset_manager_address
            
            deployment_results[chain_config['chain_id']] = {
                'chain_name': chain_config['name'],
                'rpc_url': chain_config['url'],
                'contracts': contracts
            }
            
            print(f"✅ {chain_config['name']} 部署完成")
            
        except Exception as e:
            print(f"❌ 处理 {chain_config['name']} 时出错: {e}")
            continue
    
    # 保存部署结果
    if deployment_results:
        with open('deployment_results.json', 'w', encoding='utf-8') as f:
            json.dump(deployment_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 部署结果已保存到: deployment_results.json")
        
        print("\n🎉 部署完成！")
        print("=" * 50)
        
        for chain_id, result in deployment_results.items():
            print(f"\n📋 {result['chain_name']}:")
            for contract_name, address in result['contracts'].items():
                print(f"   {contract_name}: {address}")
    else:
        print("\n❌ 没有成功部署任何合约")

if __name__ == "__main__":
    main()
