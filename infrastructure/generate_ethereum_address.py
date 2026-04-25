#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于固定种子生成以太坊账户
直接输出到 config/address.json
"""

import json
import os
from datetime import datetime
from eth_account import Account
from eth_utils import to_checksum_address
from eth_account.hdaccount import Mnemonic
import hashlib

# 启用额外的账户功能以获取私钥
Account.enable_unaudited_hdwallet_features()


def generate_account_from_seed(seed_str):
    """
    从种子字符串生成以太坊账户

    Args:
        seed_str: 种子字符串

    Returns:
        包含 address, private_key, public_key 的字典
    """
    # 将种子字符串转换为32字节私钥
    seed_bytes = seed_str.encode('utf-8')
    # 使用SHA-256确保输出32字节
    private_key_bytes = hashlib.sha256(seed_bytes).digest()
    private_key_hex = private_key_bytes.hex()

    # 从私钥创建账户
    account = Account.from_key(private_key_hex)

    return {
        "address": to_checksum_address(account.address),
        "private_key": "0x" + private_key_hex,
        "public_key": "0x" + private_key_hex,
        "seed": seed_str
    }


def generate_besu_nodes():
    """
    生成Besu节点账户（固定种子）
    """
    print("📋 生成Besu节点账户...")

    # 使用固定的种子模式（与现有docker-compose配置匹配）
    seeds = [
        ("node1", "BesuNode1Validator2024"),
        ("node2", "BesuNode2Validator2024"),
        ("node3", "BesuNode3Validator2024"),
        ("node4", "BesuNode4Validator2024")
    ]

    nodes = {}
    for name, seed in seeds:
        account = generate_account_from_seed(seed)
        nodes[name] = {
            "address": account["address"],
            "private_key": account["private_key"],
            "public_key": account["public_key"],
            "role": "validator",
            "chain": "both",
            "seed": seed
        }
        print(f"  ✓ {name}: {account['address']}")

    return nodes


def generate_user_accounts(count=20):
    """
    生成用户测试账户（固定种子）

    Args:
        count: 要生成的账户数量
    """
    print(f"\n👤 生成{count}个用户测试账户...")

    accounts = []
    for i in range(1, count + 1):
        # 使用固定种子模式
        seed = f"UserAccount{i:03d}CrossChain2024"
        account = generate_account_from_seed(seed)

        accounts.append({
            "index": i,
            "address": account["address"],
            "private_key": account["private_key"],
            "public_key": account["public_key"],
            "seed": seed
        })

        if i <= 3 or i == count:
            print(f"  [{i:2d}] {account['address']}")
        elif i == 4:
            print(f"   ...")

    return accounts


def create_address_json():
    """
    创建完整的address.json配置
    """
    print("=" * 70)
    print("🔐 基于固定种子生成以太坊账户")
    print("=" * 70)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 生成Besu节点账户
    besu_nodes = generate_besu_nodes()

    # 生成用户账户
    user_accounts = generate_user_accounts(20)

    # 构建完整的配置
    config = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "description": "所有可用账户地址和合约地址配置文件（基于固定种子生成）",
            "version": "1.0",
            "generation_method": "fixed_seed"
        },
        "besu_nodes": {
            "description": "Besu区块链节点账户（用于验证和挖矿）",
            **besu_nodes
        },
        "user_accounts": {
            "description": "用户测试账户（用于合约交互和测试）",
            "accounts": user_accounts
        },
        "contracts": {
            "description": "智能合约地址（合约部署后自动更新）",
            "chain_a": {
                "description": "Chain A（发行链）合约地址",
                "did_verifier": None,
                "cross_chain_bridge": None,
                "cross_chain_token": None,
                "asset_manager": None,
                "contract_manager": None,
                "vc_managers": {
                    "inspection_report": None,
                    "insurance_contract": None,
                    "certificate_of_origin": None,
                    "bill_of_lading": None
                }
            },
            "chain_b": {
                "description": "Chain B（验证链）合约地址",
                "did_verifier": None,
                "cross_chain_bridge": None,
                "cross_chain_token": None,
                "asset_manager": None,
                "verification_contract": None
            }
        },
        "oracle_services": {
            "description": "Oracle服务地址",
            "chain_a_oracle": "0x81be24626338695584b5beaebf51e09879a0ecc6",
            "chain_b_oracle": "0x81be24626338695584b5beaebf51e09879a0ecc6"
        },
        "summary": {
            "total_besu_nodes": len(besu_nodes),
            "total_user_accounts": len(user_accounts),
            "total_contracts": {
                "chain_a": 8,
                "chain_b": 5
            }
        }
    }

    # 确保config目录存在
    output_file = "config/address.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # 保存到文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print()
    print("=" * 70)
    print("📊 生成完成统计")
    print("=" * 70)
    print(f"Besu节点账户: {len(besu_nodes)}个")
    print(f"用户测试账户: {len(user_accounts)}个")
    print(f"输出文件: {output_file}")
    print(f"生成方式: 固定种子（可重复）")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print(f"\n💾 配置已保存到: {output_file}")
    print()
    print("✅ 优点:")
    print("  • 使用固定种子，可重复生成相同账户")
    print("  • 不会因重新生成而丢失账户")
    print("  • 便于多环境部署（开发/测试/生产）")
    print()
    print("⚠️  安全提示:")
    print("  • 种子模式已公开，仅用于测试环境")
    print("  • 生产环境请使用安全的随机种子")
    print("  • 妥善保管生成的配置文件")
    print("=" * 70)

    # 自动更新依赖配置
    print("\n🔄 自动更新依赖配置...")

    # 1. 更新DID-Address映射
    print("  [1/2] 更新DID-Address映射...")
    try:
        import subprocess
        result = subprocess.run(
            ["python3", "generate_did_address_map.py"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print("  ✅ DID-Address映射已自动更新")
        else:
            print(f"  ⚠️  映射更新失败: {result.stderr}")
    except Exception as e:
        print(f"  ⚠️  映射更新出错: {e}")

    # 2. 更新跨链配置
    print("  [2/2] 更新跨链配置...")
    try:
        result = subprocess.run(
            ["python3", "generate_cross_chain_config.py"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print("  ✅ 跨链配置已自动更新")
        else:
            print(f"  ⚠️  跨链配置更新失败: {result.stderr}")
    except Exception as e:
        print(f"  ⚠️  跨链配置更新出错: {e}")


if __name__ == "__main__":
    create_address_json()
