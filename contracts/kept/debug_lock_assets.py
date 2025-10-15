#!/usr/bin/env python3
"""
调试lockAssets问题
检查lockAssets函数失败的原因
"""

import json
from web3_fixed_connection import FixedWeb3
from eth_account import Account

def debug_lock_assets():
    """调试lockAssets问题"""
    print("🔍 调试lockAssets问题...")
    
    # 使用测试账户
    test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
    
    # 链A配置
    w3 = FixedWeb3('http://localhost:8545', 'Besu Chain A')
    bridge_address = '0xc7253857256391E518c4aF60aDa5Eb5972Dd6Dbc'
    token_address = '0x14D83c34ba0E1caC363039699d495e733B8A1182'
    verifier_address = '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
    
    # 加载合约ABI
    with open('CrossChainBridge.json', 'r') as f:
        bridge_abi = json.load(f)['abi']
    
    with open('CrossChainDIDVerifier.json', 'r') as f:
        verifier_abi = json.load(f)['abi']
    
    bridge_contract = w3.w3.eth.contract(
        address=w3.w3.to_checksum_address(bridge_address),
        abi=bridge_abi
    )
    
    verifier_contract = w3.w3.eth.contract(
        address=w3.w3.to_checksum_address(verifier_address),
        abi=verifier_abi
    )
    
    print(f"🔍 桥接合约地址: {bridge_address}")
    print(f"🔍 代币合约地址: {token_address}")
    print(f"🔍 验证器合约地址: {verifier_address}")
    print(f"🔍 测试账户地址: {test_account.address}")
    
    # 检查用户验证状态
    print("\n🔍 检查用户验证状态...")
    try:
        is_verified = verifier_contract.functions.isVerified(test_account.address).call()
        print(f"   用户验证状态: {is_verified}")
    except Exception as e:
        print(f"   ❌ 检查用户验证状态失败: {e}")
    
    # 检查用户DID
    print("\n🔍 检查用户DID...")
    try:
        user_did = verifier_contract.functions.getUserDID(test_account.address).call()
        print(f"   用户DID: {user_did}")
        print(f"   DID长度: {len(user_did)}")
    except Exception as e:
        print(f"   ❌ 检查用户DID失败: {e}")
    
    # 检查链支持
    print("\n🔍 检查链支持...")
    try:
        is_chain_a_supported = verifier_contract.functions.isChainSupported('chain_a_chain').call()
        is_chain_b_supported = verifier_contract.functions.isChainSupported('chain_b_chain').call()
        print(f"   链A支持状态: {is_chain_a_supported}")
        print(f"   链B支持状态: {is_chain_b_supported}")
    except Exception as e:
        print(f"   ❌ 检查链支持失败: {e}")
    
    # 检查代币支持
    print("\n🔍 检查代币支持...")
    try:
        is_token_supported = bridge_contract.functions.isTokenSupported(token_address).call()
        print(f"   代币支持状态: {is_token_supported}")
    except Exception as e:
        print(f"   ❌ 检查代币支持失败: {e}")
    
    # 检查代币余额
    print("\n🔍 检查代币余额...")
    try:
        with open('CrossChainToken.json', 'r') as f:
            token_abi = json.load(f)['abi']
        
        token_contract = w3.w3.eth.contract(
            address=w3.w3.to_checksum_address(token_address),
            abi=token_abi
        )
        
        balance = token_contract.functions.balanceOf(test_account.address).call()
        balance_tokens = w3.w3.from_wei(balance, 'ether')
        print(f"   代币余额: {balance_tokens} CCT")
    except Exception as e:
        print(f"   ❌ 检查代币余额失败: {e}")
    
    # 检查授权额度
    print("\n🔍 检查授权额度...")
    try:
        allowance = token_contract.functions.allowance(test_account.address, bridge_address).call()
        allowance_tokens = w3.w3.from_wei(allowance, 'ether')
        print(f"   授权额度: {allowance_tokens} CCT")
    except Exception as e:
        print(f"   ❌ 检查授权额度失败: {e}")
    
    # 检查桥接合约状态
    print("\n🔍 检查桥接合约状态...")
    try:
        owner = bridge_contract.functions.owner().call()
        verifier = bridge_contract.functions.verifier().call()
        chain_id = bridge_contract.functions.chainId().call()
        chain_type = bridge_contract.functions.chainType().call()
        
        print(f"   所有者: {owner}")
        print(f"   验证器: {verifier}")
        print(f"   链ID: {chain_id}")
        print(f"   链类型: {chain_type}")
    except Exception as e:
        print(f"   ❌ 检查桥接合约状态失败: {e}")
    
    # 尝试直接调用lockAssets函数
    print("\n🔍 尝试直接调用lockAssets函数...")
    try:
        nonce = w3.w3.eth.get_transaction_count(test_account.address)
        gas_price = w3.w3.eth.gas_price
        
        amount_wei = w3.w3.to_wei(50, 'ether')
        
        transaction = bridge_contract.functions.lockAssets(
            amount_wei,
            w3.w3.to_checksum_address(token_address),
            'chain_b_chain'
        ).build_transaction({
            'from': test_account.address,
            'gas': 200000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': 2023
        })
        
        print(f"   交易详情: {transaction}")
        
        # 签名并发送交易
        signed_txn = w3.w3.eth.account.sign_transaction(transaction, test_account.key)
        tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        print(f"   ✅ 锁定交易已发送: {tx_hash.hex()}")
        
        # 等待交易确认
        print("   ⏳ 等待交易确认...")
        receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"   🔍 交易收据: {receipt}")
        print(f"   🔍 交易状态: {receipt.status}")
        print(f"   🔍 Gas使用: {receipt.gasUsed}")
        
        if receipt.status == 1:
            print("   ✅ 锁定交易成功!")
        else:
            print("   ❌ 锁定交易失败")
            
    except Exception as e:
        print(f"   ❌ 锁定交易错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_lock_assets()

