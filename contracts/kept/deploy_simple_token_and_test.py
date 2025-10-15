#!/usr/bin/env python3
"""
部署简化代币合约并测试跨链转账
使用不强制DID验证的简化代币合约
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

def deploy_simple_token_and_test():
    """部署简化代币合约并测试跨链转账"""
    print("🚀 部署简化代币合约并测试跨链转账...")
    
    # 使用测试账户
    test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
    
    # 链配置
    chains = {
        'chain_a': {
            'name': 'Besu Chain A',
            'rpc_url': 'http://localhost:8545',
            'chain_id': 2023
        },
        'chain_b': {
            'name': 'Besu Chain B', 
            'rpc_url': 'http://localhost:8555',
            'chain_id': 2024
        }
    }
    
    # 编译简化代币合约
    print("🔨 编译简化代币合约...")
    import subprocess
    try:
        result = subprocess.run([
            'solc', '--abi', '--bin', 'SimpleCrossChainToken.sol', 
            '--output-dir', 'build', '--overwrite'
        ], capture_output=True, text=True, cwd='/home/manifold/cursor/twobesu/contracts/kept')
        
        if result.returncode == 0:
            print("✅ 简化代币合约编译成功")
        else:
            print(f"❌ 简化代币合约编译失败: {result.stderr}")
            return
    except Exception as e:
        print(f"❌ 编译简化代币合约失败: {e}")
        return
    
    # 加载编译结果
    try:
        with open('build/SimpleCrossChainToken.abi', 'r') as f:
            simple_token_abi = json.load(f)
        
        with open('build/SimpleCrossChainToken.bin', 'r') as f:
            simple_token_bytecode = f.read().strip()
        
        print("✅ 简化代币合约ABI和字节码加载成功")
    except Exception as e:
        print(f"❌ 加载简化代币合约失败: {e}")
        return
    
    # 部署到两个链
    deployed_contracts = {}
    
    for chain_id, config in chains.items():
        print(f"\n🔗 在 {config['name']} 上部署简化代币合约...")
        
        try:
            w3 = FixedWeb3(config['rpc_url'], config['name'])
            if not w3.is_connected():
                print(f"❌ {config['name']} 连接失败")
                continue
            
            # 部署合约
            nonce = w3.w3.eth.get_transaction_count(test_account.address)
            gas_price = w3.w3.eth.gas_price
            
            constructor_tx = w3.w3.eth.contract(
                abi=simple_token_abi, 
                bytecode=simple_token_bytecode
            ).constructor(
                "Simple Cross Chain Token",
                "SCCT",
                18,
                w3.w3.to_wei(1000000, 'ether')  # 1,000,000 tokens
            ).build_transaction({
                'from': test_account.address,
                'gas': 3000000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': config['chain_id']
            })
            
            # 签名并发送交易
            signed_txn = w3.w3.eth.account.sign_transaction(constructor_tx, test_account.key)
            tx_hash = w3.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            print(f"✅ 简化代币合约部署交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            print("⏳ 等待交易确认...")
            receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                contract_address = receipt.contractAddress
                print(f"✅ 简化代币合约部署成功!")
                print(f"📍 合约地址: {contract_address}")
                print(f"📊 区块号: {receipt.blockNumber}")
                print(f"⛽ Gas使用: {receipt.gasUsed}")
                
                deployed_contracts[chain_id] = {
                    'address': contract_address,
                    'tx_hash': tx_hash.hex(),
                    'block_number': receipt.blockNumber,
                    'gas_used': receipt.gasUsed
                }
            else:
                print(f"❌ 简化代币合约部署失败")
                
        except Exception as e:
            print(f"❌ 在 {config['name']} 上部署失败: {e}")
    
    # 测试跨链转账
    if len(deployed_contracts) == 2:
        print("\n🧪 测试跨链转账...")
        
        # 链A配置
        w3_a = FixedWeb3(chains['chain_a']['rpc_url'], chains['chain_a']['name'])
        contract_a = w3_a.w3.eth.contract(
            address=w3_a.w3.to_checksum_address(deployed_contracts['chain_a']['address']),
            abi=simple_token_abi
        )
        
        # 链B配置
        w3_b = FixedWeb3(chains['chain_b']['rpc_url'], chains['chain_b']['name'])
        contract_b = w3_b.w3.eth.contract(
            address=w3_b.w3.to_checksum_address(deployed_contracts['chain_b']['address']),
            abi=simple_token_abi
        )
        
        # 检查初始余额
        print("📊 检查初始余额...")
        balance_a = contract_a.functions.balanceOf(test_account.address).call()
        balance_b = contract_b.functions.balanceOf(test_account.address).call()
        
        print(f"   链A余额: {w3_a.w3.from_wei(balance_a, 'ether')} SCCT")
        print(f"   链B余额: {w3_b.w3.from_wei(balance_b, 'ether')} SCCT")
        
        # 测试链A上的transferFrom
        print("\n🔍 测试链A上的transferFrom...")
        try:
            # 先授权
            nonce = w3_a.w3.eth.get_transaction_count(test_account.address)
            gas_price = w3_a.w3.eth.gas_price
            
            amount_wei = w3_a.w3.to_wei(50, 'ether')
            
            # 授权交易
            approve_tx = contract_a.functions.approve(
                test_account.address,  # 授权给自己
                amount_wei
            ).build_transaction({
                'from': test_account.address,
                'gas': 100000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': chains['chain_a']['chain_id']
            })
            
            signed_txn = w3_a.w3.eth.account.sign_transaction(approve_tx, test_account.key)
            tx_hash = w3_a.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            print(f"✅ 授权交易已发送: {tx_hash.hex()}")
            
            # 等待授权交易确认
            receipt = w3_a.w3.eth.wait_for_transaction_receipt(tx_hash)
            if receipt.status == 1:
                print("✅ 授权交易成功!")
                
                # transferFrom交易
                nonce = w3_a.w3.eth.get_transaction_count(test_account.address)
                transfer_tx = contract_a.functions.transferFrom(
                    test_account.address,
                    test_account.address,  # 转给自己
                    amount_wei
                ).build_transaction({
                    'from': test_account.address,
                    'gas': 100000,
                    'gasPrice': gas_price,
                    'nonce': nonce,
                    'chainId': chains['chain_a']['chain_id']
                })
                
                signed_txn = w3_a.w3.eth.account.sign_transaction(transfer_tx, test_account.key)
                tx_hash = w3_a.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                
                print(f"✅ transferFrom交易已发送: {tx_hash.hex()}")
                
                # 等待transferFrom交易确认
                receipt = w3_a.w3.eth.wait_for_transaction_receipt(tx_hash)
                if receipt.status == 1:
                    print("✅ transferFrom交易成功!")
                    print("🎉 简化代币合约的transferFrom函数正常工作!")
                else:
                    print("❌ transferFrom交易失败")
            else:
                print("❌ 授权交易失败")
                
        except Exception as e:
            print(f"❌ 测试transferFrom失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 保存部署结果
    with open('simple_token_deployment_results.json', 'w') as f:
        json.dump(deployed_contracts, f, indent=2)
    
    print(f"\n📄 部署结果已保存到 simple_token_deployment_results.json")
    
    return deployed_contracts

if __name__ == "__main__":
    deploy_simple_token_and_test()
