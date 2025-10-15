#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用原始交易部署合约
"""

import json
import subprocess
import time
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

def call_rpc(url, method, params=None):
    """调用JSON-RPC API"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or [],
        "id": 1
    }
    
    try:
        result = subprocess.run([
            'curl', '-s', '-X', 'POST',
            '-H', 'Content-Type: application/json',
            '-d', json.dumps(payload),
            url
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            print(f"curl错误: {result.stderr}")
            return None
    except Exception as e:
        print(f"RPC调用失败: {e}")
        return None

def get_chain_id(url):
    """获取链ID"""
    response = call_rpc(url, "eth_chainId")
    if response and 'result' in response:
        return int(response['result'], 16)
    return None

def get_nonce(url, account):
    """获取账户nonce"""
    response = call_rpc(url, "eth_getTransactionCount", [account, "latest"])
    if response and 'result' in response:
        return int(response['result'], 16)
    return 0

def get_gas_price(url):
    """获取gas价格"""
    response = call_rpc(url, "eth_gasPrice")
    if response and 'result' in response:
        return int(response['result'], 16)
    return 1000000000  # 1 gwei

def send_raw_transaction(url, raw_tx):
    """发送原始交易"""
    response = call_rpc(url, "eth_sendRawTransaction", [raw_tx])
    if response and 'result' in response:
        return response['result']
    return None

def get_transaction_receipt(url, tx_hash):
    """获取交易收据"""
    response = call_rpc(url, "eth_getTransactionReceipt", [tx_hash])
    if response and 'result' in response:
        return response['result']
    return None

def deploy_contract(url, contract_name, private_key, constructor_args=None):
    """部署合约"""
    print(f"🔨 部署 {contract_name}...")
    
    # 加载合约JSON文件
    with open(f"{contract_name}.json", 'r') as f:
        contract_data = json.load(f)
    
    # 创建账户
    account = Account.from_key(private_key)
    print(f"   使用账户: {account.address}")
    
    # 获取链信息
    chain_id = get_chain_id(url)
    if not chain_id:
        print("❌ 无法获取链ID")
        return None
    print(f"   链ID: {chain_id}")
    
    # 获取nonce
    nonce = get_nonce(url, account.address)
    print(f"   Nonce: {nonce}")
    
    # 获取gas价格
    gas_price = get_gas_price(url)
    print(f"   Gas价格: {gas_price}")
    
    # 构建合约数据
    bytecode = contract_data['bytecode']
    
    # 如果有构造函数参数，需要编码
    if constructor_args:
        print(f"   构造函数参数: {constructor_args}")
        # 注意：实际部署时需要正确编码参数
    
    # 构建交易
    transaction = {
        'nonce': nonce,
        'gasPrice': gas_price,
        'gas': 3000000,
        'to': '',  # 空地址表示合约部署
        'value': 0,
        'data': bytecode,
        'chainId': chain_id
    }
    
    print(f"   交易详情: gas={transaction['gas']}, gasPrice={transaction['gasPrice']}")
    
    # 签名交易
    try:
        signed_txn = account.sign_transaction(transaction)
        raw_tx = signed_txn.rawTransaction.hex()
        print(f"   原始交易: {raw_tx[:100]}...")
    except Exception as e:
        print(f"❌ 签名交易失败: {e}")
        return None
    
    # 发送交易
    tx_hash = send_raw_transaction(url, raw_tx)
    if not tx_hash:
        print(f"❌ 发送交易失败")
        return None
    
    print(f"   交易哈希: {tx_hash}")
    
    # 等待确认
    print("   等待确认...")
    for i in range(30):  # 最多等待30秒
        time.sleep(1)
        receipt = get_transaction_receipt(url, tx_hash)
        if receipt:
            if receipt.get('status') == '0x1':
                contract_address = receipt.get('contractAddress')
                print(f"✅ {contract_name} 部署成功: {contract_address}")
                return contract_address
            else:
                print(f"❌ {contract_name} 部署失败，交易状态: {receipt.get('status')}")
                return None
        print(f"   等待中... ({i+1}/30)")
    
    print(f"❌ {contract_name} 部署超时")
    return None

def main():
    """主函数"""
    print("🚀 使用原始交易部署合约")
    print("=" * 50)
    
    # 预定义账户的私钥（这些是测试私钥，实际使用时应该使用安全的私钥）
    # 注意：这些私钥仅用于测试，实际部署时应该使用安全的私钥管理
    test_private_key = "0x" + "1" * 64  # 这是一个测试私钥
    
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
        
        # 测试连接
        print(f"🔍 测试连接...")
        response = call_rpc(chain_config['url'], "eth_blockNumber")
        if not response or 'result' not in response:
            print(f"❌ 无法连接到 {chain_config['name']}")
            continue
        
        block_number = int(response['result'], 16)
        print(f"✅ 连接成功，最新区块: {block_number}")
        
        # 部署合约
        contracts = {}
        
        # 1. 部署SimpleTest
        test_address = deploy_contract(chain_config['url'], 'SimpleTest', test_private_key)
        if not test_address:
            print(f"❌ 跳过 {chain_config['name']} 的后续部署")
            continue
        contracts['test'] = test_address
        
        # 2. 部署CrossChainDIDVerifier
        verifier_address = deploy_contract(chain_config['url'], 'CrossChainDIDVerifier', test_private_key)
        if not verifier_address:
            print(f"❌ 跳过 {chain_config['name']} 的后续部署")
            continue
        contracts['verifier'] = verifier_address
        
        # 3. 部署CrossChainBridge
        bridge_address = deploy_contract(chain_config['url'], 'CrossChainBridge', test_private_key)
        if not bridge_address:
            print(f"❌ 跳过 {chain_config['name']} 的后续部署")
            continue
        contracts['bridge'] = bridge_address
        
        # 4. 部署CrossChainToken
        token_address = deploy_contract(chain_config['url'], 'CrossChainToken', test_private_key)
        if not token_address:
            print(f"❌ 跳过 {chain_config['name']} 的后续部署")
            continue
        contracts['token'] = token_address
        
        # 5. 部署AssetManager
        asset_manager_address = deploy_contract(chain_config['url'], 'AssetManager', test_private_key)
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
