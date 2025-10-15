#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用curl直接调用JSON-RPC API部署合约
"""

import json
import subprocess
import time
from pathlib import Path

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

def get_accounts(url):
    """获取账户列表"""
    response = call_rpc(url, "eth_accounts")
    if response and 'result' in response:
        return response['result']
    return []

def get_balance(url, account):
    """获取账户余额"""
    response = call_rpc(url, "eth_getBalance", [account, "latest"])
    if response and 'result' in response:
        return int(response['result'], 16)
    return 0

def get_nonce(url, account):
    """获取账户nonce"""
    response = call_rpc(url, "eth_getTransactionCount", [account, "latest"])
    if response and 'result' in response:
        return int(response['result'], 16)
    return 0

def send_transaction(url, transaction):
    """发送交易"""
    response = call_rpc(url, "eth_sendTransaction", [transaction])
    if response and 'result' in response:
        return response['result']
    return None

def get_transaction_receipt(url, tx_hash):
    """获取交易收据"""
    response = call_rpc(url, "eth_getTransactionReceipt", [tx_hash])
    if response and 'result' in response:
        return response['result']
    return None

def deploy_contract(url, contract_name, constructor_args=None):
    """部署合约"""
    print(f"🔨 部署 {contract_name}...")
    
    # 加载合约JSON文件
    json_file = Path(f"{contract_name}.json")
    if not json_file.exists():
        print(f"❌ 未找到 {contract_name}.json")
        return None
    
    with open(json_file, 'r', encoding='utf-8') as f:
        contract_data = json.load(f)
    
    # 获取账户
    accounts = get_accounts(url)
    if not accounts:
        print(f"❌ 没有可用账户")
        return None
    
    account = accounts[0]
    print(f"   使用账户: {account}")
    
    # 检查余额
    balance = get_balance(url, account)
    balance_eth = balance / 10**18
    print(f"   账户余额: {balance_eth} ETH")
    
    if balance == 0:
        print("   ⚠️  账户余额为0，可能无法部署合约")
        return None
    
    # 获取nonce
    nonce = get_nonce(url, account)
    print(f"   Nonce: {nonce}")
    
    # 构建合约数据
    bytecode = contract_data['bytecode']
    
    # 如果有构造函数参数，需要编码
    if constructor_args:
        # 这里简化处理，实际应该正确编码构造函数参数
        print(f"   构造函数参数: {constructor_args}")
        # 注意：实际部署时需要正确编码参数
    
    # 构建交易
    transaction = {
        "from": account,
        "data": "0x" + bytecode,
        "gas": "0x2DC6C0",  # 3000000
        "gasPrice": "0x3B9ACA00",  # 1 gwei
        "nonce": hex(nonce)
    }
    
    print(f"   交易详情: gas={transaction['gas']}, gasPrice={transaction['gasPrice']}")
    
    # 发送交易
    tx_hash = send_transaction(url, transaction)
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
    print("🚀 使用curl部署合约")
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
        
        # 测试连接
        print(f"🔍 测试连接...")
        response = call_rpc(chain_config['url'], "eth_blockNumber")
        if not response or 'result' not in response:
            print(f"❌ 无法连接到 {chain_config['name']}")
            continue
        
        block_number = int(response['result'], 16)
        print(f"✅ 连接成功，最新区块: {block_number}")
        
        # 获取账户
        accounts = get_accounts(chain_config['url'])
        if not accounts:
            print(f"❌ 没有可用账户")
            continue
        
        print(f"   账户数量: {len(accounts)}")
        account = accounts[0]
        balance = get_balance(chain_config['url'], account)
        balance_eth = balance / 10**18
        print(f"   第一个账户: {account}")
        print(f"   账户余额: {balance_eth} ETH")
        
        if balance == 0:
            print("   ⚠️  账户余额为0，跳过部署")
            continue
        
        # 部署合约
        contracts = {}
        
        # 1. 部署CrossChainDIDVerifier
        verifier_address = deploy_contract(chain_config['url'], 'CrossChainDIDVerifier')
        if not verifier_address:
            print(f"❌ 跳过 {chain_config['name']} 的后续部署")
            continue
        contracts['verifier'] = verifier_address
        
        # 2. 部署CrossChainBridge
        bridge_address = deploy_contract(chain_config['url'], 'CrossChainBridge')
        if not bridge_address:
            print(f"❌ 跳过 {chain_config['name']} 的后续部署")
            continue
        contracts['bridge'] = bridge_address
        
        # 3. 部署CrossChainToken
        token_address = deploy_contract(chain_config['url'], 'CrossChainToken')
        if not token_address:
            print(f"❌ 跳过 {chain_config['name']} 的后续部署")
            continue
        contracts['token'] = token_address
        
        # 4. 部署AssetManager
        asset_manager_address = deploy_contract(chain_config['url'], 'AssetManager')
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
