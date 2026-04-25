#!/usr/bin/env python3
"""
生成50个DID并注册到Indy区块链（使用种子确定性生成）
种子范围: 000000000000000000000000002Agent 到 000000000000000000000000051Agent
"""

import requests
import json
import time
import nacl.signing
import nacl.encoding
import base58

# ACA-Py Admin API 配置
ADMIN_URL = "http://localhost:8080"

def seed_to_keypair(seed):
    """
    从种子生成 Ed25519 密钥对（Indy SDK 兼容）
    返回: (verkey, did)
    """
    # 种子必须是32字节
    if len(seed) > 32:
        seed = seed[:32]
    elif len(seed) < 32:
        seed = seed.ljust(32, b'\0' if isinstance(seed, bytes) else '0')

    # 转换为字节
    if isinstance(seed, str):
        seed_bytes = seed.encode('utf-8')
    else:
        seed_bytes = seed

    # 确保是32字节
    seed_bytes = seed_bytes[:32].ljust(32, b'\0')

    # 使用 PyNaCl 生成 Ed25519 密钥对
    # Indy SDK 使用特定的密钥派生方法
    # 这里使用简化的方法：直接用 seed 作为 SigningKey 的种子
    try:
        # 尝试从种子生成密钥对
        signing_key = nacl.signing.SigningKey(seed_bytes)

        # 获取验证密钥（公钥）
        verify_key_bytes = signing_key.verify_key.encode()

        # Indy verkey 是 base58 编码的 32 字节公钥
        verkey = base58.b58encode(verify_key_bytes).decode('ascii')

        # Indy DID 是 verkey 的前 16 字节的 base58 编码
        did_bytes = verify_key_bytes[:16]
        did = base58.b58encode(did_bytes).decode('ascii')

        return did, verkey
    except Exception as e:
        print(f"  错误: {e}")
        return None, None

def register_nym_to_ledger(did, verkey, role=None):
    """将DID注册到Indy区块链（不需要在钱包中创建）"""
    url = f"{ADMIN_URL}/ledger/register-nym"
    params = {
        "did": did,
        "verkey": verkey,
        "role": role
    }

    response = requests.post(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"  注册NYM失败: {response.status_code} - {response.text}")
        return None

def generate_seeds():
    """生成50个种子，从002Agent到051Agent"""
    seeds = []
    for i in range(2, 52):  # 2 到 51 (共50个)
        # 24个固定零 + 3位数字 + Agent = 32位
        seed = "000000000000000000000000" + f"{i:03d}" + "Agent"
        seeds.append(seed)
    return seeds

def main():
    print("=" * 60)
    print("开始生成50个DID并注册到Indy区块链")
    print("使用种子确定性生成（Indy SDK 兼容）")
    print("=" * 60)

    seeds = generate_seeds()
    results = []

    for idx, seed in enumerate(seeds, 1):
        print(f"\n[{idx}/50] 处理种子: {seed}")

        # 从种子确定性生成 DID 和 Verkey
        print(f"  从种子生成密钥对...")
        did, verkey = seed_to_keypair(seed)

        if not did or not verkey:
            print(f"  生成失败，跳过种子 {seed}")
            continue

        print(f"  DID: {did}")
        print(f"  Verkey: {verkey}")

        # 注册到Indy区块链
        print(f"  注册到区块链...")
        nym_result = register_nym_to_ledger(did, verkey)

        if nym_result:
            print(f"  ✓ 注册成功")
        else:
            print(f"  ✗ 注册失败")

        # 保存结果
        results.append({
            "index": idx,
            "seed": seed,
            "did": did,
            "verkey": verkey,
            "registered": nym_result is not None
        })

        # 短暂延迟
        time.sleep(0.5)

    # 保存到JSON文件
    output_file = "config/did.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 60)
    print(f"完成！共处理 {len(results)} 个DID")
    print(f"结果已保存到: {output_file}")
    print("=" * 60)

    # 统计
    registered_count = sum(1 for r in results if r["registered"])
    print(f"\n统计:")
    print(f"  总数: {len(results)}")
    print(f"  成功注册到区块链: {registered_count}")
    print(f"  注册失败: {len(results) - registered_count}")

if __name__ == "__main__":
    main()
