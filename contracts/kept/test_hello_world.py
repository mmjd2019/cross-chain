# -*- coding: utf-8 -*-
"""
测试AssetManager合约中的"hello world"消息
"""
import json
import requests
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
        response = requests.post("http://192.168.1.3:8546", json=payload, timeout=10)
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

def test_hello_world_message():
    """测试hello world消息"""
    print("🌍 测试AssetManager合约中的'hello world'消息")
    print("=" * 60)
    
    # 加载部署数据
    try:
        with open('deployment.json', 'r') as f:
            deployment_data = json.load(f)
        
        asset_manager_address = deployment_data["AssetManager"]["address"]
        verifier_address = deployment_data["DIDVerifier"]["address"]
        
        print(f"✅ AssetManager地址: {asset_manager_address}")
        print(f"✅ DIDVerifier地址: {verifier_address}")
        
    except Exception as e:
        print(f"❌ 无法加载部署数据: {e}")
        return False
    
    # 测试1: 检查合约代码
    print("\n1️⃣ 检查合约代码...")
    code = send_rpc_request("eth_getCode", [asset_manager_address, "latest"])
    if code and code != "0x":
        print(f"✅ 合约代码存在，长度: {len(code)} 字符")
    else:
        print("❌ 合约代码不存在")
        return False
    
    # 测试2: 获取部署消息
    print("\n2️⃣ 获取部署消息...")
    # getDeploymentMessage()函数选择器
    message_call = send_rpc_request("eth_call", [
        {"to": asset_manager_address, "data": "0x76a20c66"},  # getDeploymentMessage()函数选择器
        "latest"
    ])
    
    if message_call and message_call != "0x":
        # 解码返回的字符串
        # 返回格式: 0x0000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000000b68656c6c6f20776f726c6400000000000000000000000000000000000000000000
        # 其中0x20表示字符串偏移，0x0b表示字符串长度(11)，后面是"hello world"的十六进制
        
        # 提取字符串长度
        length_hex = message_call[66:130]  # 跳过0x和偏移量，取长度部分
        length = int(length_hex, 16)
        
        # 提取字符串内容
        string_hex = message_call[130:130 + length * 2]
        message = bytes.fromhex(string_hex).decode('utf-8')
        
        print(f"✅ 部署消息: '{message}'")
        if message == "zqb":
            print("✅ 消息内容正确！")
        else:
            print(f"❌ 消息内容不正确，期望: 'zqb'，实际: '{message}'")
            return False
    else:
        print("❌ 无法获取部署消息")
        return False
    
    # 测试3: 检查部署事件
    print("\n3️⃣ 检查部署事件...")
    tx_hash = deployment_data["AssetManager"]["tx_hash"]
    receipt = send_rpc_request("eth_getTransactionReceipt", [tx_hash])
    
    if receipt and receipt.get('logs'):
        print(f"✅ 发现 {len(receipt['logs'])} 个事件")
        
        # 查找AssetManagerDeployed事件
        for i, log in enumerate(receipt['logs']):
            print(f"   事件 {i+1}: 地址={log['address']}, 数据长度={len(log['data'])}")
            
            # 检查是否是AssetManagerDeployed事件
            # 事件签名: AssetManagerDeployed(string,address)
            if len(log['data']) > 2:  # 有数据的事件
                print(f"   事件数据: {log['data'][:100]}...")
    else:
        print("⚠️  未找到事件日志")
    
    # 测试4: 检查verifier地址
    print("\n4️⃣ 检查verifier地址...")
    verifier_call = send_rpc_request("eth_call", [
        {"to": asset_manager_address, "data": "0x2b7ac3f3"},  # verifier()函数选择器
        "latest"
    ])
    
    if verifier_call and verifier_call != "0x":
        called_verifier = "0x" + verifier_call[-40:]
        print(f"✅ verifier地址: {called_verifier}")
        if called_verifier.lower() == verifier_address.lower():
            print("✅ verifier地址匹配")
        else:
            print("❌ verifier地址不匹配")
            return False
    else:
        print("❌ 无法获取verifier地址")
        return False
    
    print("\n🎉 'hello world'消息测试完成！")
    print("=" * 60)
    print("📋 测试结果:")
    print(f"   合约地址: {asset_manager_address}")
    print(f"   部署消息: 'zqb'")
    print(f"   Verifier地址: {verifier_address}")
    print(f"   消息状态: ✅ 成功上链")
    
    return True

if __name__ == "__main__":
    try:
        success = test_hello_world_message()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试过程中出错: {e}")
        exit(1)
