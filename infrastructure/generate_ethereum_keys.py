#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成以太坊风格的私钥、公钥和地址
生成20组不同的密钥对并输出到JSON
"""

import json
import secrets
from datetime import datetime
from eth_account import Account
from eth_utils import to_checksum_address

# 生成随机密钥
def generate_ethereum_keypairs(count=20):
    """
    生成以太坊风格的密钥对

    Args:
        count: 要生成的密钥对数量

    Returns:
        包含私钥、公钥和地址的字典列表
    """
    print(f"🔐 生成 {count} 组以太坊密钥对...")
    print("=" * 60)

    keypairs = []

    # 启用额外的账户功能以获取私钥
    Account.enable_unaudited_hdwallet_features()

    for i in range(count):
        # 生成随机私钥（32字节）
        private_key = secrets.token_hex(32)

        # 从私钥创建账户
        account = Account.from_key(private_key)

        # 获取地址（checksum格式）
        address = to_checksum_address(account.address)

        # 获取公钥
        # 以太坊的公钥可以从私钥推导，但通常不直接使用
        # 我们可以通过私钥重新计算
        private_key_bytes = bytes.fromhex(private_key)
        account_obj = Account.from_key(private_key_bytes)

        # 公钥不是直接存储的，但可以从私钥推导
        # 在以太坊中，地址就是公钥的Keccak-256哈希的最后20字节
        # 我们可以通过私钥恢复完整公钥
        public_key = account_obj.key.hex() if hasattr(account_obj, 'key') else None

        keypair = {
            "index": i + 1,
            "private_key": "0x" + private_key,
            "address": address,
            "public_key": public_key or "Derived from private key"
        }

        keypairs.append(keypair)

        print(f"[{i+1}/{count}] 地址: {address}")

    return keypairs


def save_to_json(keypairs, filename="ethereum_keys.json"):
    """
    保存密钥对到JSON文件

    Args:
        keypairs: 密钥对列表
        filename: 输出文件名
    """
    data = {
        "generated_at": datetime.now().isoformat(),
        "total_count": len(keypairs),
        "description": "以太坊风格的私钥、公钥和地址",
        "keypairs": keypairs
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 密钥对已保存到: {filename}")
    return filename


def display_summary(keypairs):
    """显示生成摘要"""
    print("\n" + "=" * 60)
    print("📊 生成摘要")
    print("=" * 60)
    print(f"总数: {len(keypairs)}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if keypairs:
        print(f"\n第一个:")
        print(f"  地址: {keypairs[0]['address']}")
        print(f"  私钥: {keypairs[0]['private_key']}")

        print(f"\n最后一个:")
        print(f"  地址: {keypairs[-1]['address']}")
        print(f"  私钥: {keypairs[-1]['private_key']}")

    print("\n⚠️  安全警告:")
    print("  - 私钥非常重要，请妥善保管！")
    print("  - 不要将私钥分享给任何人！")
    print("  - 建议将此文件存储在安全的地方！")
    print("=" * 60)


def main():
    """主函数"""
    print("=" * 60)
    print("🔑 以太坊密钥对生成器")
    print("=" * 60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 生成20组密钥对
    count = 20
    keypairs = generate_ethereum_keypairs(count)

    # 保存到JSON
    save_to_json(keypairs, "ethereum_keys_20.json")

    # 显示摘要
    display_summary(keypairs)


if __name__ == "__main__":
    main()
