#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试部署简单合约
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

def main():
    """主函数"""
    print("🧪 测试部署简单合约")
    print("=" * 50)
    
    # 预定义账户
    account = "0x81be24626338695584b5beaebf51e09879a0ecc6"
    
    # 测试链A
    url = "http://localhost:8545"
    print(f"\n🔗 测试链A ({url})...")
    
    # 检查连接
    response = call_rpc(url, "eth_blockNumber")
    if not response or 'result' not in response:
        print("❌ 无法连接到链A")
        return
    
    block_number = int(response['result'], 16)
    print(f"✅ 连接成功，最新区块: {block_number}")
    
    # 检查账户余额
    response = call_rpc(url, "eth_getBalance", [account, "latest"])
    if response and 'result' in response:
        balance = int(response['result'], 16)
        balance_eth = balance / 10**18
        print(f"账户余额: {balance_eth} ETH")
    else:
        print("❌ 无法获取账户余额")
        return
    
    # 获取nonce
    response = call_rpc(url, "eth_getTransactionCount", [account, "latest"])
    if response and 'result' in response:
        nonce = int(response['result'], 16)
        print(f"Nonce: {nonce}")
    else:
        print("❌ 无法获取nonce")
        return
    
    # 加载合约
    with open('SimpleTest.json', 'r') as f:
        contract_data = json.load(f)
    
    bytecode = contract_data['bytecode']
    print(f"合约字节码长度: {len(bytecode)}")
    
    # 构建交易
    transaction = {
        "from": account,
        "data": bytecode,
        "gas": "0x2DC6C0",  # 3000000
        "gasPrice": "0x3B9ACA00",  # 1 gwei
        "nonce": hex(nonce)
    }
    
    print(f"交易详情: {json.dumps(transaction, indent=2)}")
    
    # 发送交易
    print("发送交易...")
    response = call_rpc(url, "eth_sendTransaction", [transaction])
    print(f"发送交易响应: {json.dumps(response, indent=2)}")
    
    if response and 'result' in response:
        tx_hash = response['result']
        print(f"✅ 交易发送成功: {tx_hash}")
        
        # 等待确认
        print("等待确认...")
        for i in range(30):
            time.sleep(1)
            receipt = call_rpc(url, "eth_getTransactionReceipt", [tx_hash])
            if receipt and 'result' in receipt and receipt['result']:
                result = receipt['result']
                if result.get('status') == '0x1':
                    contract_address = result.get('contractAddress')
                    print(f"✅ 合约部署成功: {contract_address}")
                    
                    # 测试合约调用
                    print("\n🧪 测试合约调用...")
                    
                    # 调用getInfo函数
                    call_data = "0x" + "getInfo()"  # 简化的调用数据
                    call_response = call_rpc(url, "eth_call", [{
                        "to": contract_address,
                        "data": call_data
                    }, "latest"])
                    print(f"getInfo调用结果: {call_response}")
                    
                    break
                else:
                    print(f"❌ 交易失败，状态: {result.get('status')}")
                    break
            print(f"等待中... ({i+1}/30)")
        else:
            print("❌ 交易确认超时")
    else:
        print("❌ 交易发送失败")
        if response and 'error' in response:
            print(f"错误: {response['error']}")

if __name__ == "__main__":
    main()
