#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCCrossChainBridge合约编译脚本
使用py-solc-x编译器（Solidity 0.5.16）
"""

import os
import json
import sys
from pathlib import Path

try:
    from solcx import compile_source, install_solc, set_solc_version
    from solcx import get_solc_version
except ImportError:
    print("❌ 未安装 py-solc-x")
    print("请运行: pip3 install py-solc-x")
    sys.exit(1)


class VCBridgeCompiler:
    def __init__(self, solc_version="0.5.16"):
        """初始化编译器"""
        self.solc_version = solc_version
        self.contracts_dir = Path(__file__).parent
        self.contract_file = "VCCrossChainBridge.sol"

    def setup_solc(self):
        """设置Solidity编译器版本"""
        print(f"🔧 设置Solidity编译器版本 {self.solc_version}...")

        try:
            set_solc_version(self.solc_version)
            version = get_solc_version()
            print(f"✅ 使用已安装的Solidity版本: {version}")
            return True
        except Exception:
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

    def read_contract_file(self):
        """读取合约文件内容"""
        contract_path = self.contracts_dir / self.contract_file

        if not contract_path.exists():
            print(f"❌ 合约文件不存在: {contract_path}")
            return None

        try:
            with open(contract_path, 'r', encoding='utf-8') as f:
                content = f.read()
            print(f"📄 读取合约文件: {self.contract_file} ({len(content)} 字节)")
            return content
        except Exception as e:
            print(f"❌ 读取文件失败 {self.contract_file}: {e}")
            return None

    def compile_contract(self, source_code):
        """编译合约"""
        print(f"🔨 编译 {self.contract_file}...")

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
                print(f"❌ {self.contract_file} 编译失败: 未找到合约")
                return None

            contract_interface = compiled_sol[contract_id]

            # 验证字节码
            if not contract_interface.get('bin'):
                print(f"❌ {self.contract_file} 编译失败: 未生成字节码")
                return None

            print(f"✅ {self.contract_file} 编译成功")
            print(f"   - 字节码长度: {len(contract_interface['bin'])} 字符")
            print(f"   - ABI函数数量: {len(contract_interface['abi'])}")

            return contract_interface

        except Exception as e:
            print(f"❌ 编译失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def save_contract_artifact(self, contract_interface):
        """保存合约编译产物"""
        contract_name = self.contract_file.replace('.sol', '')

        # 保存ABI
        abi_file = self.contracts_dir / f"{contract_name}.abi"
        with open(abi_file, 'w', encoding='utf-8') as f:
            json.dump(contract_interface['abi'], f, indent=2, ensure_ascii=False)
        print(f"   ✅ 保存ABI: {abi_file}")

        # 保存字节码
        bin_file = self.contracts_dir / f"{contract_name}.bin"
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

    def compile(self):
        """编译合约"""
        print("=" * 60)
        print("🔨 VCCrossChainBridge合约编译工具")
        print("=" * 60)
        print()

        # 1. 设置Solidity编译器
        if not self.setup_solc():
            return False

        print()

        # 2. 读取合约文件
        source_code = self.read_contract_file()
        if source_code is None:
            return False

        print()

        # 3. 编译合约
        contract_interface = self.compile_contract(source_code)
        if contract_interface is None:
            return False

        print()

        # 4. 保存编译产物
        self.save_contract_artifact(contract_interface)

        print()
        print("=" * 60)
        print("🎉 VCCrossChainBridge合约编译成功！")
        print("=" * 60)
        print(f"📁 编译产物保存在: {self.contracts_dir}")
        print()

        return True


def main():
    """主函数"""
    compiler = VCBridgeCompiler(solc_version="0.5.16")
    success = compiler.compile()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
