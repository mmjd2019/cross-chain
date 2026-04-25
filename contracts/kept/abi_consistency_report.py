#!/usr/bin/env python3
"""生成完整的 ABI 一致性报告"""

import json
import os
from pathlib import Path
from datetime import datetime

def load_abi(file_path):
    """加载 ABI 文件"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict) and 'abi' in data:
                return data['abi']
            elif isinstance(data, list):
                return data
            return None
    except Exception as e:
        return None

def get_abi_hash(abi):
    """获取 ABI 的哈希值"""
    if abi is None:
        return "N/A"
    import hashlib
    return hashlib.md5(json.dumps(abi, sort_keys=True).encode()).hexdigest()[:8]

def get_function_names(abi):
    """获取 ABI 中的所有函数名"""
    if abi is None:
        return set()
    return sorted([item.get('name', '') for item in abi if item.get('type') == 'function'])

def get_file_size(file_path):
    """获取文件大小"""
    if os.path.exists(file_path):
        return os.path.getsize(file_path)
    return 0

def main():
    base_dir = Path("/home/manifold/cursor/cross-chain/contracts/kept")
    build_dir = base_dir / "build"
    contract_abis_dir = base_dir / "contract_abis"
    old_dir = base_dir / "useless" / "build_commodity"

    report = []
    report.append("=" * 100)
    report.append("智能合约 ABI 一致性检查报告")
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 100)
    report.append("")

    # 所有合约
    all_contracts = [
        "DIDVerifier",
        "ContractManager",
        "VCCrossChainBridgeSimple",
        "VCCrossChainBridge",
        "InspectionReportVCManager",
        "InsuranceContractVCManager",
        "CertificateOfOriginVCManager",
        "BillOfLadingVCManager",
    ]

    # 结果统计
    stats = {
        "完全一致": [],
        "部分一致": [],
        "不一致": [],
        "缺失": [],
    }

    for contract in all_contracts:
        report.append(f"合约: {contract}")
        report.append("-" * 80)

        # 检查三个位置的文件
        build_abi_path = build_dir / f"{contract}.abi"
        contract_abis_path = contract_abis_dir / f"{contract}.json"
        old_abi_path = old_dir / f"{contract}.abi"

        build_exists = build_abi_path.exists()
        contract_abis_exists = contract_abis_path.exists()
        old_exists = old_abi_path.exists()

        # 加载 ABI
        build_abi = load_abi(str(build_abi_path)) if build_exists else None
        contract_abis_abi = load_abi(str(contract_abis_path)) if contract_abis_exists else None
        old_abi = load_abi(str(old_abi_path)) if old_exists else None

        # 获取哈希
        build_hash = get_abi_hash(build_abi)
        contract_abis_hash = get_abi_hash(contract_abis_abi)
        old_hash = get_abi_hash(old_abi)

        # 获取函数列表
        build_funcs = get_function_names(build_abi) if build_abi else []
        contract_abis_funcs = get_function_names(contract_abis_abi) if contract_abis_abi else []
        old_funcs = get_function_names(old_abi) if old_abi else []

        # 显示信息
        report.append(f"位置                  | 状态      | 大量      | Hash       | 函数数")
        report.append(f"---------------------|-----------|-----------|------------|--------")

        if build_exists:
            report.append(f"build/               | ✓         | {get_file_size(build_abi_path):6d}   | {build_hash}   | {len(build_funcs):3d}")
        else:
            report.append(f"build/               | ✗         |     N/A   | N/A        |   N/A")

        if contract_abis_exists:
            report.append(f"contract_abis/       | ✓         | {get_file_size(contract_abis_path):6d}   | {contract_abis_hash}   | {len(contract_abis_funcs):3d}")
        else:
            report.append(f"contract_abis/       | ✗         |     N/A   | N/A        |   N/A")

        if old_exists:
            report.append(f"useless/old/         | ⚠         | {get_file_size(old_abi_path):6d}   | {old_hash}   | {len(old_funcs):3d}")
        else:
            report.append(f"useless/old/         | ✗         |     N/A   | N/A        |   N/A")

        report.append("")

        # 检查一致性
        issues = []

        if build_exists and contract_abis_exists:
            if build_hash == contract_abis_hash:
                report.append(f"✅ build/ 和 contract_abis/ 一致")
            else:
                report.append(f"❌ build/ 和 contract_abis/ 不一致!")
                issues.append("build与contract_abis不一致")

        if old_exists:
            if build_exists:
                if old_hash == build_hash:
                    report.append(f"✅ useless/old/ 与 build/ 一致 (可删除)")
                else:
                    report.append(f"⚠️  useless/old/ 与 build/ 不一致")
                    issues.append("old版本与build不一致")
            if contract_abis_exists:
                if old_hash == contract_abis_hash:
                    report.append(f"✅ useless/old/ 与 contract_abis/ 一致 (可删除)")
                else:
                    report.append(f"⚠️  useless/old/ 与 contract_abis/ 不一致")
                    issues.append("old版本与contract_abis不一致")

        # 特殊情况：ContractManager
        if contract == "ContractManager":
            if not build_exists and contract_abis_exists:
                report.append(f"⚠️  ContractManager 未重新编译，只有已部署版本")
                issues.append("未重新编译")

        # 特殊情况：VCCrossChainBridge vs VCCrossChainBridgeSimple
        if contract == "VCCrossChainBridge":
            report.append(f"⚠️  注意: VCCrossChainBridge 是旧版本，当前使用 VCCrossChainBridgeSimple")
            issues.append("已替换为新版本")

        if issues:
            stats["不一致"].append((contract, issues))
        elif build_exists and contract_abis_exists:
            stats["完全一致"].append(contract)
        elif not build_exists and not contract_abis_exists:
            stats["缺失"].append(contract)
        else:
            stats["部分一致"].append(contract)

        report.append("")

    # 总结
    report.append("=" * 100)
    report.append("总结")
    report.append("=" * 100)
    report.append(f"完全一致: {len(stats['完全一致'])} 个")
    report.append(f"部分一致: {len(stats['部分一致'])} 个")
    report.append(f"不一致/需要注意: {len(stats['不一致'])} 个")
    report.append(f"缺失: {len(stats['缺失'])} 个")
    report.append("")

    if stats['完全一致']:
        report.append("✅ 完全一致的合约:")
        for contract in stats['完全一致']:
            report.append(f"   - {contract}")
        report.append("")

    if stats['部分一致']:
        report.append("⚠️  部分一致的合约:")
        for contract in stats['部分一致']:
            report.append(f"   - {contract}")
        report.append("")

    if stats['不一致']:
        report.append("❌ 不一致/需要注意的合约:")
        for contract, issues in stats['不一致']:
            report.append(f"   - {contract}: {', '.join(issues)}")
        report.append("")

    # 建议
    report.append("=" * 100)
    report.append("建议")
    report.append("=" * 100)
    report.append("1. build/ 目录是最新的编译结果，应该作为权威来源")
    report.append("2. contract_abis/ 目录用于备份和参考，应该与 build/ 保持一致")
    report.append("3. useless/build_commodity/ 目录是旧版本，建议删除以避免混淆")
    report.append("4. ContractManager 合约未重新编译，如需要请重新编译")
    report.append("5. VCCrossChainBridge 已被 VCCrossChainBridgeSimple 替代")

    # 输出报告
    report_text = "\n".join(report)
    print(report_text)

    # 保存报告到文件
    report_file = base_dir / "abi_consistency_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_text)
    print(f"\n报告已保存到: {report_file}")

if __name__ == "__main__":
    main()
