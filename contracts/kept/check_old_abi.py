#!/usr/bin/env python3
"""检查旧版本 ABI 与当前版本 ABI 的差异"""

import json
import os
from pathlib import Path

def load_abi(file_path):
    """加载 ABI 文件"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        return None

def get_abi_hash(abi):
    """获取 ABI 的哈希值"""
    if abi is None:
        return None
    import hashlib
    return hashlib.md5(json.dumps(abi, sort_keys=True).encode()).hexdigest()[:8]

def get_function_names(abi):
    """获取 ABI 中的所有函数名"""
    if abi is None:
        return set()
    return set(item.get('name', '') for item in abi if item.get('type') == 'function')

def main():
    base_dir = Path("/home/manifold/cursor/cross-chain/contracts/kept")
    build_dir = base_dir / "build"
    old_dir = base_dir / "useless" / "build_commodity"

    print("=" * 80)
    print("旧版本 ABI 与当前版本对比检查")
    print("=" * 80)
    print()

    # 检查 old 目录中的每个 .abi 文件
    old_abi_files = list(old_dir.glob("*.abi"))

    for old_abi_path in old_abi_files:
        contract_name = old_abi_path.stem  # 去掉 .abi 后缀
        print(f"检查合约: {contract_name}")
        print("-" * 40)

        # 加载旧版本 ABI
        old_abi = load_abi(str(old_abi_path))
        old_hash = get_abi_hash(old_abi)
        old_functions = get_function_names(old_abi)

        # 查找当前版本对应的 ABI 文件
        current_abi_path = None
        possible_paths = [
            build_dir / f"{contract_name}.abi",
            build_dir / f"{contract_name}Simple.abi",  # 处理 VCCrossChainBridge 的情况
        ]

        for path in possible_paths:
            if path.exists():
                current_abi_path = path
                break

        if current_abi_path is None:
            print(f"  当前版本: ✗ 文件不存在")
            print(f"  旧版本 hash: {old_hash}")
            print(f"  旧版本函数数量: {len(old_functions)}")
            print()

        else:
            # 加载当前版本 ABI
            current_abi = load_abi(str(current_abi_path))
            current_hash = get_abi_hash(current_abi)
            current_functions = get_function_names(current_abi)

            print(f"  当前版本: {current_abi_path.name} (hash: {current_hash})")
            print(f"  旧版本: {old_abi_path.name} (hash: {old_hash})")

            if old_hash == current_hash:
                print(f"  状态: ✅ 一致")
            else:
                print(f"  状态: ❌ 不一致!")
                print(f"    当前版本函数数量: {len(current_functions)}")
                print(f"    旧版本函数数量: {len(old_functions)}")

                # 检查函数差异
                only_in_current = current_functions - old_functions
                only_in_old = old_functions - current_functions

                if only_in_current:
                    print(f"    仅在当前版本中: {only_in_current}")
                if only_in_old:
                    print(f"    仅在旧版本中: {only_in_old}")

                # 如果函数名相同但内容不同
                if current_functions == old_functions:
                    print(f"    函数名相同，但函数签名或其他属性有差异")

            print()

    print("=" * 80)
    print("总结")
    print("=" * 80)
    print("useless/build_commodity/ 目录包含旧版本的 ABI 文件")
    print("如果与当前版本不一致，建议删除该目录以避免混淆")

if __name__ == "__main__":
    main()
