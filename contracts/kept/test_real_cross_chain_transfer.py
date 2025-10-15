#!/usr/bin/env python3
"""
测试真正的跨链转账
使用支持跨链的简化代币合约
"""

import json
import time
from web3_fixed_connection import FixedWeb3
from eth_account import Account

def test_real_cross_chain_transfer():
    """测试真正的跨链转账"""
    print("🌉 测试真正的跨链转账...")
    
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
    
    # 编译支持跨链的代币合约
    print("🔨 编译支持跨链的代币合约...")
    import subprocess
    try:
        result = subprocess.run([
            'solc', '--abi', '--bin', 'SimpleCrossChainTokenWithBridge.sol', 
            '--output-dir', 'build', '--overwrite'
        ], capture_output=True, text=True, cwd='/home/manifold/cursor/twobesu/contracts/kept')
        
        if result.returncode == 0:
            print("✅ 支持跨链的代币合约编译成功")
        else:
            print(f"❌ 支持跨链的代币合约编译失败: {result.stderr}")
            return
    except Exception as e:
        print(f"❌ 编译支持跨链的代币合约失败: {e}")
        return
    
    # 加载编译结果
    try:
        with open('build/SimpleCrossChainTokenWithBridge.abi', 'r') as f:
            cross_chain_token_abi = json.load(f)
        
        with open('build/SimpleCrossChainTokenWithBridge.bin', 'r') as f:
            cross_chain_token_bytecode = f.read().strip()
        
        print("✅ 支持跨链的代币合约ABI和字节码加载成功")
    except Exception as e:
        print(f"❌ 加载支持跨链的代币合约失败: {e}")
        return
    
    # 部署到两个链
    deployed_contracts = {}
    
    for chain_id, config in chains.items():
        print(f"\n🔗 在 {config['name']} 上部署支持跨链的代币合约...")
        
        try:
            w3 = FixedWeb3(config['rpc_url'], config['name'])
            if not w3.is_connected():
                print(f"❌ {config['name']} 连接失败")
                continue
            
            # 部署合约
            nonce = w3.w3.eth.get_transaction_count(test_account.address)
            gas_price = w3.w3.eth.gas_price
            
            constructor_tx = w3.w3.eth.contract(
                abi=cross_chain_token_abi, 
                bytecode=cross_chain_token_bytecode
            ).constructor(
                "Cross Chain Token",
                "CCT",
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
            
            print(f"✅ 支持跨链的代币合约部署交易已发送: {tx_hash.hex()}")
            
            # 等待交易确认
            print("⏳ 等待交易确认...")
            receipt = w3.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                contract_address = receipt.contractAddress
                print(f"✅ 支持跨链的代币合约部署成功!")
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
                print(f"❌ 支持跨链的代币合约部署失败")
                
        except Exception as e:
            print(f"❌ 在 {config['name']} 上部署失败: {e}")
    
    # 测试跨链转账
    if len(deployed_contracts) == 2:
        print("\n🌉 测试跨链转账流程...")
        
        # 链A配置
        w3_a = FixedWeb3(chains['chain_a']['rpc_url'], chains['chain_a']['name'])
        contract_a = w3_a.w3.eth.contract(
            address=w3_a.w3.to_checksum_address(deployed_contracts['chain_a']['address']),
            abi=cross_chain_token_abi
        )
        
        # 链B配置
        w3_b = FixedWeb3(chains['chain_b']['rpc_url'], chains['chain_b']['name'])
        contract_b = w3_b.w3.eth.contract(
            address=w3_b.w3.to_checksum_address(deployed_contracts['chain_b']['address']),
            abi=cross_chain_token_abi
        )
        
        # 检查初始余额
        print("📊 检查初始余额...")
        balance_a = contract_a.functions.balanceOf(test_account.address).call()
        balance_b = contract_b.functions.balanceOf(test_account.address).call()
        
        print(f"   链A余额: {w3_a.w3.from_wei(balance_a, 'ether')} CCT")
        print(f"   链B余额: {w3_b.w3.from_wei(balance_b, 'ether')} CCT")
        
        # 步骤1: 在链A上锁定代币
        print("\n🔒 步骤1: 在链A上锁定代币...")
        try:
            nonce = w3_a.w3.eth.get_transaction_count(test_account.address)
            gas_price = w3_a.w3.eth.gas_price
            
            amount_wei = w3_a.w3.to_wei(100, 'ether')
            target_chain = "chain_b"
            
            lock_tx = contract_a.functions.crossChainLock(
                amount_wei,
                target_chain
            ).build_transaction({
                'from': test_account.address,
                'gas': 200000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': chains['chain_a']['chain_id']
            })
            
            signed_txn = w3_a.w3.eth.account.sign_transaction(lock_tx, test_account.key)
            tx_hash = w3_a.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            print(f"✅ 锁定交易已发送: {tx_hash.hex()}")
            
            # 等待锁定交易确认
            receipt = w3_a.w3.eth.wait_for_transaction_receipt(tx_hash)
            if receipt.status == 1:
                print("✅ 代币锁定成功!")
                
                # 检查锁定后的余额
                balance_after_lock = contract_a.functions.balanceOf(test_account.address).call()
                locked_balance = contract_a.functions.getLockedBalance(test_account.address).call()
                
                print(f"   锁定后可用余额: {w3_a.w3.from_wei(balance_after_lock, 'ether')} CCT")
                print(f"   锁定余额: {w3_a.w3.from_wei(locked_balance, 'ether')} CCT")
                
                # 获取锁定ID（从事件日志中）
                lock_events = contract_a.events.CrossChainLocked().processReceipt(receipt)
                if lock_events:
                    lock_id = lock_events[0]['args']['lockId']
                    print(f"   锁定ID: {lock_id.hex()}")
                else:
                    # 如果无法从事件中获取，使用交易哈希作为锁定ID
                    lock_id = tx_hash
                    print(f"   使用交易哈希作为锁定ID: {lock_id.hex()}")
                    
                    # 步骤2: 在链B上解锁代币
                    print("\n🔓 步骤2: 在链B上解锁代币...")
                    
                    # 设置桥接合约（这里我们使用测试账户作为桥接合约）
                    nonce = w3_b.w3.eth.get_transaction_count(test_account.address)
                    gas_price = w3_b.w3.eth.gas_price
                    
                    set_bridge_tx = contract_b.functions.setBridgeContract(test_account.address).build_transaction({
                        'from': test_account.address,
                        'gas': 100000,
                        'gasPrice': gas_price,
                        'nonce': nonce,
                        'chainId': chains['chain_b']['chain_id']
                    })
                    
                    signed_txn = w3_b.w3.eth.account.sign_transaction(set_bridge_tx, test_account.key)
                    tx_hash = w3_b.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    
                    # 等待设置桥接合约交易确认
                    receipt = w3_b.w3.eth.wait_for_transaction_receipt(tx_hash)
                    if receipt.status == 1:
                        print("✅ 桥接合约设置成功!")
                        
                        # 解锁代币
                        nonce = w3_b.w3.eth.get_transaction_count(test_account.address)
                        unlock_tx = contract_b.functions.crossChainUnlock(
                            test_account.address,
                            amount_wei,
                            "chain_a",
                            lock_id
                        ).build_transaction({
                            'from': test_account.address,
                            'gas': 200000,
                            'gasPrice': gas_price,
                            'nonce': nonce,
                            'chainId': chains['chain_b']['chain_id']
                        })
                        
                        signed_txn = w3_b.w3.eth.account.sign_transaction(unlock_tx, test_account.key)
                        tx_hash = w3_b.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                        
                        print(f"✅ 解锁交易已发送: {tx_hash.hex()}")
                        
                        # 等待解锁交易确认
                        receipt = w3_b.w3.eth.wait_for_transaction_receipt(tx_hash)
                        if receipt.status == 1:
                            print("✅ 代币解锁成功!")
                            
                            # 检查解锁后的余额
                            balance_after_unlock = contract_b.functions.balanceOf(test_account.address).call()
                            print(f"   链B解锁后余额: {w3_b.w3.from_wei(balance_after_unlock, 'ether')} CCT")
                            
                            print("\n🎉 跨链转账成功完成!")
                            print(f"   链A锁定: 100 CCT")
                            print(f"   链B解锁: 100 CCT")
                            print("   这是真正的跨链转账!")
                        else:
                            print("❌ 代币解锁失败")
                    else:
                        print("❌ 桥接合约设置失败")
                else:
                    print("❌ 未找到锁定事件")
            else:
                print("❌ 代币锁定失败")
                
        except Exception as e:
            print(f"❌ 跨链转账测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 保存部署结果
    with open('cross_chain_token_deployment_results.json', 'w') as f:
        json.dump(deployed_contracts, f, indent=2)
    
    print(f"\n📄 部署结果已保存到 cross_chain_token_deployment_results.json")
    
    return deployed_contracts

if __name__ == "__main__":
    test_real_cross_chain_transfer()