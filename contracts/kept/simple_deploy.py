#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化部署脚本
直接部署合约到Besu链
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
    
    # 构建交易
    transaction = constructor.build_transaction({
        'from': w3.eth.accounts[0],
        'gas': 3000000,
        'gasPrice': w3.to_wei('1', 'gwei')
    })
    
    # 发送交易
    tx_hash = w3.eth.send_transaction(transaction)
    print(f"   交易哈希: {tx_hash.hex()}")
    
    # 等待确认
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    if receipt.status == 1:
        print(f"✅ {contract_name} 部署成功: {receipt.contractAddress}")
        return receipt.contractAddress
    else:
        print(f"❌ {contract_name} 部署失败")
        return None

def main():
    """主函数"""
    print("🚀 简化跨链系统部署")
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
        print(f"\n🔗 连接到 {chain_config['name']}...")
        
        try:
            # 连接Web3
            w3 = Web3(Web3.HTTPProvider(chain_config['url']))
            
            if not w3.is_connected():
                print(f"❌ 无法连接到 {chain_config['name']}")
                continue
            
            print(f"✅ 已连接到 {chain_config['name']}")
            
            # 检查账户
            accounts = w3.eth.accounts
            if not accounts:
                print(f"❌ {chain_config['name']} 没有可用账户")
                continue
            
            print(f"   账户: {accounts[0]}")
            balance = w3.eth.get_balance(accounts[0])
            print(f"   余额: {w3.from_wei(balance, 'ether')} ETH")
            
            # 部署合约
            contracts = {}
            
            # 1. 部署IERC20 (接口，不需要部署)
            print("⏭️  跳过 IERC20 (接口)")
            
            # 2. 部署CrossChainDIDVerifier
            verifier_address = deploy_contract(w3, 'CrossChainDIDVerifier')
            if verifier_address:
                contracts['verifier'] = verifier_address
            
            # 3. 部署CrossChainBridge
            bridge_address = deploy_contract(w3, 'CrossChainBridge', [
                verifier_address,
                chain_config['chain_id'],
                2  # 支持锁定和解锁
            ])
            if bridge_address:
                contracts['bridge'] = bridge_address
            
            # 4. 部署CrossChainToken
            token_name = f"CrossChain Token {chain_config['chain_id'].upper()}"
            token_symbol = f"CCT{chain_config['chain_id'][-1].upper()}"
            token_address = deploy_contract(w3, 'CrossChainToken', [
                token_name,
                token_symbol,
                18,  # decimals
                1000000 * 10**18,  # initial supply
                verifier_address
            ])
            if token_address:
                contracts['token'] = token_address
            
            # 5. 部署AssetManager
            asset_manager_address = deploy_contract(w3, 'AssetManager', [
                verifier_address,
                bridge_address
            ])
            if asset_manager_address:
                contracts['asset_manager'] = asset_manager_address
            
            deployment_results[chain_config['chain_id']] = {
                'chain_name': chain_config['name'],
                'rpc_url': chain_config['url'],
                'contracts': contracts
            }
            
            print(f"✅ {chain_config['name']} 部署完成")
            
        except Exception as e:
            print(f"❌ 部署 {chain_config['name']} 时出错: {e}")
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