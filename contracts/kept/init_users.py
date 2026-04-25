#!/usr/bin/env python3
"""初始化用户DID验证 - 简单版"""
import json
import sys
from web3 import Web3
from eth_account import Account

# 配置
CONFIG_PATH = "/home/manifold/cursor/cross-chain/config/deployed_contracts_config.json"
ABI_PATH = "/home/manifold/cursor/cross-chain/contracts/kept"
CHAIN_A_RPC = "http://localhost:8545"

def main():
    print("="*70)
    print("初始化用户DID验证")
    print("="*70)
    
    # 加载配置
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    
    # 连接Chain A
    w3 = Web3(Web3.HTTPProvider(CHAIN_A_RPC))
    if not w3.is_connected():
        print("❌ 无法连接到Chain A")
        return False
    
    print(f"✅ 已连接到Chain A，区块: {w3.eth.block_number}")
    
    # 获取合约信息
    chain_a = config['chain_a']
    did_verifier_addr = chain_a['contracts']['DIDVerifier']['address']
    admin_addr = chain_a['deployer_address']
    admin_key = chain_a['private_key']
    
    # 加载DIDVerifier ABI
    with open(f"{ABI_PATH}/DIDVerifier.json") as f:
        abi = json.load(f)['abi']
    
    did_verifier = w3.eth.contract(address=did_verifier_addr, abi=abi)
    
    # 检查当前已验证用户数
    current_count = did_verifier.functions.getVerifiedUserCount().call()
    print(f"\n当前已验证用户数: {current_count}")
    
    if current_count > 0:
        print("⚠️  已有用户注册，跳过初始化")
        return True
    
    # 注册管理员（Oracle）
    print("\n注册管理员用户...")
    oracle_did = config['oracle_config']['chain_a']['oracle_did']
    did_hash = Web3.solidity_keccak(['string'], [oracle_did])
    
    # 构建交易
    account = Account.from_key(admin_key)
    nonce = w3.eth.get_transaction_count(account.address)
    
    # 调用registerUser
    tx = did_verifier.functions.registerUser(did_hash).build_transaction({
        'from': account.address,
        'gas': 200000,
        'gasPrice': w3.to_wei('1', 'gwei'),
        'nonce': nonce,
    })
    
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    if receipt['status'] == 1:
        print(f"✅ 管理员注册成功, tx: {tx_hash.hex()[:10]}...")
    else:
        print(f"❌ 管理员注册失败")
        return False
    
    print(f"\n✅ 初始化完成！")
    print(f"   管理员DID: {oracle_did}")
    print(f"   管理员地址: {account.address}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
