#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成DID-Address映射配置文件
从config/did.json和config/address.json读取数据
生成config/did_address_map.json
每个地址分配一个DID（一一映射）
"""

import json
import os
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, List

def load_json_file(filepath: str) -> Any:
    """加载JSON文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 加载文件失败 {filepath}: {e}")
        return None

def save_json_file(data: Any, filepath: str) -> bool:
    """保存JSON文件"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ 保存文件失败 {filepath}: {e}")
        return False

def create_mapping(index: int, did_info: Dict, address: str,
                   address_type: str, address_label: str,
                   role: str, description: str) -> Dict:
    """创建单个映射条目"""
    return {
        "index": index,
        "did": did_info["did"],
        "verkey": did_info["verkey"],
        "role": role,
        "address": address,
        "address_type": address_type,
        "address_label": address_label,
        "verified": did_info.get("registered", True),
        "description": description,
        "seed": did_info["seed"]
    }

def collect_addresses_to_map(address_config: Dict) -> List[Dict]:
    """收集所有需要映射的地址"""
    addresses = []

    # 1. User Accounts
    print("   📁 User Accounts...")
    user_accounts = address_config.get('user_accounts', {}).get('accounts', [])
    for acc in user_accounts:
        addresses.append({
            "address": acc["address"],
            "address_type": "user_account",
            "address_label": f"User Account {acc['index']:03d}",
            "role": "user",
            "description": f"用户账户 {acc['index']} 的DID映射"
        })
    print(f"     ✅ 添加: {len(user_accounts)} 个")

    # 2. Chain A Contracts
    print("   📁 Chain A Contracts...")
    chain_a = address_config.get('contracts', {}).get('chain_a', {})

    # 直接合约
    direct_contracts = ['did_verifier', 'cross_chain_bridge', 'contract_manager']
    for contract_name in direct_contracts:
        if contract_name in chain_a and isinstance(chain_a[contract_name], str):
            addresses.append({
                "address": chain_a[contract_name],
                "address_type": "contract_chain_a",
                "address_label": f"Chain A {contract_name.replace('_', ' ').title()}",
                "role": "contract",
                "description": f"Chain A {contract_name} 合约的DID映射"
            })
    print(f"     ✅ 直接合约: {len([c for c in direct_contracts if c in chain_a])} 个")

    # VC Managers
    if 'vc_managers' in chain_a:
        vc_managers = chain_a['vc_managers']
        for vc_name, vc_address in vc_managers.items():
            addresses.append({
                "address": vc_address,
                "address_type": "vc_manager_chain_a",
                "address_label": f"VC Manager {vc_name.replace('_', ' ').title()}",
                "role": "contract",
                "description": f"Chain A {vc_name} VC Manager 合约的DID映射"
            })
        print(f"     ✅ VC Managers: {len(vc_managers)} 个")

    # 3. Chain B Contracts
    print("   📁 Chain B Contracts...")
    chain_b = address_config.get('contracts', {}).get('chain_b', {})
    chain_b_count = 0
    for contract_name, contract_address in chain_b.items():
        if isinstance(contract_address, str):
            addresses.append({
                "address": contract_address,
                "address_type": "contract_chain_b",
                "address_label": f"Chain B {contract_name.replace('_', ' ').title()}",
                "role": "contract",
                "description": f"Chain B {contract_name} 合约的DID映射"
            })
            chain_b_count += 1
    print(f"     ✅ 添加: {chain_b_count} 个")

    return addresses

def generate_did_address_map():
    """生成DID-Address映射配置"""

    print("📋 生成DID-Address映射配置")
    print("=" * 60)

    # 1. 加载源文件
    print("\n1️⃣ 加载源文件...")
    did_list = load_json_file("config/did.json")
    if not did_list:
        print("❌ 无法加载config/did.json")
        return None

    address_config = load_json_file("config/address.json")
    if not address_config:
        print("❌ 无法加载config/address.json")
        return None

    print(f"   ✅ DID 数量: {len(did_list)}")
    print(f"   ✅ 源文件: did.json, address.json")

    # 2. 收集需要映射的地址
    print("\n2️⃣ 收集需要映射的地址...")
    addresses_to_map = collect_addresses_to_map(address_config)
    total_addresses = len(addresses_to_map)
    print(f"\n   📊 总计需要映射: {total_addresses} 个地址")

    # 检查DID数量是否足够
    if len(did_list) < total_addresses:
        print(f"❌ DID数量不足！需要 {total_addresses} 个，只有 {len(did_list)} 个")
        return None

    # 3. 创建映射
    print(f"\n3️⃣ 创建映射关系...")
    print(f"   使用 did.json[0:{total_addresses}]")

    mappings = []
    for i, addr_info in enumerate(addresses_to_map):
        did_info = did_list[i]
        mapping = create_mapping(
            index=i + 1,
            did_info=did_info,
            address=addr_info["address"],
            address_type=addr_info["address_type"],
            address_label=addr_info["address_label"],
            role=addr_info["role"],
            description=addr_info["description"]
        )
        mappings.append(mapping)

    print(f"   ✅ 创建映射: {len(mappings)} 条")

    # 4. 生成统计信息
    print(f"\n4️⃣ 生成统计信息...")

    by_role = defaultdict(int)
    by_address_type = defaultdict(int)
    verified_count = 0

    for m in mappings:
        by_role[m["role"]] += 1
        by_address_type[m["address_type"]] += 1
        if m["verified"]:
            verified_count += 1

    summary = {
        "total_mappings": len(mappings),
        "verified_mappings": verified_count,
        "by_role": dict(by_role),
        "by_address_type": dict(by_address_type),
        "unique_addresses": total_addresses
    }

    # 5. 生成索引
    print(f"5️⃣ 生成索引...")

    indexes = {
        "by_did": {m["did"]: m["index"] for m in mappings},
        "by_address": {},
        "by_role": defaultdict(list)
    }

    # by_address 索引
    for m in mappings:
        addr = m["address"]
        if addr not in indexes["by_address"]:
            indexes["by_address"][addr] = []
        indexes["by_address"][addr].append(m["index"])

    # by_role 索引
    for m in mappings:
        indexes["by_role"][m["role"]].append(m["index"])

    # 转换 defaultdict 为普通 dict
    indexes["by_role"] = dict(indexes["by_role"])

    # 6. 构建最终数据结构
    print(f"\n6️⃣ 构建最终数据结构...")

    result = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "description": "DID-Address映射配置文件 - 用于CrossChainDIDVerifier合约",
            "version": "2.0",
            "generator": "generate_did_address_map.py",
            "source_files": ["did.json", "address.json"]
        },
        "mappings": mappings,
        "summary": summary,
        "indexes": indexes
    }

    # 7. 保存文件
    print(f"\n7️⃣ 保存文件...")
    os.makedirs("config", exist_ok=True)
    output_file = "config/did_address_map.json"

    if not save_json_file(result, output_file):
        return None

    print(f"   ✅ 已保存: {output_file}")

    # 8. 显示结果
    print(f"\n{'=' * 60}")
    print(f"✅ 完成！映射文件已生成")
    print(f"{'=' * 60}")

    print(f"\n📊 统计信息:")
    print(f"  总映射数: {summary['total_mappings']}")
    print(f"  已验证: {summary['verified_mappings']}")
    print(f"\n  按角色分类:")
    for role, count in summary['by_role'].items():
        print(f"    - {role}: {count}")
    print(f"\n  按地址类型分类:")
    for addr_type, count in summary['by_address_type'].items():
        print(f"    - {addr_type}: {count}")

    # 显示前3个映射示例
    print(f"\n前3个映射示例:")
    for m in mappings[:3]:
        print(f"  [{m['index']}] {m['did']} -> {m['address'][:20]}... ({m['address_type']})")

    return output_file

def main():
    """主函数"""
    print("🔐 DID-Address映射配置生成器 v2.0")
    print("=" * 60)
    print("📌 功能: 为每个用户账户和合约地址分配一个DID")
    print("📌 输入: config/did.json, config/address.json")
    print("📌 输出: config/did_address_map.json")
    print("=" * 60)

    output_file = generate_did_address_map()

    if output_file:
        print("\n🎉 配置生成成功!")
        print(f"📁 输出文件: {output_file}")
        print(f"\n该配置文件可用于:")
        print(f"   1. 部署CrossChainDIDVerifier合约时注册DID-Address映射")
        print(f"   2. Oracle服务验证用户身份")
        print(f"   3. Web应用查询DID对应的以太坊地址")
    else:
        print("\n❌ 配置生成失败")

if __name__ == "__main__":
    main()
