#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大宗货物跨境交易智能合约编译脚本
使用py-solc-x编译器（Solidity 0.5.16）
"""

import os
import json
import sys
from pathlib import Path

try:
    from solcx import compile_source, install_solc, set_solc_version
    from solcx import get_solc_version, set_solc_binary_path
except ImportError:
    print("❌ 未安装 py-solc-x")
    print("请运行: pip install py-solc-x")
    sys.exit(1)


class CommodityContractCompiler:
    def __init__(self, solc_version="0.5.16"):
        """初始化编译器"""
        self.solc_version = solc_version
        self.contracts_dir = Path(__file__).parent
        self.build_dir = self.contracts_dir / "build_commodity"
        self.build_dir.mkdir(exist_ok=True)

        # 新生成的合约列表（8个）
        self.contract_files = [
            "DIDVerifier.sol",
            "ContractManager.sol",
            "InspectionReportVCManager.sol",
            "InsuranceContractVCManager.sol",
            "CertificateOfOriginVCManager.sol",
            "BillOfLadingVCManager.sol",
            "VCCrossChainBridge.sol",
            "VCVerifier.sol"
        ]

    def setup_solc(self):
        """设置Solidity编译器版本"""
        print(f"🔧 设置Solidity编译器版本 {self.solc_version}...")

        try:
            # 尝试设置已安装的版本
            set_solc_version(self.solc_version)
            version = get_solc_version()
            print(f"✅ 使用已安装的Solidity版本: {version}")
            return True
        except Exception:
            # 如果未安装，则下载安装
            print(f"📥 下载并安装Solidity {self.solc_version}...")
            try:
                install_solc(self.solc_version)
                set_solc_version(self.solc_version)
                version = get_solc_version()
                print(f"✅ Solidity {version} 安装成功")
                return True
            except Exception as e:
                print(f"❌ 安装Solidity失败: {e}")
                return False

    def read_contract_file(self, contract_file):
        """读取合约文件内容"""
        contract_path = self.contracts_dir / contract_file

        if not contract_path.exists():
            print(f"❌ 合约文件不存在: {contract_file}")
            return None

        try:
            with open(contract_path, 'r', encoding='utf-8') as f:
                content = f.read()
            print(f"📄 读取合约文件: {contract_file} ({len(content)} 字节)")
            return content
        except Exception as e:
            print(f"❌ 读取文件失败 {contract_file}: {e}")
            return None

    def compile_contract(self, contract_file, source_code):
        """编译单个合约"""
        print(f"🔨 编译 {contract_file}...")

        try:
            # 编译合约
            compiled_sol = compile_source(
                source_code,
                output_values=['abi', 'bin'],
                solc_version=self.solc_version,
                optimize=True,
                optimize_runs=200
            )

            # 提取合约ID和接口
            contract_id = None
            for key in compiled_sol.keys():
                if '<stdin>:' in key:
                    contract_id = key
                    break

            if contract_id is None:
                print(f"❌ {contract_file} 编译失败: 未找到合约")
                return None

            contract_interface = compiled_sol[contract_id]

            # 验证字节码
            if not contract_interface.get('bin'):
                print(f"❌ {contract_file} 编译失败: 未生成字节码")
                return None

            print(f"✅ {contract_file} 编译成功")
            print(f"   - 字节码长度: {len(contract_interface['bin'])} 字符")
            print(f"   - ABI函数数量: {len(contract_interface['abi'])}")

            return contract_interface

        except Exception as e:
            print(f"❌ 编译 {contract_file} 失败: {e}")
            return None

    def save_contract_artifact(self, contract_file, contract_interface):
        """保存合约编译产物"""
        contract_name = contract_file.replace('.sol', '')

        # 保存ABI
        abi_file = self.build_dir / f"{contract_name}.abi"
        with open(abi_file, 'w', encoding='utf-8') as f:
            json.dump(contract_interface['abi'], f, indent=2, ensure_ascii=False)
        print(f"   ✅ 保存ABI: {abi_file}")

        # 保存字节码
        bin_file = self.build_dir / f"{contract_name}.bin"
        with open(bin_file, 'w', encoding='utf-8') as f:
            f.write(contract_interface['bin'])
        print(f"   ✅ 保存字节码: {bin_file}")

        # 保存完整的JSON产物
        artifact = {
            "contractName": contract_name,
            "abi": contract_interface['abi'],
            "bytecode": contract_interface['bin'],
            "deployedBytecode": contract_interface['bin'],
            "compiler": {
                "name": "solc",
                "version": self.solc_version
            },
            "networks": {},
            "schemaVersion": "3.4.7",
            "updatedAt": self.get_current_timestamp()
        }

        json_file = self.contracts_dir / f"{contract_name}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(artifact, f, indent=2, ensure_ascii=False)
        print(f"   ✅ 保存JSON产物: {json_file}")

    def get_current_timestamp(self):
        """获取当前时间戳"""
        import datetime
        return datetime.datetime.now().isoformat()

    def compile_all(self):
        """编译所有合约"""
        print("=" * 60)
        print("🔨 大宗货物跨境交易智能合约编译工具")
        print("=" * 60)
        print()

        # 1. 设置Solidity编译器
        if not self.setup_solc():
            return False

        print()
        print("=" * 60)
        print("📋 开始编译合约...")
        print("=" * 60)
        print()

        # 2. 编译每个合约
        success_count = 0
        failed_contracts = []

        for contract_file in self.contract_files:
            # 读取合约文件
            source_code = self.read_contract_file(contract_file)
            if source_code is None:
                failed_contracts.append(contract_file)
                continue

            # 编译合约
            contract_interface = self.compile_contract(contract_file, source_code)
            if contract_interface is None:
                failed_contracts.append(contract_file)
                continue

            # 保存编译产物
            self.save_contract_artifact(contract_file, contract_interface)

            success_count += 1
            print()

        # 3. 输出编译结果
        print("=" * 60)
        print("📊 编译结果统计")
        print("=" * 60)
        print(f"总计: {len(self.contract_files)} 个合约")
        print(f"✅ 成功: {success_count} 个")
        print(f"❌ 失败: {len(failed_contracts)} 个")

        if failed_contracts:
            print()
            print("失败的合约:")
            for contract in failed_contracts:
                print(f"  - {contract}")

        print()

        if success_count == len(self.contract_files):
            print("🎉 所有合约编译成功！")
            print(f"📁 编译产物保存在: {self.build_dir}")
            print(f"📄 JSON产物保存在合约目录")
            return True
        else:
            print("❌ 部分合约编译失败")
            return False

    def clean_build(self):
        """清理编译产物"""
        print("🧹 清理编译产物...")

        # 清理build目录
        if self.build_dir.exists():
            import shutil
            shutil.rmtree(self.build_dir)
            print(f"✅ 清理 build 目录: {self.build_dir}")

        # 清理JSON文件
        for contract_file in self.contract_files:
            contract_name = contract_file.replace('.sol', '')
            json_file = self.contracts_dir / f"{contract_name}.json"
            if json_file.exists():
                json_file.unlink()
                print(f"✅ 删除 {json_file.name}")

    def list_contracts(self):
        """列出所有合约文件"""
        print("📋 大宗货物跨境交易智能合约列表")
        print("-" * 60)

        for i, contract_file in enumerate(self.contract_files, 1):
            contract_path = self.contracts_dir / contract_file
            if contract_path.exists():
                size = contract_path.stat().st_size
                print(f"{i:2d}. ✅ {contract_file:40s} ({size:,} 字节)")
            else:
                print(f"{i:2d}. ❌ {contract_file:40s} (不存在)")


def main():
    """主函数"""
    compiler = CommodityContractCompiler(solc_version="0.5.16")

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "clean":
            compiler.clean_build()
        elif command == "list":
            compiler.list_contracts()
        elif command == "compile":
            compiler.compile_all()
        else:
            print("❌ 未知命令")
            print("可用命令: compile, clean, list")
    else:
        # 默认编译
        success = compiler.compile_all()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
