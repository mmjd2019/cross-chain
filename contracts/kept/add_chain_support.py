#!/usr/bin/env python3
"""
添加链支持
为验证器合约添加链支持
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

def add_chain_support():
    """添加链支持"""
    print("🔧 添加链支持...")
    
    # 使用合约所有者账户
    owner_account = Account.from_key('0x1111111111111111111111111111111111111111111111111111111111111111')
    
    # 链配置
    chains = {
        'chain_a': {
            'name': 'Besu Chain A',
            'rpc_url': 'http://localhost:8545',
            'chain_id': 2023,
            'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf',
            'chain_identifier': 'chain_a_chain'
        },
        'chain_b': {
            'name': 'Besu Chain B', 
            'rpc_url': 'http://localhost:8555',
            'chain_id': 2024,
            'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf',
            'chain_identifier': 'chain_b_chain'
        }
    }
    
    # 加载验证器合约ABI
    with open('CrossChainDIDVerifier.json', 'r') as f:
        verifier_abi = json.load(f)['abi']
    
    results = {}
    
    for chain_id, config in chains.items():
        print(f"\n🔗 在 {config['name']} 上添加链支持...")
        
        try:
            w3 = FixedWeb3(config['rpc_url'], config['name'])
            if not w3.is_connected():
                print(f"❌ {config['name']} 连接失败")
                continue
            
            # 创建验证器合约实例
            verifier_contract = w3.w3.eth.contract(
                address=w3.w3.to_checksum_address(config['verifier_address']),
                abi=verifier_abi
            )
            
            # 检查当前链支持状态
            print("   检查当前链支持状态...")
            is_chain_a_supported = verifier_contract.functions.isChainSupported('chain_a_chain').call()
            is_chain_b_supported = verifier_contract.functions.isChainSupported('chain_b_chain').call()
            
            print(f"   链A支持状态: {is_chain_a_supported}")
            print(f"   链B支持状态: {is_chain_b_supported}")
            
            if is_chain_a_supported and is_chain_b_supported:
                print(f"   ✅ 所有链都已经支持")
                results[chain_id] = {'success': True, 'already_supported': True}
                continue
            
            # 添加链支持
            print("   添加链支持...")
            
            nonce = w3.w3.eth.get_transaction_count(owner_account.address)
            gas_price = w3.w3.eth.gas_price
            
            # 添加链A支持
            if not is_chain_a_supported:
                print("   添加链A支持...")
                transaction = verifier_contract.functions.addSupportedChain('chain_a_chain').build_transaction({
                    'from': owner_account.address,
                    'gas': 200000,
                    'gasPrice': gas_price,
                    'nonce': nonce,
                    'chainId': config['chain_id']
                })
                
                signed_txn = w3.w3.eth.account.sign_transaction(transaction, owner_account.key)
                tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                
                print(f"   ✅ 链A支持交易已发送: {tx_hash.hex()}")
                
                # 等待交易确认
                receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
                if receipt.status == 1:
                    print(f"   ✅ 链A支持添加成功!")
                else:
                    print(f"   ❌ 链A支持添加失败")
                
                nonce += 1
            
            # 添加链B支持
            if not is_chain_b_supported:
                print("   添加链B支持...")
                transaction = verifier_contract.functions.addSupportedChain('chain_b_chain').build_transaction({
                    'from': owner_account.address,
                    'gas': 200000,
                    'gasPrice': gas_price,
                    'nonce': nonce,
                    'chainId': config['chain_id']
                })
                
                signed_txn = w3.w3.eth.account.sign_transaction(transaction, owner_account.key)
                tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                
                print(f"   ✅ 链B支持交易已发送: {tx_hash.hex()}")
                
                # 等待交易确认
                receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
                if receipt.status == 1:
                    print(f"   ✅ 链B支持添加成功!")
                else:
                    print(f"   ❌ 链B支持添加失败")
            
            # 验证链支持
            print("   验证链支持...")
            is_chain_a_supported_after = verifier_contract.functions.isChainSupported('chain_a_chain').call()
            is_chain_b_supported_after = verifier_contract.functions.isChainSupported('chain_b_chain').call()
            
            print(f"   链A支持状态: {is_chain_a_supported_after}")
            print(f"   链B支持状态: {is_chain_b_supported_after}")
            
            if is_chain_a_supported_after and is_chain_b_supported_after:
                print(f"   ✅ 所有链支持添加成功")
                results[chain_id] = {'success': True, 'already_supported': False}
            else:
                print(f"   ❌ 链支持添加失败")
                results[chain_id] = {'success': False, 'error': 'Chain support verification failed'}
                
        except Exception as e:
            print(f"   ❌ 添加链支持失败: {e}")
            results[chain_id] = {'success': False, 'error': str(e)}
    
    # 保存结果
    with open('chain_support_addition_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 添加结果已保存到 chain_support_addition_results.json")
    
    success_count = sum(1 for result in results.values() if result.get('success', False))
    print(f"✅ 成功添加 {success_count} 个链的链支持")
    
    return results

if __name__ == "__main__":
    add_chain_support()

