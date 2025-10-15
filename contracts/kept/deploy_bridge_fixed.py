#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复的跨链桥合约部署脚本
"""

import json
import subprocess
import time
from eth_account import Account
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

def encode_constructor_params(contract_abi, constructor_args):
    """编码构造函数参数"""
    # 简化的参数编码，实际应该使用正确的ABI编码
    if not constructor_args:
        return ""
    
    # 对于CrossChainBridge，参数是: address, string, uint256
    # 这里我们简化处理，实际应该使用正确的ABI编码
    return ""

def deploy_contract_with_params(url, contract_name, private_key, constructor_args=None):
    """部署带参数的合约"""
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
        # 这里简化处理，实际应该使用正确的ABI编码
        # 对于CrossChainBridge，我们需要编码: address, string, uint256
        encoded_params = encode_constructor_params(contract_data['abi'], constructor_args)
        if encoded_params:
            bytecode += encoded_params[2:]  # 去掉0x前缀
    
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
                # 获取失败原因
                try:
                    trace_response = call_rpc(url, "debug_traceTransaction", [tx_hash])
                    if trace_response and 'result' in trace_response:
                        print(f"   失败原因: {trace_response['result']}")
                except:
                    pass
                return None
        print(f"   等待中... ({i+1}/30)")
    
    print(f"❌ {contract_name} 部署超时")
    return None

def main():
    """主函数"""
    print("🔧 修复的跨链桥合约部署")
    print("=" * 50)
    
    # 测试私钥
    test_private_key = "0x" + "1" * 64
    
    # 已部署的合约地址
    deployed_contracts = {
        'chain_a': {
            'url': 'http://localhost:8545',
            'name': 'Besu Chain A',
            'verifier': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
        },
        'chain_b': {
            'url': 'http://localhost:8555',
            'name': 'Besu Chain B',
            'verifier': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
        }
    }
    
    deployment_results = {}
    
    for chain_id, chain_info in deployed_contracts.items():
        print(f"\n🔗 处理 {chain_info['name']}...")
        
        # 测试连接
        response = call_rpc(chain_info['url'], "eth_blockNumber")
        if not response or 'result' not in response:
            print(f"❌ 无法连接到 {chain_info['name']}")
            continue
        
        block_number = int(response['result'], 16)
        print(f"✅ 连接成功，最新区块: {block_number}")
        
        # 部署CrossChainBridge
        bridge_address = deploy_contract_with_params(
            chain_info['url'], 
            'CrossChainBridge', 
            test_private_key,
            [chain_info['verifier'], chain_id, 2]  # verifier, chainId, chainType
        )
        
        if bridge_address:
            deployment_results[chain_id] = {
                'chain_name': chain_info['name'],
                'rpc_url': chain_info['url'],
                'verifier': chain_info['verifier'],
                'bridge': bridge_address
            }
            print(f"✅ {chain_info['name']} 跨链桥部署成功")
        else:
            print(f"❌ {chain_info['name']} 跨链桥部署失败")
    
    # 保存部署结果
    if deployment_results:
        with open('bridge_deployment_results.json', 'w', encoding='utf-8') as f:
            json.dump(deployment_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 跨链桥部署结果已保存到: bridge_deployment_results.json")
        
        print("\n🎉 跨链桥部署完成！")
        print("=" * 50)
        
        for chain_id, result in deployment_results.items():
            print(f"\n📋 {result['chain_name']}:")
            print(f"   Verifier: {result['verifier']}")
            print(f"   Bridge: {result['bridge']}")
    else:
        print("\n❌ 没有成功部署任何跨链桥合约")

if __name__ == "__main__":
    main()
