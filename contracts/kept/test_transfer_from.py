#!/usr/bin/env python3
"""
测试transferFrom函数
直接测试代币合约的transferFrom函数
"""

import json
from web3_fixed_connection import FixedWeb3
from eth_account import Account

def test_transfer_from():
    """测试transferFrom函数"""
    print("🧪 测试transferFrom函数...")
    
    # 使用测试账户
    test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
    
    # 链A配置
    w3 = FixedWeb3('http://localhost:8545', 'Besu Chain A')
    token_address = '0x14D83c34ba0E1caC363039699d495e733B8A1182'
    bridge_address = '0xc7253857256391E518c4aF60aDa5Eb5972Dd6Dbc'
    
    # 加载代币合约ABI
    with open('CrossChainToken.json', 'r') as f:
        token_abi = json.load(f)['abi']
    
    token_contract = w3.w3.eth.contract(
        address=w3.w3.to_checksum_address(token_address),
        abi=token_abi
    )
    
    print(f"🔍 代币合约地址: {token_address}")
    print(f"🔍 桥接合约地址: {bridge_address}")
    print(f"🔍 测试账户地址: {test_account.address}")
    
    # 检查余额和授权
    print("\n🔍 检查余额和授权...")
    try:
        balance = token_contract.functions.balanceOf(test_account.address).call()
        balance_tokens = w3.w3.from_wei(balance, 'ether')
        print(f"   代币余额: {balance_tokens} CCT")
        
        allowance = token_contract.functions.allowance(test_account.address, bridge_address).call()
        allowance_tokens = w3.w3.from_wei(allowance, 'ether')
        print(f"   授权额度: {allowance_tokens} CCT")
    except Exception as e:
        print(f"   ❌ 检查余额和授权失败: {e}")
        return
    
    # 尝试直接调用transferFrom函数
    print("\n🔍 尝试直接调用transferFrom函数...")
    try:
        nonce = w3.w3.eth.get_transaction_count(test_account.address)
        gas_price = w3.w3.eth.gas_price
        
        amount_wei = w3.w3.to_wei(50, 'ether')
        
        transaction = token_contract.functions.transferFrom(
            test_account.address,
            bridge_address,
            amount_wei
        ).build_transaction({
            'from': test_account.address,
            'gas': 100000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': 2023
        })
        
        print(f"   交易详情: {transaction}")
        
        # 签名并发送交易
        signed_txn = w3.w3.eth.account.sign_transaction(transaction, test_account.key)
        tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        print(f"   ✅ transferFrom交易已发送: {tx_hash.hex()}")
        
        # 等待交易确认
        print("   ⏳ 等待交易确认...")
        receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"   🔍 交易收据: {receipt}")
        print(f"   🔍 交易状态: {receipt.status}")
        print(f"   🔍 Gas使用: {receipt.gasUsed}")
        
        if receipt.status == 1:
            print("   ✅ transferFrom交易成功!")
            
            # 检查余额变化
            print("   🔍 检查余额变化...")
            balance_after = token_contract.functions.balanceOf(test_account.address).call()
            balance_after_tokens = w3.w3.from_wei(balance_after, 'ether')
            print(f"   转账后代币余额: {balance_after_tokens} CCT")
            
            bridge_balance = token_contract.functions.balanceOf(bridge_address).call()
            bridge_balance_tokens = w3.w3.from_wei(bridge_balance, 'ether')
            print(f"   桥接合约代币余额: {bridge_balance_tokens} CCT")
            
        else:
            print("   ❌ transferFrom交易失败")
            
    except Exception as e:
        print(f"   ❌ transferFrom交易错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_transfer_from()

