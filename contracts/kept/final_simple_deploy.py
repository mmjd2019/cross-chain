# -*- coding: utf-8 -*-
"""
最终简化部署脚本
"""
import json
import requests
import time
from web3 import Web3

def send_rpc_request(method, params):
    """发送JSON-RPC请求"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    
    try:
        response = requests.post("http://localhost:8545", json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if "error" in result:
                print(f"RPC错误: {result['error']}")
                return None
            return result.get("result")
        else:
            print(f"HTTP错误: {response.status_code}")
            return None
    except Exception as e:
        print(f"请求失败: {e}")
        return None

def deploy_contracts():
    """部署合约"""
    print("🚀 开始部署智能合约")
    print("=" * 50)
    
    # 测试网络连接
    print("🔍 测试网络连接...")
    block_number = send_rpc_request("eth_blockNumber", [])
    if block_number:
        print(f"✅ 网络连接成功，当前区块: {int(block_number, 16)}")
    else:
        print("❌ 网络连接失败")
        return False
    
    # 使用提供的私钥
    private_key = "0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a"
    
    try:
        # 创建账户
        w3 = Web3()
        account = w3.eth.account.from_key(private_key)
        print(f"✅ 账户地址: {account.address}")
        
        # 检查余额
        balance_hex = send_rpc_request("eth_getBalance", [account.address, "latest"])
        if balance_hex:
            balance = int(balance_hex, 16)
            balance_eth = w3.from_wei(balance, 'ether')
            print(f"💰 账户余额: {balance_eth} ETH")
        else:
            print("⚠️  无法获取账户余额")
        
    except Exception as e:
        print(f"❌ 私钥无效: {e}")
        return False
    
    # 加载合约
    try:
        # 加载DIDVerifier
        with open('build/DIDVerifier.json', 'r') as f:
            verifier_data = json.load(f)
        
        print("✅ 合约文件加载成功")
        
    except Exception as e:
        print(f"❌ 加载合约文件失败: {e}")
        return False
    
    # 部署DIDVerifier
    try:
        print("\n📝 部署DIDVerifier合约...")
        
        # 获取nonce
        nonce_hex = send_rpc_request("eth_getTransactionCount", [account.address, "latest"])
        if not nonce_hex:
            print("❌ 无法获取nonce")
            return False
        
        nonce = int(nonce_hex, 16)
        print(f"📊 Nonce: {nonce}")
        
        # 构建部署交易 - 使用更简单的格式
        deploy_tx = {
            'nonce': nonce,
            'gas': 1100001,
            'gasPrice': 1000000000,  # 1 gwei
            'chainId': 2023,
            'data': '0x' + verifier_data['bin'],
            'value': 0  # 部署合约不需要发送ETH
        }
        
        # 签名交易
        signed_tx = w3.eth.account.sign_transaction(deploy_tx, private_key)
        raw_tx = signed_tx.rawTransaction.hex()
        
        print(f"📋 原始交易: {raw_tx[:100]}...")
        
        # 发送交易
        tx_hash = send_rpc_request("eth_sendRawTransaction", [raw_tx])
        if not tx_hash:
            print("❌ 发送交易失败")
            return False
        
        print(f"⏳ 交易已发送: {tx_hash}")
        print("⏳ 等待确认...")
        
        # 等待确认
        for i in range(30):  # 最多等待30秒
            time.sleep(1)
            receipt = send_rpc_request("eth_getTransactionReceipt", [tx_hash])
            if receipt:
                if receipt.get('status') == '0x1':
                    verifier_address = receipt['contractAddress']
                    print(f"✅ DIDVerifier部署成功: {verifier_address}")
                    break
                else:
                    print("❌ DIDVerifier部署失败")
                    return False
            print(f"⏳ 等待确认... ({i+1}/30)")
        else:
            print("❌ 交易确认超时")
            return False
            
    except Exception as e:
        print(f"❌ 部署DIDVerifier失败: {e}")
        return False
    
    # 保存部署结果
    deployment_result = {
        "DIDVerifier": {
            "address": verifier_address,
            "tx_hash": tx_hash
        }
    }
    
    with open('build/deployment.json', 'w') as f:
        json.dump(deployment_result, f, indent=2)
    
    print("\n🎉 部署完成！")
    print("=" * 50)
    print(f"DIDVerifier地址: {verifier_address}")
    print(f"交易哈希: {tx_hash}")
    print("\n部署结果已保存到: build/deployment.json")
    
    return True

if __name__ == "__main__":
    try:
        success = deploy_contracts()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 部署过程中出错: {e}")
        exit(1)

