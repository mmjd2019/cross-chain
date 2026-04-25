#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于 test_publish_did.py 创建的简化版
批量生成20个公共DID，直接输出到config/did.json
"""

import requests
import json
import time
import os
from datetime import datetime

# 配置
ISSUER_URL = "http://localhost:8080"
HOLDER_URL = "http://localhost:8081"
START_SEED = "000000000000000000000000002Agent"
COUNT = 20
OUTPUT_FILE = "config/did.json"  # 输出到config目录

# 管理员DID（已存在的固定DID）
ADMIN_DIDS = [
    {
        "seed": "000000000000000000000000000Agent",
        "did": "DPvobytTtKvmyeRTJZYjsg",
        "verkey": "7kqimjHKGQPRc2TXhmz1UZSYSqrV44AqEb62jrQkRj4i",
        "role": "admin_issuer"
    },
    {
        "seed": "000000000000000000000000001Agent",
        "did": "YL2HDxkVL8qMrssaZbvtfH",
        "verkey": "J5Lefumq5gcnMDyThDh9Sgz8yKrG2QEbxp1gKMEiETxB",
        "role": "admin_holder"
    }
]


def generate_seeds(start_seed, count):
    """生成种子序列"""
    seeds = []
    prefix = start_seed[:25]  # 0000000000000000000000000
    suffix = start_seed[-5:]  # Agent
    number_part = start_seed[25:-5]  # 002
    start_number = int(number_part)

    for i in range(count):
        number = start_number + i
        number_str = str(number).zfill(3)
        seed = f"{prefix}{number_str}{suffix}"
        seeds.append(seed)

    return seeds


def create_and_publish_did(admin_url, seed):
    """
    创建并发布DID到区块链

    关键：使用 params 而不是 json！
    """
    try:
        # 步骤1: 创建DID
        create_response = requests.post(
            f"{admin_url}/wallet/did/create",
            json={"seed": seed, "method": "sov"},
            timeout=30
        )

        if create_response.status_code not in [200, 201]:
            return {
                "seed": seed,
                "success": False,
                "error": f"创建失败: HTTP {create_response.status_code}"
            }

        did_result = create_response.json()['result']
        did = did_result['did']
        verkey = did_result['verkey']

        # 步骤2: 发布DID到区块链（使用 query parameters）
        time.sleep(0.1)

        publish_response = requests.post(
            f"{admin_url}/ledger/register-nym",
            params={"did": did, "verkey": verkey},  # 关键：使用 params
            timeout=30
        )

        if publish_response.status_code == 200:
            return {
                "seed": seed,
                "did": did,
                "verkey": verkey,
                "success": True
            }
        else:
            return {
                "seed": seed,
                "did": did,
                "success": False,
                "error": f"发布失败: {publish_response.text}"
            }

    except Exception as e:
        return {
            "seed": seed,
            "success": False,
            "error": str(e)
        }


def main():
    print("=" * 60)
    print("🌐 批量生成20个公共DID并输出到config/did.json")
    print("=" * 60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"发行者: {ISSUER_URL}")
    print(f"持有者: {HOLDER_URL}")
    print(f"起始种子: {START_SEED}")
    print(f"数量: {COUNT}")
    print(f"输出文件: {OUTPUT_FILE}")
    print("=" * 60)

    # 初始化结果数组（简单数组格式，与config/did.json一致）
    did_list = []

    # 添加管理员DID
    print("\n📋 添加管理员DID...")
    for admin_did in ADMIN_DIDS:
        did_list.append(admin_did)
        print(f"  ✓ {admin_did['role']}: {admin_did['did']}")

    # 生成种子
    seeds = generate_seeds(START_SEED, COUNT)
    print(f"\n✅ 生成 {len(seeds)} 个种子")

    # 为发行者和持有者生成DID
    total = len(seeds) * 2
    current = 0

    print(f"\n🚀 开始生成 {total} 个公共DID...\n")

    for seed in seeds:
        # 发行者 DID
        current += 1
        print(f"[{current}/{total}] 发行者 - 种子: {seed}", end=" ")
        issuer_result = create_and_publish_did(ISSUER_URL, seed)

        if issuer_result['success']:
            print(f"✅ {issuer_result['did']}")
            # 添加到列表（只保留必要字段）
            did_list.append({
                "seed": seed,
                "did": issuer_result['did'],
                "verkey": issuer_result['verkey'],
                "role": "issuer"
            })
        else:
            print(f"❌ {issuer_result.get('error', 'Unknown')}")

        time.sleep(0.2)

        # 持有者 DID
        current += 1
        print(f"[{current}/{total}] 持有者 - 种子: {seed}", end=" ")
        holder_result = create_and_publish_did(HOLDER_URL, seed)

        if holder_result['success']:
            print(f"✅ {holder_result['did']}")
            # 添加到列表（只保留必要字段）
            did_list.append({
                "seed": seed,
                "did": holder_result['did'],
                "verkey": holder_result['verkey'],
                "role": "holder"
            })
        else:
            print(f"❌ {holder_result.get('error', 'Unknown')}")

        time.sleep(0.2)

    # 统计
    admin_count = len(ADMIN_DIDS)
    issuer_count = len([d for d in did_list if d['role'] == 'issuer'])
    holder_count = len([d for d in did_list if d['role'] == 'holder'])
    total_count = len(did_list)

    print("\n" + "=" * 60)
    print("📊 生成完成")
    print("=" * 60)
    print(f"管理员DID: {admin_count}个")
    print(f"发行者DID: {issuer_count}个")
    print(f"持有者DID: {holder_count}个")
    print(f"总计DID: {total_count}个")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 确保config目录存在
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    # 保存结果到config/did.json
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(did_list, f, indent=2, ensure_ascii=False)
    print(f"\n💾 结果已保存到: {OUTPUT_FILE}")

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
    main()
