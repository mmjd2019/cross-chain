#!/usr/bin/env python3
"""检查不同位置的 ABI 文件是否一致"""

import json
import os
from pathlib import Path

# 合约名称映射
CONTRACT_MAPPING = {
    "DIDVerifier": "DIDVerifier",
    "VCCrossChainBridgeSimple": "VCCrossChainBridgeSimple",
    "InspectionReportVCManager": "InspectionReportVCManager",
    "InsuranceContractVCManager": "InsuranceContractVCManager",
    "CertificateOfOriginVCManager": "CertificateOfOriginVCManager",
    "BillOfLadingVCManager": "BillOfLadingVCManager",
}

def load_abi(file_path):
    """加载 ABI 文件"""
    try:
        if file_path.endswith('.json'):
            with open(file_path, 'r') as f:
                data = json.load(f)
                # 有些 JSON 可能包含 abi 字段，有些直接是 abi 数组
                if isinstance(data, dict) and 'abi' in data:
                    return data['abi']
                elif isinstance(data, list):
                    return data
                else:
                    return None
        else:  # .abi 文件
            with open(file_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"  错误: {e}")
        return None

def compare_abi(abi1, abi2):
    """比较两个 ABI 是否一致"""
    if abi1 is None or abi2 is None:
        return False
    return json.dumps(abi1, sort_keys=True) == json.dumps(abi2, sort_keys=True)

def get_abi_hash(abi):
    """获取 ABI 的哈希值用于快速比较"""
    if abi is None:
        return None
    import hashlib
    return hashlib.md5(json.dumps(abi, sort_keys=True).encode()).hexdigest()[:8]

def main():
    base_dir = Path("/home/manifold/cursor/cross-chain/contracts/kept")
    build_dir = base_dir / "build"
    contract_abis_dir = base_dir / "contract_abis"

    print("=" * 80)
    print("ABI 文件一致性检查")
    print("=" * 80)
    print()

    # 存储结果
    results = {}
    mismatches = []

    for contract, file_base in CONTRACT_MAPPING.items():
        print(f"检查合约: {contract}")
        print("-" * 40)

        # 在 build 目录中查找对应的 .abi 文件
        build_abi_path = build_dir / f"{contract}.abi"
        build_abi = None
        build_hash = None

        if build_abi_path.exists():
            build_abi = load_abi(str(build_abi_path))
            build_hash = get_abi_hash(build_abi)
            print(f"  build/{contract}.abi: ✓ (hash: {build_hash})")
        else:
            print(f"  build/{contract}.abi: ✗ 文件不存在")

        # 在 contract_abis 目录中查找对应的 .json 文件
        contract_abis_path = contract_abis_dir / f"{contract}.json"
        contract_abis_abi = None
        contract_abis_hash = None

        if contract_abis_path.exists():
            contract_abis_abi = load_abi(str(contract_abis_path))
            contract_abis_hash = get_abi_hash(contract_abis_abi)
            print(f"  contract_abis/{contract}.json: ✓ (hash: {contract_abis_hash})")
        else:
            print(f"  contract_abis/{contract}.json: ✗ 文件不存在")

        # 检查一致性
        if build_abi and contract_abis_abi:
            if compare_abi(build_abi, contract_abis_abi):
                print(f"  状态: ✅ 一致")
                results[contract] = "一致"
            else:
                print(f"  状态: ❌ 不一致!")
                results[contract] = "不一致"
                mismatches.append(contract)
                # 显示差异详情
                print(f"    build/ ABI 函数数量: {len(build_abi)}")
                print(f"    contract_abis/ ABI 函数数量: {len(contract_abis_abi)}")

                # 检查函数名差异
                build_functions = set(item.get('name', '') for item in build_abi if item.get('type') == 'function')
                contract_abis_functions = set(item.get('name', '') for item in contract_abis_abi if item.get('type') == 'function')

                if build_functions != contract_abis_functions:
                    only_in_build = build_functions - contract_abis_functions
                    only_in_contract_abis = contract_abis_functions - build_functions
                    if only_in_build:
                        print(f"    仅在 build/ 中: {only_in_build}")
                    if only_in_contract_abis:
                        print(f"    仅在 contract_abis/ 中: {only_in_contract_abis}")
        elif build_abi is None and contract_abis_abi is None:
            print(f"  状态: ⚠️ 两个位置都不存在")
            results[contract] = "不存在"
        else:
            print(f"  状态: ⚠️ 只有一个位置存在")
            results[contract] = "部分存在"

        print()

    # 总结
    print("=" * 80)
    print("总结")
    print("=" * 80)
    print(f"总共检查: {len(CONTRACT_MAPPING)} 个合约")
    print(f"一致: {sum(1 for v in results.values() if v == '一致')} 个")
    print(f"不一致: {len(mismatches)} 个")
    print(f"其他: {sum(1 for v in results.values() if v not in ['一致', '不一致'])} 个")

    if mismatches:
        print()
        print("⚠️ 发现不一致的合约:")
        for contract in mismatches:
            print(f"  - {contract}")
        return 1
    else:
        print()
        print("✅ 所有 ABI 文件都是一致的!")
        return 0

if __name__ == "__main__":
    exit(main())
