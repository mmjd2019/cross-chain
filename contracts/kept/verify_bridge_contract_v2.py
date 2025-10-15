#!/usr/bin/env python3
"""
验证桥接合约 V2
为新的桥接合约地址添加DID验证
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

def verify_bridge_contract_v2():
    """验证桥接合约 V2"""
    print("🔐 验证桥接合约 V2...")
    
    # 使用测试账户（已授权的Oracle）
    test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
    
    # 新的桥接合约地址
    bridge_addresses = {
        'chain_a': '0xc7253857256391E518c4aF60aDa5Eb5972Dd6Dbc',
        'chain_b': '0x27e5Ee255a177D1902D7FF48D66f950ed9408867'
    }
    
    # 链配置
    chains = {
        'chain_a': {
            'name': 'Besu Chain A',
            'rpc_url': 'http://localhost:8545',
            'chain_id': 2023,
            'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf',
            'bridge_address': bridge_addresses['chain_a']
        },
        'chain_b': {
            'name': 'Besu Chain B', 
            'rpc_url': 'http://localhost:8555',
            'chain_id': 2024,
            'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf',
            'bridge_address': bridge_addresses['chain_b']
        }
    }
    
    # 加载验证器合约ABI
    with open('CrossChainDIDVerifier.json', 'r') as f:
        verifier_abi = json.load(f)['abi']
    
    results = {}
    
    for chain_id, config in chains.items():
        print(f"\n🔗 验证 {config['name']} 的桥接合约...")
        
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
            
            # 检查当前验证状态
            print("   检查当前验证状态...")
            is_verified = verifier_contract.functions.isVerified(config['bridge_address']).call()
            print(f"   桥接合约验证状态: {is_verified}")
            
            if is_verified:
                print(f"   ✅ 桥接合约已经验证")
                results[chain_id] = {'success': True, 'already_verified': True}
                continue
            
            # 验证桥接合约
            print("   验证桥接合约...")
            bridge_did = f"did:bridge:{config['bridge_address']}"
            
            nonce = w3.w3.eth.get_transaction_count(test_account.address)
            gas_price = w3.w3.eth.gas_price
            
            # 构建交易
            transaction = verifier_contract.functions.verifyIdentity(
                w3.w3.to_checksum_address(config['bridge_address']),
                bridge_did
            ).build_transaction({
                'from': test_account.address,
                'gas': 200000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': config['chain_id']
            })
            
            # 签名并发送交易
            signed_txn = w3.w3.eth.account.sign_transaction(transaction, test_account.key)
            tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            print(f"   ✅ 桥接合约验证交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            print("   ⏳ 等待交易确认...")
            receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                print(f"   ✅ 桥接合约验证成功!")
                print(f"   交易哈希: {tx_hash.hex()}")
                print(f"   区块号: {receipt.blockNumber}")
                
                # 验证验证状态
                print("   验证后状态检查...")
                is_verified_after = verifier_contract.functions.isVerified(config['bridge_address']).call()
                if is_verified_after:
                    print(f"   ✅ 桥接合约验证成功")
                    results[chain_id] = {
                        'success': True,
                        'already_verified': False,
                        'tx_hash': tx_hash.hex(),
                        'block_number': receipt.blockNumber
                    }
                else:
                    print(f"   ❌ 桥接合约验证失败")
                    results[chain_id] = {'success': False, 'error': 'Verification failed'}
            else:
                print(f"   ❌ 桥接合约验证失败")
                results[chain_id] = {'success': False, 'error': 'Transaction failed'}
                
        except Exception as e:
            print(f"   ❌ 验证桥接合约失败: {e}")
            results[chain_id] = {'success': False, 'error': str(e)}
    
    # 保存结果
    with open('bridge_contract_verification_v2_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 验证结果已保存到 bridge_contract_verification_v2_results.json")
    
    success_count = sum(1 for result in results.values() if result.get('success', False))
    print(f"✅ 成功验证 {success_count} 个桥接合约")
    
    return results

if __name__ == "__main__":
    verify_bridge_contract_v2()

