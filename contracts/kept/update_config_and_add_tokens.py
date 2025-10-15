#!/usr/bin/env python3
"""
更新配置并添加代币支持
使用修复后的桥接合约添加代币支持
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

def update_config_and_add_tokens():
    """更新配置并添加代币支持"""
    print("🔧 更新配置并添加代币支持...")
    
    # 使用合约所有者账户
    owner_account = Account.from_key('0x1111111111111111111111111111111111111111111111111111111111111111')
    
    # 新的桥接合约地址
    new_bridge_addresses = {
        'chain_a': '0xc7253857256391E518c4aF60aDa5Eb5972Dd6Dbc',
        'chain_b': '0x27e5Ee255a177D1902D7FF48D66f950ed9408867'
    }
    
    # 链配置
    chains = {
        'chain_a': {
            'name': 'Besu Chain A',
            'rpc_url': 'http://localhost:8545',
            'chain_id': 2023,
            'bridge_address': new_bridge_addresses['chain_a']
        },
        'chain_b': {
            'name': 'Besu Chain B', 
            'rpc_url': 'http://localhost:8555',
            'chain_id': 2024,
            'bridge_address': new_bridge_addresses['chain_b']
        }
    }
    
    # 代币地址
    token_addresses = {
        'chain_a': '0x14D83c34ba0E1caC363039699d495e733B8A1182',
        'chain_b': '0x8Ce489412b110427695f051dAE4055d565BC7cF4'
    }
    
    # 加载桥接合约ABI
    with open('CrossChainBridge.json', 'r') as f:
        bridge_abi = json.load(f)['abi']
    
    results = {}
    
    for chain_id, config in chains.items():
        print(f"\n🔗 在 {config['name']} 上添加代币支持...")
        
        try:
            w3 = FixedWeb3(config['rpc_url'], config['name'])
            if not w3.is_connected():
                print(f"❌ {config['name']} 连接失败")
                continue
            
            # 创建桥接合约实例
            bridge_contract = w3.w3.eth.contract(
                address=w3.w3.to_checksum_address(config['bridge_address']),
                abi=bridge_abi
            )
            
            # 验证桥接合约
            print("   🔍 验证桥接合约...")
            owner = bridge_contract.functions.owner().call()
            verifier = bridge_contract.functions.verifier().call()
            chain_id_from_contract = bridge_contract.functions.chainId().call()
            
            print(f"   🔍 所有者: {owner}")
            print(f"   🔍 验证器: {verifier}")
            print(f"   🔍 链ID: {chain_id_from_contract}")
            
            if verifier == '0x0000000000000000000000000000000000000000':
                print(f"   ❌ 桥接合约未正确初始化")
                continue
            
            # 检查代币支持状态
            token_address = token_addresses[chain_id]
            print(f"   🔍 检查代币支持状态...")
            
            try:
                is_supported = bridge_contract.functions.isTokenSupported(
                    w3.w3.to_checksum_address(token_address)
                ).call()
                print(f"   🔍 代币 {token_address} 支持状态: {is_supported}")
                
                if is_supported:
                    print(f"   ✅ 代币已经支持")
                    results[chain_id] = {'success': True, 'already_supported': True}
                    continue
                    
            except Exception as e:
                print(f"   ⚠️  检查代币支持状态失败: {e}")
            
            # 添加代币支持
            print(f"   🔧 添加代币支持...")
            
            nonce = w3.w3.eth.get_transaction_count(owner_account.address)
            gas_price = w3.w3.eth.gas_price
            
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
                'chainId': config['chain_id']
            })
            
            # 签名并发送交易
            signed_txn = w3.w3.eth.account.sign_transaction(transaction, owner_account.key)
            tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            print(f"   ✅ 添加代币支持交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            print("   ⏳ 等待交易确认...")
            receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                print(f"   ✅ 代币支持添加成功!")
                print(f"   📊 区块号: {receipt.blockNumber}")
                print(f"   ⛽ Gas使用: {receipt.gasUsed}")
                
                # 验证代币支持
                print("   🔍 验证代币支持...")
                is_supported_after = bridge_contract.functions.isTokenSupported(
                    w3.w3.to_checksum_address(token_address)
                ).call()
                
                if is_supported_after:
                    print(f"   ✅ 代币支持验证成功!")
                    results[chain_id] = {
                        'success': True,
                        'already_supported': False,
                        'tx_hash': tx_hash.hex(),
                        'block_number': receipt.blockNumber,
                        'gas_used': receipt.gasUsed
                    }
                else:
                    print(f"   ❌ 代币支持验证失败")
                    results[chain_id] = {'success': False, 'error': 'Verification failed'}
            else:
                print(f"   ❌ 代币支持添加失败")
                results[chain_id] = {'success': False, 'error': 'Transaction failed'}
                
        except Exception as e:
            print(f"   ❌ 添加代币支持失败: {e}")
            results[chain_id] = {'success': False, 'error': str(e)}
    
    # 更新配置文件
    print("\n📝 更新配置文件...")
    
    # 更新cross_chain_config.json
    try:
        with open('cross_chain_config.json', 'r') as f:
            config_data = json.load(f)
        
        # 更新桥接合约地址
        for i, chain in enumerate(config_data['chains']):
            if chain['name'] == 'Besu Chain A':
                chain['bridge_address'] = new_bridge_addresses['chain_a']
            elif chain['name'] == 'Besu Chain B':
                chain['bridge_address'] = new_bridge_addresses['chain_b']
        
        with open('cross_chain_config.json', 'w') as f:
            json.dump(config_data, f, indent=2)
        
        print("   ✅ cross_chain_config.json 已更新")
    except Exception as e:
        print(f"   ❌ 更新 cross_chain_config.json 失败: {e}")
    
    # 保存结果
    with open('token_support_update_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 更新结果已保存到 token_support_update_results.json")
    
    success_count = sum(1 for result in results.values() if result.get('success', False))
    print(f"✅ 成功更新 {success_count} 个链的代币支持")
    
    if success_count > 0:
        print("\n📋 新的桥接合约地址:")
        for chain_id, result in results.items():
            if result.get('success'):
                print(f"   {chain_id}: {new_bridge_addresses[chain_id]}")
    
    return results

if __name__ == "__main__":
    update_config_and_add_tokens()

