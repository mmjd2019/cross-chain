#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨链合约编译脚本
使用solc编译所有跨链相关合约
"""

import os
import json
import subprocess
import sys
from pathlib import Path

class ContractCompiler:
    def __init__(self):
        self.contracts_dir = Path(__file__).parent
        self.build_dir = self.contracts_dir / "build"
        self.build_dir.mkdir(exist_ok=True)
        
        # 合约文件列表
        self.contract_files = [
            "IERC20.sol",
            "CrossChainDIDVerifier.sol", 
            "CrossChainBridge.sol",
            "CrossChainToken.sol",
            "AssetManager.sol"
        ]
    
    def check_solc(self):
        """检查solc是否安装"""
        try:
            result = subprocess.run(['solc', '--version'], 
                                  capture_output=True, text=True, check=True)
            print(f"✅ 找到 solc: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ 未找到 solc 编译器")
            print("请安装 solc:")
            print("  Ubuntu/Debian: sudo apt install solc")
            print("  macOS: brew install solidity")
            print("  或访问: https://docs.soliditylang.org/en/latest/installing-solidity.html")
            return False
    
    def compile_contract(self, contract_file: str):
        """编译单个合约"""
        contract_path = self.contracts_dir / contract_file
        
        if not contract_path.exists():
            print(f"❌ 合约文件不存在: {contract_file}")
            return False
        
        print(f"🔨 编译 {contract_file}...")
        
        try:
            # 编译合约
            cmd = [
                'solc',
                '--optimize',
                '--optimize-runs', '200',
                '--abi',
                '--bin',
                '--overwrite',
                '--output-dir', str(self.build_dir),
                str(contract_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # 生成JSON文件
            contract_name = contract_path.stem
            self.generate_json_artifact(contract_name)
            
            print(f"✅ {contract_file} 编译成功")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 编译 {contract_file} 失败:")
            print(f"错误: {e.stderr}")
            return False
        except Exception as e:
            print(f"❌ 编译 {contract_file} 时出错: {e}")
            return False
    
    def generate_json_artifact(self, contract_name: str):
        """生成JSON格式的合约产物"""
        abi_file = self.build_dir / f"{contract_name}.abi"
        bin_file = self.build_dir / f"{contract_name}.bin"
        
        if not abi_file.exists() or not bin_file.exists():
            print(f"⚠️  未找到 {contract_name} 的编译产物")
            return
        
        try:
            # 读取ABI和字节码
            with open(abi_file, 'r', encoding='utf-8') as f:
                abi = json.load(f)
            
            with open(bin_file, 'r', encoding='utf-8') as f:
                bytecode = f.read().strip()
            
            # 生成JSON产物
            artifact = {
                "contractName": contract_name,
                "abi": abi,
                "bytecode": f"0x{bytecode}",
                "deployedBytecode": f"0x{bytecode}",
                "compiler": {
                    "name": "solc",
                    "version": self.get_solc_version()
                },
                "networks": {},
                "schemaVersion": "3.4.7",
                "updatedAt": self.get_current_timestamp()
            }
            
            # 保存JSON文件
            json_file = self.contracts_dir / f"{contract_name}.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(artifact, f, indent=2, ensure_ascii=False)
            
            print(f"✅ 生成 {contract_name}.json")
            
        except Exception as e:
            print(f"❌ 生成 {contract_name}.json 时出错: {e}")
    
    def get_solc_version(self):
        """获取solc版本"""
        try:
            result = subprocess.run(['solc', '--version'], 
                                  capture_output=True, text=True, check=True)
            version_line = result.stdout.split('\n')[0]
            return version_line.replace('Version: ', '')
        except:
            return "unknown"
    
    def get_current_timestamp(self):
        """获取当前时间戳"""
        import datetime
        return datetime.datetime.now().isoformat()
    
    def compile_all(self):
        """编译所有合约"""
        print("🔨 开始编译跨链合约...")
        print("=" * 50)
        
        if not self.check_solc():
            return False
        
        success_count = 0
        total_count = len(self.contract_files)
        
        for contract_file in self.contract_files:
            if self.compile_contract(contract_file):
                success_count += 1
        
        print("\n" + "=" * 50)
        print(f"📊 编译完成: {success_count}/{total_count} 个合约成功")
        
        if success_count == total_count:
            print("✅ 所有合约编译成功！")
            print(f"📁 编译产物保存在: {self.build_dir}")
            print("📄 JSON产物保存在合约目录")
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
            print("✅ 清理 build 目录")
        
        # 清理JSON文件
        for contract_file in self.contract_files:
            contract_name = Path(contract_file).stem
            json_file = self.contracts_dir / f"{contract_name}.json"
            if json_file.exists():
                json_file.unlink()
                print(f"✅ 删除 {json_file.name}")
    
    def list_contracts(self):
        """列出所有合约文件"""
        print("📋 合约文件列表:")
        print("-" * 30)
        
        for i, contract_file in enumerate(self.contract_files, 1):
            contract_path = self.contracts_dir / contract_file
            status = "✅" if contract_path.exists() else "❌"
            print(f"{i:2d}. {status} {contract_file}")

def main():
    """主函数"""
    print("🔨 跨链合约编译工具")
    print("=" * 50)
    
    compiler = ContractCompiler()
    
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
        compiler.compile_all()

if __name__ == "__main__":
    main()
