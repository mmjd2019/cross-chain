#!/usr/bin/env python3
"""
详细调试transferFrom函数
逐步检查transferFrom函数的每个要求
"""

import json
from web3_fixed_connection import FixedWeb3
from eth_account import Account

def debug_transfer_from_detailed():
    """详细调试transferFrom函数"""
    print("🔍 详细调试transferFrom函数...")
    
    # 使用测试账户
    test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
    
    # 链A配置
    w3 = FixedWeb3('http://localhost:8545', 'Besu Chain A')
    token_address = '0x14D83c34ba0E1caC363039699d495e733B8A1182'
    bridge_address = '0xc7253857256391E518c4aF60aDa5Eb5972Dd6Dbc'
    verifier_address = '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
    
    # 加载合约ABI
    with open('CrossChainToken.json', 'r') as f:
        token_abi = json.load(f)['abi']
    
    with open('CrossChainDIDVerifier.json', 'r') as f:
        verifier_abi = json.load(f)['abi']
    
    token_contract = w3.w3.eth.contract(
        address=w3.w3.to_checksum_address(token_address),
        abi=token_abi
    )
    
    verifier_contract = w3.w3.eth.contract(
        address=w3.w3.to_checksum_address(verifier_address),
        abi=verifier_abi
    )
    
    print(f"🔍 代币合约地址: {token_address}")
    print(f"🔍 桥接合约地址: {bridge_address}")
    print(f"🔍 验证器合约地址: {verifier_address}")
    print(f"🔍 测试账户地址: {test_account.address}")
    
    # 检查transferFrom函数的所有要求
    print("\n🔍 检查transferFrom函数的所有要求...")
    
    # 1. 检查from地址验证
    print("   1. 检查from地址验证...")
    try:
        is_from_verified = verifier_contract.functions.isUserVerified(test_account.address).call()
        print(f"      from地址验证状态: {is_from_verified}")
    except Exception as e:
        print(f"      ❌ 检查from地址验证失败: {e}")
    
    # 2. 检查to地址验证
    print("   2. 检查to地址验证...")
    try:
        is_to_verified = verifier_contract.functions.isUserVerified(bridge_address).call()
        print(f"      to地址验证状态: {is_to_verified}")
    except Exception as e:
        print(f"      ❌ 检查to地址验证失败: {e}")
    
    # 3. 检查msg.sender验证
    print("   3. 检查msg.sender验证...")
    try:
        is_sender_verified = verifier_contract.functions.isUserVerified(test_account.address).call()
        print(f"      msg.sender验证状态: {is_sender_verified}")
    except Exception as e:
        print(f"      ❌ 检查msg.sender验证失败: {e}")
    
    # 4. 检查授权额度
    print("   4. 检查授权额度...")
    try:
        allowance = token_contract.functions.allowance(test_account.address, bridge_address).call()
        allowance_tokens = w3.w3.from_wei(allowance, 'ether')
        print(f"      授权额度: {allowance_tokens} CCT")
        
        amount_wei = w3.w3.to_wei(50, 'ether')
        print(f"      转账金额: {w3.w3.from_wei(amount_wei, 'ether')} CCT")
        print(f"      授权是否足够: {allowance >= amount_wei}")
    except Exception as e:
        print(f"      ❌ 检查授权额度失败: {e}")
    
    # 5. 检查余额
    print("   5. 检查余额...")
    try:
        balance = token_contract.functions.balanceOf(test_account.address).call()
        balance_tokens = w3.w3.from_wei(balance, 'ether')
        print(f"      余额: {balance_tokens} CCT")
        print(f"      余额是否足够: {balance >= amount_wei}")
    except Exception as e:
        print(f"      ❌ 检查余额失败: {e}")
    
    # 6. 检查代币合约的验证器地址
    print("   6. 检查代币合约的验证器地址...")
    try:
        token_verifier = token_contract.functions.verifier().call()
        print(f"      代币合约验证器地址: {token_verifier}")
        print(f"      验证器地址是否匹配: {token_verifier.lower() == verifier_address.lower()}")
    except Exception as e:
        print(f"      ❌ 检查代币合约验证器地址失败: {e}")
    
    # 7. 尝试直接调用transferFrom函数
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
        else:
            print("   ❌ transferFrom交易失败")
            
    except Exception as e:
        print(f"   ❌ transferFrom交易错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_transfer_from_detailed()