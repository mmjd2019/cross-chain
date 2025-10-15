#!/usr/bin/env python3
"""
修复桥接合约
重新部署桥接合约并正确初始化
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

def fix_bridge_contract():
    """修复桥接合约"""
    print("🔧 修复桥接合约...")
    
    # 使用合约所有者账户
    owner_account = Account.from_key('0x1111111111111111111111111111111111111111111111111111111111111111')
    
    # 链配置
    chains = {
        'chain_a': {
            'name': 'Besu Chain A',
            'rpc_url': 'http://localhost:8545',
            'chain_id': 2023,
            'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
        },
        'chain_b': {
            'name': 'Besu Chain B', 
            'rpc_url': 'http://localhost:8555',
            'chain_id': 2024,
            'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
        }
    }
    
    # 加载桥接合约ABI和字节码
    with open('CrossChainBridge.json', 'r') as f:
        bridge_data = json.load(f)
        bridge_abi = bridge_data['abi']
        bridge_bytecode = bridge_data['bytecode']
    
    results = {}
    
    for chain_id, config in chains.items():
        print(f"\n🔗 修复 {config['name']} 的桥接合约...")
        
        try:
            w3 = FixedWeb3(config['rpc_url'], config['name'])
            if not w3.is_connected():
                print(f"❌ {config['name']} 连接失败")
                continue
            
            # 部署新的桥接合约
            print("   部署新的桥接合约...")
            
            nonce = w3.w3.eth.get_transaction_count(owner_account.address)
            gas_price = w3.w3.eth.gas_price
            
            # 构建部署交易
            bridge_contract = w3.w3.eth.contract(abi=bridge_abi, bytecode=bridge_bytecode)
            
            constructor_tx = bridge_contract.constructor(
                w3.w3.to_checksum_address(config['verifier_address']),
                f"{chain_id}_chain",
                2  # 链类型：2表示支持锁定和解锁
            ).build_transaction({
                'from': owner_account.address,
                'gas': 3000000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': config['chain_id']
            })
            
            # 签名并发送交易
            signed_txn = w3.w3.eth.account.sign_transaction(constructor_tx, owner_account.key)
            tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            print(f"   ✅ 桥接合约部署交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            print("   ⏳ 等待交易确认...")
            receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                bridge_address = receipt.contractAddress
                print(f"   ✅ 桥接合约部署成功!")
                print(f"   📍 新桥接合约地址: {bridge_address}")
                print(f"   📊 区块号: {receipt.blockNumber}")
                print(f"   ⛽ Gas使用: {receipt.gasUsed}")
                
                # 验证新合约
                print("   🔍 验证新桥接合约...")
                new_bridge_contract = w3.w3.eth.contract(
                    address=w3.w3.to_checksum_address(bridge_address),
                    abi=bridge_abi
                )
                
                # 检查构造函数参数
                owner = new_bridge_contract.functions.owner().call()
                verifier = new_bridge_contract.functions.verifier().call()
                chain_id_from_contract = new_bridge_contract.functions.chainId().call()
                chain_type = new_bridge_contract.functions.chainType().call()
                
                print(f"   🔍 所有者: {owner}")
                print(f"   🔍 验证器: {verifier}")
                print(f"   🔍 链ID: {chain_id_from_contract}")
                print(f"   🔍 链类型: {chain_type}")
                
                if verifier != '0x0000000000000000000000000000000000000000':
                    print(f"   ✅ 桥接合约初始化成功!")
                    results[chain_id] = {
                        'success': True,
                        'old_address': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af',
                        'new_address': bridge_address,
                        'tx_hash': tx_hash.hex(),
                        'block_number': receipt.blockNumber,
                        'gas_used': receipt.gasUsed
                    }
                else:
                    print(f"   ❌ 桥接合约初始化失败")
                    results[chain_id] = {'success': False, 'error': 'Verifier address is zero'}
            else:
                print(f"   ❌ 桥接合约部署失败")
                results[chain_id] = {'success': False, 'error': 'Deployment transaction failed'}
                
        except Exception as e:
            print(f"   ❌ 修复桥接合约失败: {e}")
            results[chain_id] = {'success': False, 'error': str(e)}
    
    # 保存结果
    with open('bridge_contract_fix_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 修复结果已保存到 bridge_contract_fix_results.json")
    
    success_count = sum(1 for result in results.values() if result.get('success', False))
    print(f"✅ 成功修复 {success_count} 个桥接合约")
    
    if success_count > 0:
        print("\n📋 新的桥接合约地址:")
        for chain_id, result in results.items():
            if result.get('success'):
                print(f"   {chain_id}: {result['new_address']}")
    
    return results

if __name__ == "__main__":
    fix_bridge_contract()

