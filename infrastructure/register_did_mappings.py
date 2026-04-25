#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
注册 DID-Address 映射到两个 Besu 链的 CrossChainDIDVerifier 合约
从 config/did_address_map.json 读取映射数据
"""

import json
import time
import sys
sys.path.insert(0, 'oracle')
from web3 import Web3
from web3_fixed_connection import FixedWeb3
from typing import Dict, List, Any

def load_json_file(filepath: str) -> Any:
    """加载 JSON 文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 加载文件失败 {filepath}: {e}")
        return None

def get_contract_abi() -> List:
    """获取 CrossChainDIDVerifier 合约 ABI"""
    # 只需要 verifyIdentity 函数的 ABI
    return [{
        "inputs": [
            {"internalType": "address", "name": "_user", "type": "address"},
            {"internalType": "string", "name": "_did", "type": "string"}
        ],
        "name": "verifyIdentity",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }]

def register_chain_mappings(fixed_w3: FixedWeb3, contract_address: str,
                            private_key: str, mappings: List[Dict],
                            chain_name: str) -> Dict:
    """注册单个链的 DID 映射"""
    print(f"\n{'=' * 60}")
    print(f"📝 开始注册 {chain_name} 的 DID 映射")
    print(f"{'=' * 60}")

    w3 = fixed_w3.w3  # 获取底层的 Web3 实例

    # 获取合约实例
    account = w3.eth.account.from_key(private_key)
    w3.eth.default_account = account.address

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=get_contract_abi()
    )

    print(f"📋 合约地址: {contract_address}")
    print(f"👤 调用者地址: {account.address}")
    print(f"📊 待注册映射数: {len(mappings)}")

    # 统计
    success_count = 0
    failed_count = 0
    results = []

    # 批量注册
    for idx, mapping in enumerate(mappings, 1):
        try:
            print(f"\n[{idx}/{len(mappings)}] 注册映射...")
            print(f"  DID: {mapping['did']}")
            print(f"  Address: {mapping['address']}")

            # 构建交易
            gas_price = fixed_w3.get_gas_price()
            nonce = fixed_w3.get_nonce(account.address)

            transaction = contract.functions.verifyIdentity(
                Web3.to_checksum_address(mapping['address']),
                mapping['did']
            ).build_transaction({
                'from': account.address,
                'gas': 200000,
                'gasPrice': gas_price,
                'nonce': nonce,
            })

            # 签名交易
            signed_txn = w3.eth.account.sign_transaction(transaction, private_key)

            # 发送交易
            tx_hash = fixed_w3.send_raw_transaction(signed_txn.rawTransaction)
            if not tx_hash:
                raise Exception("发送交易失败")
            tx_hash_hex = tx_hash.hex()

            print(f"  ⏳ 交易已发送: {tx_hash_hex}")

            # 等待交易确认
            receipt = fixed_w3.wait_for_transaction_receipt(tx_hash, timeout=120)
            if not receipt:
                raise Exception("等待交易确认超时")

            if receipt['status'] == 1:
                success_count += 1
                print(f"  ✅ 成功！区块: {receipt['blockNumber']}")
                print(f"  📊 进度: {success_count}/{len(mappings)} 成功, {failed_count} 失败")
                results.append({
                    "did": mapping['did'],
                    "address": mapping['address'],
                    "tx_hash": tx_hash_hex,
                    "status": "success",
                    "block_number": receipt['blockNumber']
                })
            else:
                failed_count += 1
                print(f"  ❌ 交易失败")
                print(f"  📊 进度: {success_count}/{len(mappings)} 成功, {failed_count} 失败")
                results.append({
                    "did": mapping['did'],
                    "address": mapping['address'],
                    "tx_hash": tx_hash_hex,
                    "status": "failed"
                })

            # 短暂延迟，避免过快请求
            time.sleep(0.5)

        except Exception as e:
            failed_count += 1
            print(f"  ❌ 错误: {e}")
            print(f"  📊 进度: {success_count}/{len(mappings)} 成功, {failed_count} 失败")
            results.append({
                "did": mapping['did'],
                "address": mapping['address'],
                "tx_hash": None,
                "status": f"error: {str(e)}"
            })

    # 输出统计
    print(f"\n{'=' * 60}")
    print(f"📊 {chain_name} 注册完成")
    print(f"{'=' * 60}")
    print(f"✅ 成功: {success_count}/{len(mappings)}")
    print(f"❌ 失败: {failed_count}/{len(mappings)}")

    return {
        "chain_name": chain_name,
        "contract_address": contract_address,
        "total": len(mappings),
        "success": success_count,
        "failed": failed_count,
        "results": results
    }

def main():
    """主函数"""
    print("🔐 DID-Address 映射批量注册工具")
    print("=" * 60)
    print("📌 功能: 在两个 Besu 链上注册 DID-Address 映射")
    print("📌 输入: config/did_address_map.json")
    print("=" * 60)

    # 1. 加载配置文件
    print("\n1️⃣ 加载配置文件...")

    did_address_map = load_json_file("config/did_address_map.json")
    if not did_address_map:
        return

    deployed_config = load_json_file("config/deployed_contracts_config.json")
    if not deployed_config:
        return

    print("   ✅ 配置文件加载成功")

    # 2. 提取映射数据
    print("\n2️⃣ 提取映射数据...")
    mappings = did_address_map.get("mappings", [])
    print(f"   ✅ 找到 {len(mappings)} 条映射")

    # 3. 提取链配置
    print("\n3️⃣ 提取链配置...")

    # Chain A
    chain_a_rpc = deployed_config['chain_a']['rpc_url']
    chain_a_private_key = deployed_config['chain_a']['private_key']
    chain_a_did_verifier = deployed_config['chain_a']['contracts']['DIDVerifier']['address']

    print(f"   Chain A:")
    print(f"     RPC: {chain_a_rpc}")
    print(f"     DIDVerifier: {chain_a_did_verifier}")

    # Chain B
    chain_b_rpc = deployed_config['chain_b']['rpc_url']
    chain_b_private_key = deployed_config['chain_b']['private_key']
    chain_b_did_verifier = deployed_config['chain_b']['contracts']['DIDVerifier']['address']

    print(f"   Chain B:")
    print(f"     RPC: {chain_b_rpc}")
    print(f"     DIDVerifier: {chain_b_did_verifier}")

    # 4. 连接到 Chain A
    print("\n4️⃣ 连接到 Besu 链...")
    w3_chain_a = FixedWeb3(chain_a_rpc, "Chain A")
    w3_chain_b = FixedWeb3(chain_b_rpc, "Chain B")

    if not w3_chain_a.is_connected():
        print(f"   ❌ Chain A 连接失败")
        return

    if not w3_chain_b.is_connected():
        print(f"   ❌ Chain B 连接失败")
        return

    block_a = w3_chain_a.get_latest_block()
    block_b = w3_chain_b.get_latest_block()

    print(f"   ✅ Chain A 已连接 (块高: {block_a['number'] if block_a else 'N/A'})")
    print(f"   ✅ Chain B 已连接 (块高: {block_b['number'] if block_b else 'N/A'})")

    # 5. 确认操作
    print(f"\n⚠️  准备注册 {len(mappings)} 条映射到 2 条链")
    print(f"   总计交易数: {len(mappings) * 2}")
    print(f"   预计时间: {len(mappings) * 2 * 2} 秒（估计）")

    # 检查余额
    account_a = w3_chain_a.w3.eth.account.from_key(chain_a_private_key)
    account_b = w3_chain_b.w3.eth.account.from_key(chain_b_private_key)

    balance_a_wei, balance_a_eth = w3_chain_a.get_balance(account_a.address)
    balance_b_wei, balance_b_eth = w3_chain_b.get_balance(account_b.address)

    print(f"\n💰 账户余额:")
    print(f"   Chain A ({account_a.address}): {balance_a_eth:.4f} ETH")
    print(f"   Chain B ({account_b.address}): {balance_b_eth:.4f} ETH")

    # 6. 注册到 Chain A
    print(f"\n{'=' * 60}")
    print(f"🚀 开始批量注册")
    print(f"{'=' * 60}")

    chain_a_result = register_chain_mappings(
        w3_chain_a,
        chain_a_did_verifier,
        chain_a_private_key,
        mappings,
        "Chain A"
    )

    # 7. 注册到 Chain B
    chain_b_result = register_chain_mappings(
        w3_chain_b,
        chain_b_did_verifier,
        chain_b_private_key,
        mappings,
        "Chain B"
    )

    # 8. 保存结果
    print(f"\n8️⃣ 保存注册结果...")

    registration_result = {
        "timestamp": time.time(),
        "summary": {
            "total_mappings": len(mappings),
            "chain_a": {
                "total": chain_a_result['total'],
                "success": chain_a_result['success'],
                "failed": chain_a_result['failed']
            },
            "chain_b": {
                "total": chain_b_result['total'],
                "success": chain_b_result['success'],
                "failed": chain_b_result['failed']
            }
        },
        "chain_a": chain_a_result,
        "chain_b": chain_b_result
    }

    output_file = "config/did_registration_result.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(registration_result, f, indent=2, ensure_ascii=False)

    print(f"   ✅ 结果已保存: {output_file}")

    # 9. 最终统计
    print(f"\n{'=' * 60}")
    print(f"✅ 所有注册完成！")
    print(f"{'=' * 60}")

    total_success = chain_a_result['success'] + chain_b_result['success']
    total_failed = chain_a_result['failed'] + chain_b_result['failed']

    print(f"\n📊 总体统计:")
    print(f"  Chain A: {chain_a_result['success']}/{chain_a_result['total']} 成功")
    print(f"  Chain B: {chain_b_result['success']}/{chain_b_result['total']} 成功")
    print(f"  总计: {total_success}/{total_success + total_failed} 成功")

    if total_failed > 0:
        print(f"\n⚠️  有 {total_failed} 条注册失败，请查看结果文件")

if __name__ == "__main__":
    main()
