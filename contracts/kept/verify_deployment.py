# -*- coding: utf-8 -*-
"""
合约部署验证脚本
"""
import json
import requests
from web3 import Web3

def verify_contract_deployment():
    """验证合约部署"""
    print("🔍 验证合约部署状态")
    print("=" * 50)
    
    # 从部署记录读取合约地址
    try:
        with open('build/deployment.json', 'r') as f:
            deployment_data = json.load(f)
        contract_address = deployment_data['DIDVerifier']['address']
        tx_hash = deployment_data['DIDVerifier']['tx_hash']
        print(f"📋 从部署记录读取: {contract_address}")
    except Exception as e:
        print(f"❌ 无法读取部署记录: {e}")
        return False
    
    def send_rpc_request(method, params):
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
                    print(f"❌ RPC错误: {result['error']}")
                    return None
                return result.get("result")
            else:
                print(f"❌ HTTP错误: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return None
    
    # 1. 验证合约代码存在
    print("1️⃣ 检查合约代码...")
    code = send_rpc_request("eth_getCode", [contract_address, "latest"])
    if code and code != "0x":
        print(f"✅ 合约代码存在，长度: {len(code)} 字符")
    else:
        print("❌ 合约代码不存在")
        return False
    
    # 2. 验证交易存在
    print("\n2️⃣ 检查部署交易...")
    tx = send_rpc_request("eth_getTransactionByHash", [tx_hash])
    if tx:
        print(f"✅ 交易存在")
        print(f"   发送方: {tx['from']}")
        print(f"   接收方: {tx.get('to', 'None (合约部署)')}")
        print(f"   Value: {int(tx['value'], 16)} wei ({int(tx['value'], 16) / 1e18:.18f} ETH)")
        print(f"   Gas限制: {int(tx['gas'], 16)}")
        print(f"   Gas价格: {int(tx['gasPrice'], 16)} wei ({int(tx['gasPrice'], 16) / 1e9:.2f} Gwei)")
        print(f"   数据长度: {len(tx.get('data', ''))} 字符")
    else:
        print("❌ 交易不存在")
        return False
    
    # 3. 验证交易收据
    print("\n3️⃣ 检查交易收据...")
    receipt = send_rpc_request("eth_getTransactionReceipt", [tx_hash])
    if receipt:
        status = int(receipt['status'], 16)
        if status == 1:
            print("✅ 交易成功执行")
            print(f"   合约地址: {receipt['contractAddress']}")
            print(f"   Gas使用: {int(receipt['gasUsed'], 16)}")
            print(f"   区块号: {int(receipt['blockNumber'], 16)}")
        else:
            print("❌ 交易执行失败")
            return False
    else:
        print("❌ 交易收据不存在")
        return False
    
    # 4. 验证合约函数调用
    print("\n4️⃣ 测试合约函数...")
    
    # 测试owner函数
    owner_call = send_rpc_request("eth_call", [
        {"to": contract_address, "data": "0x8da5cb5b"},
        "latest"
    ])
    if owner_call and owner_call != "0x":
        w3 = Web3()
        owner_address = "0x" + owner_call[-40:]  # 取最后40个字符作为地址
        print(f"✅ owner函数调用成功: {owner_address}")
    else:
        print("❌ owner函数调用失败")
        return False
    
    # 测试oracle函数
    oracle_call = send_rpc_request("eth_call", [
        {"to": contract_address, "data": "0x7dc0d1d0"},
        "latest"
    ])
    if oracle_call:
        oracle_address = "0x" + oracle_call[-40:]
        print(f"✅ oracle函数调用成功: {oracle_address}")
    else:
        print("❌ oracle函数调用失败")
        return False
    
    # 5. 验证ABI匹配
    print("\n5️⃣ 验证ABI文件...")
    try:
        with open('build/DIDVerifier.json', 'r') as f:
            abi_data = json.load(f)
        
        # 检查关键函数是否存在
        function_names = [item['name'] for item in abi_data['abi'] if item['type'] == 'function']
        expected_functions = ['owner', 'oracle', 'verifyIdentity', 'isVerified']
        
        missing_functions = [f for f in expected_functions if f not in function_names]
        if not missing_functions:
            print("✅ ABI文件完整，包含所有关键函数")
        else:
            print(f"❌ ABI文件缺少函数: {missing_functions}")
            return False
            
    except Exception as e:
        print(f"❌ 无法读取ABI文件: {e}")
        return False
    
    print("\n🎉 验证完成！合约确实已成功部署")
    print("=" * 50)
    print(f"📋 部署信息:")
    print(f"   合约地址: {contract_address}")
    print(f"   交易哈希: {tx_hash}")
    print(f"   部署者: {tx['from']}")
    print(f"   区块号: {int(receipt['blockNumber'], 16)}")
    print(f"   Gas使用: {int(receipt['gasUsed'], 16)}")
    
    return True

if __name__ == "__main__":
    verify_contract_deployment()
