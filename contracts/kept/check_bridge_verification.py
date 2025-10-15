#!/usr/bin/env python3
"""
检查桥接合约验证状态
详细检查桥接合约的DID验证状态
"""

import json
from web3_fixed_connection import FixedWeb3
from eth_account import Account

def check_bridge_verification():
    """检查桥接合约验证状态"""
    print("🔍 检查桥接合约验证状态...")
    
    # 使用测试账户
    test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
    
    # 链A配置
    w3 = FixedWeb3('http://localhost:8545', 'Besu Chain A')
    bridge_address = '0xc7253857256391E518c4aF60aDa5Eb5972Dd6Dbc'
    verifier_address = '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
    
    # 加载验证器合约ABI
    with open('CrossChainDIDVerifier.json', 'r') as f:
        verifier_abi = json.load(f)['abi']
    
    verifier_contract = w3.w3.eth.contract(
        address=w3.w3.to_checksum_address(verifier_address),
        abi=verifier_abi
    )
    
    print(f"🔍 桥接合约地址: {bridge_address}")
    print(f"🔍 验证器合约地址: {verifier_address}")
    print(f"🔍 测试账户地址: {test_account.address}")
    
    # 检查用户验证状态
    print("\n🔍 检查用户验证状态...")
    try:
        is_verified = verifier_contract.functions.isVerified(test_account.address).call()
        print(f"   用户验证状态: {is_verified}")
    except Exception as e:
        print(f"   ❌ 检查用户验证状态失败: {e}")
    
    # 检查桥接合约验证状态
    print("\n🔍 检查桥接合约验证状态...")
    try:
        is_bridge_verified = verifier_contract.functions.isVerified(bridge_address).call()
        print(f"   桥接合约验证状态: {is_bridge_verified}")
    except Exception as e:
        print(f"   ❌ 检查桥接合约验证状态失败: {e}")
    
    # 检查用户DID
    print("\n🔍 检查用户DID...")
    try:
        user_did = verifier_contract.functions.getUserDID(test_account.address).call()
        print(f"   用户DID: {user_did}")
    except Exception as e:
        print(f"   ❌ 检查用户DID失败: {e}")
    
    # 检查桥接合约DID
    print("\n🔍 检查桥接合约DID...")
    try:
        bridge_did = verifier_contract.functions.getUserDID(bridge_address).call()
        print(f"   桥接合约DID: {bridge_did}")
    except Exception as e:
        print(f"   ❌ 检查桥接合约DID失败: {e}")
    
    # 检查所有验证的地址
    print("\n🔍 检查所有验证的地址...")
    try:
        # 这里我们需要知道如何获取所有验证的地址
        # 可能需要查看合约的事件日志
        print("   无法直接获取所有验证的地址")
    except Exception as e:
        print(f"   ❌ 检查所有验证的地址失败: {e}")
    
    # 尝试直接调用isUserVerified函数
    print("\n🔍 尝试直接调用isUserVerified函数...")
    try:
        # 检查用户
        is_user_verified = verifier_contract.functions.isUserVerified(test_account.address).call()
        print(f"   用户isUserVerified: {is_user_verified}")
        
        # 检查桥接合约
        is_bridge_user_verified = verifier_contract.functions.isUserVerified(bridge_address).call()
        print(f"   桥接合约isUserVerified: {is_bridge_user_verified}")
        
    except Exception as e:
        print(f"   ❌ 调用isUserVerified失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_bridge_verification()

