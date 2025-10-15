#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查已部署合约的状态
"""

import json
import subprocess
import time
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

def check_contract_code(url, contract_address, contract_name):
    """检查合约代码"""
    print(f"🔍 检查 {contract_name} ({contract_address})...")
    
    response = call_rpc(url, "eth_getCode", [contract_address, "latest"])
    if response and 'result' in response:
        code = response['result']
        if code == "0x":
            print(f"   ❌ 合约代码为空 - 合约未部署或部署失败")
            return False
        else:
            print(f"   ✅ 合约代码存在，长度: {len(code)} 字节")
            return True
    else:
        print(f"   ❌ 无法获取合约代码")
        return False

def check_contract_balance(url, contract_address, contract_name):
    """检查合约余额"""
    response = call_rpc(url, "eth_getBalance", [contract_address, "latest"])
    if response and 'result' in response:
        balance = int(response['result'], 16)
        balance_eth = balance / 10**18
        print(f"   💰 合约余额: {balance_eth} ETH")
        return balance_eth
    else:
        print(f"   ❌ 无法获取合约余额")
        return 0

def check_chain_status(url, chain_name):
    """检查链状态"""
    print(f"\n🔗 检查 {chain_name}...")
    
    # 检查连接
    response = call_rpc(url, "eth_blockNumber")
    if not response or 'result' not in response:
        print(f"❌ 无法连接到 {chain_name}")
        return False
    
    block_number = int(response['result'], 16)
    print(f"✅ 连接成功，最新区块: {block_number}")
    
    # 检查链ID
    response = call_rpc(url, "eth_chainId")
    if response and 'result' in response:
        chain_id = int(response['result'], 16)
        print(f"   链ID: {chain_id}")
    
    # 检查挖矿状态
    response = call_rpc(url, "eth_mining")
    if response and 'result' in response:
        mining = response['result']
        print(f"   挖矿状态: {'运行中' if mining else '已停止'}")
    
    return True

def main():
    """主函数"""
    print("🔍 检查已部署合约状态")
    print("=" * 50)
    
    # 已部署的合约地址
    deployed_contracts = {
        'chain_a': {
            'url': 'http://localhost:8545',
            'name': 'Besu Chain A',
            'contracts': {
                'SimpleTest': '0xae519fc2ba8e6ffe6473195c092bf1bae986ff90',
                'CrossChainDIDVerifier': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf',
                'SimpleBridge': '0x6e05f58eedda592f34dd9105b1827f252c509de0',
                'CrossChainBridgeSimple': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af',
                'SimpleAssetManager': '0xed8d61f42dc1e56ae992d333a4992c3796b22a74'
            }
        },
        'chain_b': {
            'url': 'http://localhost:8555',
            'name': 'Besu Chain B',
            'contracts': {
                'SimpleTest': '0xae519fc2ba8e6ffe6473195c092bf1bae986ff90',
                'CrossChainDIDVerifier': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf',
                'SimpleBridge': '0x6e05f58eedda592f34dd9105b1827f252c509de0',
                'CrossChainBridgeSimple': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af',
                'SimpleAssetManager': '0xed8d61f42dc1e56ae992d333a4992c3796b22a74'
            }
        }
    }
    
    check_results = {}
    total_contracts = 0
    successful_contracts = 0
    
    for chain_id, chain_info in deployed_contracts.items():
        print(f"\n{'='*60}")
        print(f"🔗 检查 {chain_info['name']}")
        print(f"{'='*60}")
        
        # 检查链状态
        if not check_chain_status(chain_info['url'], chain_info['name']):
            check_results[chain_id] = {
                'chain_name': chain_info['name'],
                'status': 'failed',
                'reason': '无法连接到链'
            }
            continue
        
        chain_results = {
            'chain_name': chain_info['name'],
            'rpc_url': chain_info['url'],
            'status': 'success',
            'contracts': {}
        }
        
        # 检查每个合约
        for contract_name, address in chain_info['contracts'].items():
            total_contracts += 1
            
            # 检查合约代码
            code_exists = check_contract_code(chain_info['url'], address, contract_name)
            
            # 检查合约余额
            balance = check_contract_balance(chain_info['url'], address, contract_name)
            
            contract_status = {
                'address': address,
                'code_exists': code_exists,
                'balance': balance,
                'status': 'success' if code_exists else 'failed'
            }
            
            chain_results['contracts'][contract_name] = contract_status
            
            if code_exists:
                successful_contracts += 1
                print(f"   ✅ {contract_name} 部署成功")
            else:
                print(f"   ❌ {contract_name} 部署失败")
        
        check_results[chain_id] = chain_results
    
    # 保存检查结果
    with open('contract_check_results.json', 'w', encoding='utf-8') as f:
        json.dump(check_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print("📊 检查结果总结")
    print(f"{'='*60}")
    
    # 显示检查结果
    for chain_id, result in check_results.items():
        if result['status'] == 'success':
            print(f"\n✅ {result['chain_name']}:")
            for contract_name, contract_result in result['contracts'].items():
                status_icon = "✅" if contract_result['code_exists'] else "❌"
                print(f"   {status_icon} {contract_name}: {contract_result['address']}")
        else:
            print(f"\n❌ {result['chain_name']}: {result['reason']}")
    
    # 统计信息
    print(f"\n📈 统计信息:")
    print(f"   总合约数: {total_contracts}")
    print(f"   成功部署: {successful_contracts}")
    print(f"   部署成功率: {successful_contracts/total_contracts*100:.1f}%")
    
    if successful_contracts == total_contracts:
        print(f"\n🎉 所有合约都已成功部署！")
    elif successful_contracts > 0:
        print(f"\n⚠️  部分合约部署成功，部分失败")
    else:
        print(f"\n❌ 所有合约部署都失败了")
    
    print(f"\n📄 详细检查结果已保存到: contract_check_results.json")

if __name__ == "__main__":
    main()
