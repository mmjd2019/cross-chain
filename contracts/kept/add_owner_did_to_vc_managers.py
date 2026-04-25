#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为三种非工作的VCManager合约添加owner DID到oracle允许列表
解决除InspectionReport外其他三种类型跨链传输失败的问题
"""

import json
import sys
from web3 import Web3
from web3.middleware import geth_poa_middleware

# 配置
CONFIG_PATH = "/home/manifold/cursor/cross-chain-new/config/cross_chain_oracle_config.json"
ABI_DIR = "/home/manifold/cursor/cross-chain-new/contracts/kept/contract_abis"

# 所有合约的owner账户 0x81Be24626338695584B5beaEBf51e09879A0eCc6 在DIDVerifier中注册的DID
OWNER_DID = "DPvobytTtKvmyeRTJZYjsg"

CONTRACTS_TO_CONFIGURE = {
    "InsuranceContractVCManager": {
        "address": "0xC1e2E535D3979F868455A82D208EfABdC3174aa5",
        "owner_did": OWNER_DID,
    },
    "CertificateOfOriginVCManager": {
        "address": "0x8499286b6d3B9c4b9c15A8A855a8B4839026fD7C",
        "owner_did": OWNER_DID,
    },
    "BillOfLadingVCManager": {
        "address": "0xA9a4074B2A92E63e4c7DC440E80ea1f76a28F701",
        "owner_did": OWNER_DID,
    },
}


def main():
    # 加载配置
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)

    rpc_url = config['chains']['chain_a']['rpc_url']
    gas_price = config['blockchain']['gas_price']
    gas_limit = config['blockchain']['gas_limit']

    # 使用vc_manager_owner账户（合约的owner/admin）
    owner_private_key = config['vc_manager_owner']['private_key']

    # 连接链
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 30}))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    try:
        block = w3.eth.get_block('latest')
        print(f"✅ 已连接到链，当前区块: {block['number']}")
    except Exception as e:
        print(f"❌ 无法连接到链 {rpc_url}: {e}")
        return 1

    account = w3.eth.account.from_key(owner_private_key)
    account_address = account.address
    print(f"✅ 已连接到链，使用账户: {account_address}")

    results = {}

    for contract_name, contract_info in CONTRACTS_TO_CONFIGURE.items():
        print(f"\n{'='*60}")
        print(f"📝 配置 {contract_name}")
        print(f"   合约地址: {contract_info['address']}")
        print(f"   Owner DID: {contract_info['owner_did']}")

        # 加载ABI
        abi_path = f"{ABI_DIR}/{contract_name}.json"
        with open(abi_path, 'r') as f:
            abi_data = json.load(f)

        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_info['address']),
            abi=abi_data['abi']
        )

        # 先检查DID是否已在允许列表中
        try:
            is_already_allowed = contract.functions.oracleAllowedDIDs(contract_info['owner_did']).call()
            if is_already_allowed:
                print(f"   ⚠️  DID已在允许列表中，跳过")
                results[contract_name] = "already_allowed"
                continue
        except Exception as e:
            print(f"   ⚠️  检查DID状态失败: {e}")
            # 继续尝试添加

        # 添加owner DID到oracle允许列表
        try:
            tx = contract.functions.addOracleDID(contract_info['owner_did']).build_transaction({
                'from': account_address,
                'gasPrice': gas_price,
                'gas': gas_limit,
                'nonce': w3.eth.get_transaction_count(account_address),
            })

            signed = w3.eth.account.sign_transaction(tx, owner_private_key)
            tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
            print(f"   交易哈希: {tx_hash.hex()}")

            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt['status'] == 1:
                print(f"   ✅ Owner DID添加成功")
                results[contract_name] = "success"
            else:
                print(f"   ❌ 交易回滚")
                results[contract_name] = "failed"
        except Exception as e:
            error_msg = str(e)
            if "Already allowed" in error_msg:
                print(f"   ⚠️  DID已存在（合约端检查）")
                results[contract_name] = "already_allowed"
            else:
                print(f"   ❌ 添加失败: {error_msg}")
                results[contract_name] = f"error: {error_msg}"

    # 汇总
    print(f"\n{'='*60}")
    print("📊 配置结果汇总:")
    for name, result in results.items():
        status = "✅" if result in ("success", "already_allowed") else "❌"
        print(f"  {status} {name}: {result}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
