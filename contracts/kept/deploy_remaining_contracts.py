#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
部署剩余合约并使用正确的ABI编码
"""

import json
import subprocess
import time
from eth_account import Account
from web3 import Web3
from eth_abi import encode

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

def encode_function_call(function_signature, params=None):
    """编码函数调用"""
    # 计算函数选择器
    function_selector = Web3.keccak(text=function_signature)[:4]
    
    if not params:
        return function_selector.hex()
    
    # 编码参数
    encoded_params = encode(['string'], [params]) if isinstance(params, str) else b''
    return (function_selector + encoded_params).hex()

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
        # 这里简化处理，实际应该使用正确的ABI编码
        # 对于CrossChainToken，参数是: string, string, uint8, uint256, address
        if contract_name == 'CrossChainToken' and len(constructor_args) == 5:
            # 编码参数: name, symbol, decimals, initialSupply, verifierAddress
            try:
                encoded_params = encode(
                    ['string', 'string', 'uint8', 'uint256', 'address'],
                    constructor_args
                )
                bytecode += encoded_params.hex()[2:]  # 去掉0x前缀
                print(f"   ✅ 构造函数参数编码成功")
            except Exception as e:
                print(f"   ⚠️  构造函数参数编码失败: {e}")
        elif contract_name == 'AssetManager' and len(constructor_args) == 2:
            # 编码参数: verifierAddress, bridgeAddress
            try:
                encoded_params = encode(
                    ['address', 'address'],
                    constructor_args
                )
                bytecode += encoded_params.hex()[2:]  # 去掉0x前缀
                print(f"   ✅ 构造函数参数编码成功")
            except Exception as e:
                print(f"   ⚠️  构造函数参数编码失败: {e}")
    
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

def test_contract_with_abi(url, contract_address, contract_name, abi):
    """使用ABI测试合约"""
    print(f"🧪 测试 {contract_name}...")
    
    # 检查合约代码
    response = call_rpc(url, "eth_getCode", [contract_address, "latest"])
    if response and 'result' in response:
        code = response['result']
        if code == "0x":
            print(f"   ❌ 合约代码为空")
            return False
        else:
            print(f"   ✅ 合约代码存在，长度: {len(code)}")
    
    # 测试owner函数
    try:
        owner_call = encode_function_call("owner()")
        response = call_rpc(url, "eth_call", [{
            "to": contract_address,
            "data": "0x" + owner_call
        }, "latest"])
        
        if response and 'result' in response:
            result = response['result']
            if result != "0x":
                print(f"   ✅ owner函数调用成功: {result}")
            else:
                print(f"   ⚠️  owner函数返回空")
        else:
            print(f"   ❌ owner函数调用失败")
    except Exception as e:
        print(f"   ❌ owner函数调用出错: {e}")
    
    # 测试特定合约的函数
    if contract_name == "CrossChainToken":
        try:
            # 测试name函数
            name_call = encode_function_call("name()")
            response = call_rpc(url, "eth_call", [{
                "to": contract_address,
                "data": "0x" + name_call
            }, "latest"])
            
            if response and 'result' in response:
                result = response['result']
                if result != "0x":
                    print(f"   ✅ name函数调用成功: {result}")
                else:
                    print(f"   ⚠️  name函数返回空")
        except Exception as e:
            print(f"   ❌ name函数调用出错: {e}")
    
    elif contract_name == "AssetManager":
        try:
            # 测试getDeploymentMessage函数
            message_call = encode_function_call("getDeploymentMessage()")
            response = call_rpc(url, "eth_call", [{
                "to": contract_address,
                "data": "0x" + message_call
            }, "latest"])
            
            if response and 'result' in response:
                result = response['result']
                if result != "0x":
                    print(f"   ✅ getDeploymentMessage函数调用成功: {result}")
                else:
                    print(f"   ⚠️  getDeploymentMessage函数返回空")
        except Exception as e:
            print(f"   ❌ getDeploymentMessage函数调用出错: {e}")
    
    return True

def main():
    """主函数"""
    print("🚀 部署剩余合约并使用正确ABI编码")
    print("=" * 50)
    
    # 测试私钥
    test_private_key = "0x" + "1" * 64
    
    # 已部署的合约地址
    deployed_contracts = {
        'chain_a': {
            'url': 'http://localhost:8545',
            'name': 'Besu Chain A',
            'verifier': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf',
            'bridge': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af'
        },
        'chain_b': {
            'url': 'http://localhost:8555',
            'name': 'Besu Chain B',
            'verifier': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf',
            'bridge': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af'
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
        
        contracts = {}
        
        # 1. 部署CrossChainToken
        token_name = f"CrossChain Token {chain_id.upper()}"
        token_symbol = f"CCT{chain_id[-1].upper()}"
        token_address = deploy_contract(
            chain_info['url'], 
            'CrossChainToken', 
            test_private_key,
            [token_name, token_symbol, 18, 1000000 * 10**18, chain_info['verifier']]
        )
        
        if token_address:
            contracts['token'] = token_address
            # 加载ABI进行测试
            with open('CrossChainToken.json', 'r') as f:
                token_abi = json.load(f)['abi']
            test_contract_with_abi(chain_info['url'], token_address, 'CrossChainToken', token_abi)
        
        # 2. 部署AssetManager
        asset_manager_address = deploy_contract(
            chain_info['url'], 
            'AssetManager', 
            test_private_key,
            [chain_info['verifier'], chain_info['bridge']]
        )
        
        if asset_manager_address:
            contracts['asset_manager'] = asset_manager_address
            # 加载ABI进行测试
            with open('AssetManager.json', 'r') as f:
                asset_manager_abi = json.load(f)['abi']
            test_contract_with_abi(chain_info['url'], asset_manager_address, 'AssetManager', asset_manager_abi)
        
        if contracts:
            deployment_results[chain_id] = {
                'chain_name': chain_info['name'],
                'rpc_url': chain_info['url'],
                'verifier': chain_info['verifier'],
                'bridge': chain_info['bridge'],
                'contracts': contracts
            }
            print(f"✅ {chain_info['name']} 剩余合约部署完成")
        else:
            print(f"❌ {chain_info['name']} 剩余合约部署失败")
    
    # 保存部署结果
    if deployment_results:
        with open('remaining_contracts_deployment_results.json', 'w', encoding='utf-8') as f:
            json.dump(deployment_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 剩余合约部署结果已保存到: remaining_contracts_deployment_results.json")
        
        print("\n🎉 剩余合约部署完成！")
        print("=" * 50)
        
        for chain_id, result in deployment_results.items():
            print(f"\n📋 {result['chain_name']}:")
            print(f"   Verifier: {result['verifier']}")
            print(f"   Bridge: {result['bridge']}")
            for contract_name, address in result['contracts'].items():
                print(f"   {contract_name}: {address}")
    else:
        print("\n❌ 没有成功部署任何剩余合约")

if __name__ == "__main__":
    main()
