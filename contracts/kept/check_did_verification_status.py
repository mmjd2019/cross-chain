#!/usr/bin/env python3
"""
检查DID验证状态
检查Oracle服务是否将VC验证结果写入了DID验证器
"""

import json
from web3_fixed_connection import FixedWeb3
from eth_account import Account

def check_did_verification_status():
    """检查DID验证状态"""
    print("🔍 检查DID验证状态...")
    
    # 使用测试账户
    test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
    
    # 链A配置
    w3 = FixedWeb3('http://localhost:8545', 'Besu Chain A')
    verifier_address = '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
    bridge_address = '0xc7253857256391E518c4aF60aDa5Eb5972Dd6Dbc'
    
    # 加载验证器合约ABI
    with open('CrossChainDIDVerifier.json', 'r') as f:
        verifier_abi = json.load(f)['abi']
    
    verifier_contract = w3.w3.eth.contract(
        address=w3.w3.to_checksum_address(verifier_address),
        abi=verifier_abi
    )
    
    print(f"🔍 验证器合约地址: {verifier_address}")
    print(f"🔍 桥接合约地址: {bridge_address}")
    print(f"🔍 测试账户地址: {test_account.address}")
    
    # 检查用户验证状态
    print("\n🔍 检查用户验证状态...")
    try:
        is_verified = verifier_contract.functions.isVerified(test_account.address).call()
        print(f"   用户验证状态: {is_verified}")
        
        is_user_verified = verifier_contract.functions.isUserVerified(test_account.address).call()
        print(f"   用户isUserVerified: {is_user_verified}")
        
    except Exception as e:
        print(f"   ❌ 检查用户验证状态失败: {e}")
    
    # 检查桥接合约验证状态
    print("\n🔍 检查桥接合约验证状态...")
    try:
        is_bridge_verified = verifier_contract.functions.isVerified(bridge_address).call()
        print(f"   桥接合约验证状态: {is_bridge_verified}")
        
        is_bridge_user_verified = verifier_contract.functions.isUserVerified(bridge_address).call()
        print(f"   桥接合约isUserVerified: {is_bridge_user_verified}")
        
    except Exception as e:
        print(f"   ❌ 检查桥接合约验证状态失败: {e}")
    
    # 检查用户DID
    print("\n🔍 检查用户DID...")
    try:
        user_did = verifier_contract.functions.getUserDID(test_account.address).call()
        print(f"   用户DID: {user_did}")
        print(f"   DID长度: {len(user_did)}")
        
    except Exception as e:
        print(f"   ❌ 检查用户DID失败: {e}")
    
    # 检查桥接合约DID
    print("\n🔍 检查桥接合约DID...")
    try:
        bridge_did = verifier_contract.functions.getUserDID(bridge_address).call()
        print(f"   桥接合约DID: {bridge_did}")
        print(f"   DID长度: {len(bridge_did)}")
        
    except Exception as e:
        print(f"   ❌ 检查桥接合约DID失败: {e}")
    
    # 检查Oracle服务状态
    print("\n🔍 检查Oracle服务状态...")
    try:
        # 检查是否有Oracle服务在运行
        import requests
        oracle_url = "http://localhost:5000/status"
        response = requests.get(oracle_url, timeout=5)
        if response.status_code == 200:
            print("   ✅ Oracle服务正在运行")
            oracle_status = response.json()
            print(f"   Oracle状态: {oracle_status}")
        else:
            print("   ❌ Oracle服务未运行")
    except Exception as e:
        print(f"   ❌ 检查Oracle服务失败: {e}")
    
    # 检查链上事件日志
    print("\n🔍 检查链上事件日志...")
    try:
        # 获取最近的区块
        latest_block = w3.w3.eth.block_number
        print(f"   最新区块号: {latest_block}")
        
        # 检查最近的事件
        from_block = max(0, latest_block - 100)
        to_block = latest_block
        
        print(f"   检查区块范围: {from_block} - {to_block}")
        
        # 获取IdentityVerified事件
        identity_verified_filter = verifier_contract.events.IdentityVerified.create_filter(
            fromBlock=from_block,
            toBlock=to_block
        )
        
        events = identity_verified_filter.get_all_entries()
        print(f"   找到 {len(events)} 个IdentityVerified事件")
        
        for i, event in enumerate(events):
            print(f"   事件 {i+1}:")
            print(f"     区块号: {event.blockNumber}")
            print(f"     用户地址: {event.args.user}")
            print(f"     用户DID: {event.args.did}")
            print(f"     时间戳: {event.args.timestamp}")
            
    except Exception as e:
        print(f"   ❌ 检查链上事件日志失败: {e}")
    
    # 检查是否需要DID验证
    print("\n🔍 检查是否需要DID验证...")
    print("   分析: transferFrom函数要求from、to、msg.sender都必须通过DID验证")
    print("   问题: 如果from和to是同一个链上的账户，可能不需要DID验证")
    print("   建议: 考虑修改代币合约，允许同链转账不需要DID验证")

if __name__ == "__main__":
    check_did_verification_status()
