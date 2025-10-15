#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Besu链连接
"""

import json
import subprocess
import time
from web3 import Web3

def test_rpc_with_curl(url, chain_name):
    """使用curl测试RPC连接"""
    print(f"🔗 测试 {chain_name} RPC连接...")
    
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_blockNumber",
        "params": [],
        "id": 1
    }
    
    try:
        result = subprocess.run([
            'curl', '-s', '-X', 'POST',
            '-H', 'Content-Type: application/json',
            '-d', json.dumps(payload),
            url
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            response = json.loads(result.stdout)
            if 'result' in response:
                block_number = int(response['result'], 16)
                print(f"✅ {chain_name} RPC连接成功")
                print(f"   - 最新区块: {block_number}")
                return True
            else:
                print(f"❌ {chain_name} RPC响应异常: {response}")
                return False
        else:
            print(f"❌ {chain_name} RPC连接失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ {chain_name} RPC连接错误: {e}")
        return False

def test_web3_connection(url, chain_name):
    """使用Web3测试连接"""
    print(f"🔗 测试 {chain_name} Web3连接...")
    
    try:
        w3 = Web3(Web3.HTTPProvider(url))
        
        if w3.is_connected():
            block_number = w3.eth.block_number
            chain_id = w3.eth.chain_id
            print(f"✅ {chain_name} Web3连接成功")
            print(f"   - 最新区块: {block_number}")
            print(f"   - 链ID: {chain_id}")
            return True
        else:
            print(f"❌ {chain_name} Web3连接失败")
            return False
            
    except Exception as e:
        print(f"❌ {chain_name} Web3连接错误: {e}")
        return False

def test_contract_interaction(url, chain_name):
    """测试合约交互"""
    print(f"🔗 测试 {chain_name} 合约交互...")
    
    try:
        w3 = Web3(Web3.HTTPProvider(url))
        
        if not w3.is_connected():
            print(f"❌ {chain_name} Web3未连接")
            return False
        
        # 测试获取账户
        accounts = w3.eth.accounts
        print(f"✅ {chain_name} 合约交互成功")
        print(f"   - 账户数量: {len(accounts)}")
        if accounts:
            print(f"   - 第一个账户: {accounts[0]}")
        
        return True
        
    except Exception as e:
        print(f"❌ {chain_name} 合约交互错误: {e}")
        return False

def main():
    """主函数"""
    print("🧪 Besu链连接测试")
    print("=" * 60)
    
    # 测试链A
    print("测试链A (端口8545)...")
    print("-" * 30)
    
    curl_a = test_rpc_with_curl('http://localhost:8545', '链A')
    print()
    
    web3_a = test_web3_connection('http://localhost:8545', '链A')
    print()
    
    contract_a = test_contract_interaction('http://localhost:8545', '链A')
    print()
    
    # 测试链B
    print("测试链B (端口8555)...")
    print("-" * 30)
    
    curl_b = test_rpc_with_curl('http://localhost:8555', '链B')
    print()
    
    web3_b = test_web3_connection('http://localhost:8555', '链B')
    print()
    
    contract_b = test_contract_interaction('http://localhost:8555', '链B')
    print()
    
    # 总结
    print("📊 测试结果总结:")
    print("=" * 60)
    print(f"链A - curl: {'✅' if curl_a else '❌'}, Web3: {'✅' if web3_a else '❌'}, 合约: {'✅' if contract_a else '❌'}")
    print(f"链B - curl: {'✅' if curl_b else '❌'}, Web3: {'✅' if web3_b else '❌'}, 合约: {'✅' if contract_b else '❌'}")
    
    if curl_a and web3_a and contract_a and curl_b and web3_b and contract_b:
        print("\n🎉 所有测试通过！Besu链连接正常")
        return True
    else:
        print("\n⚠️  部分测试失败，请检查Besu链配置")
        return False

if __name__ == "__main__":
    main()
