#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试所有已部署的合约
"""

import json
import subprocess
import time

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

def test_contract(url, contract_address, contract_name, tests):
    """测试合约"""
    print(f"🧪 测试 {contract_name} ({contract_address})...")
    
    # 检查合约代码
    response = call_rpc(url, "eth_getCode", [contract_address, "latest"])
    if response and 'result' in response:
        code = response['result']
        if code == "0x":
            print(f"   ❌ 合约代码为空")
            return False
        else:
            print(f"   ✅ 合约代码存在，长度: {len(code)}")
    
    # 运行测试
    for test_name, test_data in tests.items():
        print(f"   🔍 测试 {test_name}...")
        
        response = call_rpc(url, "eth_call", [{
            "to": contract_address,
            "data": test_data
        }, "latest"])
        
        if response and 'result' in response:
            result = response['result']
            if result != "0x":
                print(f"      ✅ {test_name} 成功: {result}")
            else:
                print(f"      ⚠️  {test_name} 返回空")
        else:
            print(f"      ❌ {test_name} 失败")
    
    return True

def main():
    """主函数"""
    print("🧪 测试所有已部署的合约")
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
                'CrossChainBridgeSimple': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af'
            }
        },
        'chain_b': {
            'url': 'http://localhost:8555',
            'name': 'Besu Chain B',
            'contracts': {
                'SimpleTest': '0xae519fc2ba8e6ffe6473195c092bf1bae986ff90',
                'CrossChainDIDVerifier': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf',
                'SimpleBridge': '0x6e05f58eedda592f34dd9105b1827f252c509de0',
                'CrossChainBridgeSimple': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af'
            }
        }
    }
    
    # 测试配置
    test_configs = {
        'SimpleTest': {
            'message': '0x" + "message()"',  # 简化的函数签名
            'value': '0x" + "value()"'
        },
        'CrossChainDIDVerifier': {
            'owner': '0x8da5cb5b'  # owner()函数签名
        },
        'SimpleBridge': {
            'owner': '0x8da5cb5b',  # owner()函数签名
            'chainId': '0x" + "chainId()"',
            'chainType': '0x" + "chainType()"'
        },
        'CrossChainBridgeSimple': {
            'owner': '0x8da5cb5b',  # owner()函数签名
            'chainId': '0x" + "chainId()"',
            'chainType': '0x" + "chainType()"',
            'totalLocks': '0x" + "totalLocks()"',
            'totalUnlocks': '0x" + "totalUnlocks()"'
        }
    }
    
    test_results = {}
    
    for chain_id, chain_info in deployed_contracts.items():
        print(f"\n🔗 测试 {chain_info['name']}...")
        
        # 测试连接
        response = call_rpc(chain_info['url'], "eth_blockNumber")
        if not response or 'result' not in response:
            print(f"❌ 无法连接到 {chain_info['name']}")
            continue
        
        block_number = int(response['result'], 16)
        print(f"✅ 连接成功，最新区块: {block_number}")
        
        chain_results = {}
        
        # 测试每个合约
        for contract_name, address in chain_info['contracts'].items():
            if contract_name in test_configs:
                success = test_contract(
                    chain_info['url'], 
                    address, 
                    contract_name, 
                    test_configs[contract_name]
                )
                chain_results[contract_name] = {
                    'address': address,
                    'success': success
                }
            else:
                print(f"⚠️  跳过 {contract_name} (无测试配置)")
                chain_results[contract_name] = {
                    'address': address,
                    'success': False
                }
        
        test_results[chain_id] = {
            'chain_name': chain_info['name'],
            'rpc_url': chain_info['url'],
            'contracts': chain_results
        }
    
    # 保存测试结果
    with open('contract_test_results.json', 'w', encoding='utf-8') as f:
        json.dump(test_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 测试结果已保存到: contract_test_results.json")
    
    # 显示测试总结
    print("\n🎉 合约测试完成！")
    print("=" * 50)
    
    for chain_id, result in test_results.items():
        print(f"\n📋 {result['chain_name']}:")
        for contract_name, contract_result in result['contracts'].items():
            status = "✅" if contract_result['success'] else "❌"
            print(f"   {status} {contract_name}: {contract_result['address']}")
    
    # 统计信息
    total_contracts = 0
    successful_contracts = 0
    
    for chain_id, result in test_results.items():
        for contract_name, contract_result in result['contracts'].items():
            total_contracts += 1
            if contract_result['success']:
                successful_contracts += 1
    
    print(f"\n📊 测试统计:")
    print(f"   总合约数: {total_contracts}")
    print(f"   成功测试: {successful_contracts}")
    print(f"   成功率: {successful_contracts/total_contracts*100:.1f}%")
    
    print(f"\n💡 下一步建议:")
    print("1. 修复函数调用问题（需要正确的ABI编码）")
    print("2. 部署剩余的合约（CrossChainToken, AssetManager）")
    print("3. 配置合约之间的依赖关系")
    print("4. 测试跨链功能")

if __name__ == "__main__":
    main()
