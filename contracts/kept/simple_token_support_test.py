#!/usr/bin/env python3
"""
简化的代币支持测试
测试添加代币支持的基本功能
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

def test_add_token_support():
    """测试添加代币支持"""
    print("🧪 测试添加代币支持...")
    
    # 使用合约所有者账户
    owner_account = Account.from_key('0x1111111111111111111111111111111111111111111111111111111111111111')
    
    # 链A配置
    w3 = FixedWeb3('http://localhost:8545', 'Besu Chain A')
    bridge_address = '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af'
    token_address = '0x14D83c34ba0E1caC363039699d495e733B8A1182'
    
    # 加载桥接合约ABI
    with open('CrossChainBridge.json', 'r') as f:
        bridge_abi = json.load(f)['abi']
    
    bridge_contract = w3.w3.eth.contract(
        address=w3.w3.to_checksum_address(bridge_address),
        abi=bridge_abi
    )
    
    print(f"🔍 桥接合约地址: {bridge_address}")
    print(f"🔍 代币地址: {token_address}")
    print(f"🔍 所有者地址: {owner_account.address}")
    
    # 检查当前支持状态
    try:
        is_supported = bridge_contract.functions.isTokenSupported(
            w3.w3.to_checksum_address(token_address)
        ).call()
        print(f"🔍 当前支持状态: {is_supported}")
    except Exception as e:
        print(f"❌ 检查支持状态失败: {e}")
    
    # 尝试添加代币支持
    try:
        nonce = w3.w3.eth.get_transaction_count(owner_account.address)
        gas_price = w3.w3.eth.gas_price
        
        print(f"🔍 当前nonce: {nonce}")
        print(f"🔍 Gas价格: {gas_price}")
        
        # 构建交易
        transaction = bridge_contract.functions.addSupportedToken(
            w3.w3.to_checksum_address(token_address),
            "CrossChain Token",
            "CCT",
            18
        ).build_transaction({
            'from': owner_account.address,
            'gas': 200000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': 2023
        })
        
        print(f"🔍 交易详情: {transaction}")
        
        # 签名并发送交易
        signed_txn = w3.w3.eth.account.sign_transaction(transaction, owner_account.key)
        tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        print(f"✅ 交易已发送: {tx_hash.hex()}")
        
        # 等待交易确认
        print("⏳ 等待交易确认...")
        receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"🔍 交易收据: {receipt}")
        print(f"🔍 交易状态: {receipt.status}")
        print(f"🔍 Gas使用: {receipt.gasUsed}")
        
        if receipt.status == 1:
            print("✅ 代币支持添加成功!")
            
            # 再次检查支持状态
            is_supported_after = bridge_contract.functions.isTokenSupported(
                w3.w3.to_checksum_address(token_address)
            ).call()
            print(f"🔍 添加后支持状态: {is_supported_after}")
            
        else:
            print("❌ 代币支持添加失败")
            
    except Exception as e:
        print(f"❌ 添加代币支持错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_add_token_support()

