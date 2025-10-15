#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Web3连接
"""

from web3 import Web3
import requests

def test_connection():
    """测试连接"""
    print("🔍 测试Web3连接...")
    
    # 测试链A
    print("\n📋 测试链A (localhost:8545):")
    try:
        # 直接HTTP请求
        response = requests.post('http://localhost:8545', 
                               json={"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1},
                               timeout=5)
        print(f"   HTTP状态: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   区块高度: {data.get('result', 'N/A')}")
        else:
            print(f"   HTTP错误: {response.text}")
    except Exception as e:
        print(f"   HTTP请求失败: {e}")
    
    try:
        # Web3连接
        w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
        print(f"   Web3连接: {w3.is_connected()}")
        if w3.is_connected():
            print(f"   最新区块: {w3.eth.block_number}")
            print(f"   账户数量: {len(w3.eth.accounts)}")
            if w3.eth.accounts:
                print(f"   第一个账户: {w3.eth.accounts[0]}")
                balance = w3.eth.get_balance(w3.eth.accounts[0])
                print(f"   账户余额: {w3.from_wei(balance, 'ether')} ETH")
    except Exception as e:
        print(f"   Web3连接失败: {e}")
    
    # 测试链B
    print("\n📋 测试链B (localhost:8555):")
    try:
        # 直接HTTP请求
        response = requests.post('http://localhost:8555', 
                               json={"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1},
                               timeout=5)
        print(f"   HTTP状态: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   区块高度: {data.get('result', 'N/A')}")
        else:
            print(f"   HTTP错误: {response.text}")
    except Exception as e:
        print(f"   HTTP请求失败: {e}")
    
    try:
        # Web3连接
        w3 = Web3(Web3.HTTPProvider('http://localhost:8555'))
        print(f"   Web3连接: {w3.is_connected()}")
        if w3.is_connected():
            print(f"   最新区块: {w3.eth.block_number}")
            print(f"   账户数量: {len(w3.eth.accounts)}")
            if w3.eth.accounts:
                print(f"   第一个账户: {w3.eth.accounts[0]}")
                balance = w3.eth.get_balance(w3.eth.accounts[0])
                print(f"   账户余额: {w3.from_wei(balance, 'ether')} ETH")
    except Exception as e:
        print(f"   Web3连接失败: {e}")

if __name__ == "__main__":
    test_connection()
