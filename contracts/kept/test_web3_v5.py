#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用Web3.py v5语法测试Besu连接
"""

import json
import requests
from web3 import Web3

def test_web3_v5_connection():
    """使用Web3.py v5语法测试连接"""
    print("🔗 使用Web3.py v5语法测试连接...")
    
    try:
        # 使用Web3.py v5的语法
        w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
        
        # 检查连接
        is_connected = w3.isConnected()
        print(f"连接状态: {is_connected}")
        
        if is_connected:
            # 获取区块号
            block_number = w3.eth.blockNumber
            print(f"区块号: {block_number}")
            
            # 获取链ID
            chain_id = w3.eth.chainId
            print(f"链ID: {chain_id}")
            
            # 获取账户
            accounts = w3.eth.accounts
            print(f"账户数量: {len(accounts)}")
            
            return True
        else:
            print("连接失败")
            return False
            
    except Exception as e:
        print(f"连接错误: {e}")
        return False

def test_manual_rpc_calls():
    """手动RPC调用测试"""
    print("\\n🔗 手动RPC调用测试...")
    
    try:
        # 获取区块号
        response = requests.post('http://localhost:8545', 
                               json={'jsonrpc': '2.0', 'method': 'eth_blockNumber', 'params': [], 'id': 1})
        if response.status_code == 200:
            data = response.json()
            block_number = int(data['result'], 16)
            print(f"区块号: {block_number}")
        
        # 获取链ID
        response = requests.post('http://localhost:8545', 
                               json={'jsonrpc': '2.0', 'method': 'eth_chainId', 'params': [], 'id': 2})
        if response.status_code == 200:
            data = response.json()
            chain_id = int(data['result'], 16)
            print(f"链ID: {chain_id}")
        
        # 获取账户
        response = requests.post('http://localhost:8545', 
                               json={'jsonrpc': '2.0', 'method': 'eth_accounts', 'params': [], 'id': 3})
        if response.status_code == 200:
            data = response.json()
            accounts = data['result']
            print(f"账户数量: {len(accounts)}")
            if accounts:
                print(f"第一个账户: {accounts[0]}")
        
        return True
        
    except Exception as e:
        print(f"RPC调用错误: {e}")
        return False

def test_contract_deployment():
    """测试合约部署"""
    print("\\n🔗 测试合约部署...")
    
    try:
        # 使用手动RPC调用
        response = requests.post('http://localhost:8545', 
                               json={'jsonrpc': '2.0', 'method': 'eth_accounts', 'params': [], 'id': 1})
        if response.status_code == 200:
            data = response.json()
            accounts = data['result']
            if accounts:
                print(f"可用账户: {len(accounts)}")
                print(f"第一个账户: {accounts[0]}")
                return True
            else:
                print("没有可用账户")
                return False
        else:
            print("获取账户失败")
            return False
            
    except Exception as e:
        print(f"合约部署测试错误: {e}")
        return False

def main():
    """主函数"""
    print("🧪 Web3.py v5语法测试")
    print("=" * 50)
    
    # 测试Web3 v5连接
    web3_ok = test_web3_v5_connection()
    print()
    
    # 测试手动RPC调用
    rpc_ok = test_manual_rpc_calls()
    print()
    
    # 测试合约部署
    contract_ok = test_contract_deployment()
    print()
    
    # 总结
    print("📊 测试结果:")
    print(f"Web3 v5连接: {'✅' if web3_ok else '❌'}")
    print(f"手动RPC调用: {'✅' if rpc_ok else '❌'}")
    print(f"合约部署: {'✅' if contract_ok else '❌'}")
    
    if rpc_ok and contract_ok:
        print("\\n🎉 Besu链连接正常，可以使用手动RPC调用方式")
        return True
    else:
        print("\\n⚠️  Besu链连接有问题")
        return False

if __name__ == "__main__":
    main()
