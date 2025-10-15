#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合约语法检查脚本
检查Solidity合约的语法正确性
"""

import subprocess
import os
from pathlib import Path

class ContractSyntaxChecker:
    def __init__(self):
        """初始化语法检查器"""
        self.contracts_dir = Path(__file__).parent
        self.check_results = {}
        
    def check_solc_available(self):
        """检查solc编译器是否可用"""
        print("🔍 检查solc编译器...")
        
        try:
            result = subprocess.run(['solc', '--version'], 
                                  capture_output=True, text=True, check=True)
            print(f"✅ solc 可用: {result.stdout.strip()}")
            return True
        except FileNotFoundError:
            print("❌ solc 编译器未安装")
            print("安装方法:")
            print("  Ubuntu/Debian: sudo apt install solc")
            print("  macOS: brew install solidity")
            return False
        except Exception as e:
            print(f"❌ solc 检查失败: {e}")
            return False
    
    def check_single_contract(self, contract_file: str) -> bool:
        """检查单个合约的语法"""
        file_path = self.contracts_dir / contract_file
        
        if not file_path.exists():
            print(f"❌ 文件不存在: {contract_file}")
            return False
        
        print(f"🔍 检查 {contract_file}...")
        
        try:
            # 使用solc进行语法检查
            cmd = [
                'solc',
                '--strict-asm',  # 严格汇编模式
                '--optimize',    # 启用优化
                '--no-color',    # 禁用颜色输出
                str(file_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"   ✅ 语法正确")
                return True
            else:
                print(f"   ❌ 语法错误:")
                print(f"   {result.stderr}")
                return False
                
        except Exception as e:
            print(f"   ❌ 检查失败: {e}")
            return False
    
    def check_all_contracts(self):
        """检查所有合约"""
        print("\n🔍 检查所有合约语法...")
        
        contract_files = [
            "IERC20.sol",
            "CrossChainDIDVerifier.sol",
            "CrossChainBridge.sol", 
            "CrossChainToken.sol",
            "AssetManager.sol"
        ]
        
        results = {}
        all_passed = True
        
        for contract_file in contract_files:
            success = self.check_single_contract(contract_file)
            results[contract_file] = success
            if not success:
                all_passed = False
        
        self.check_results = results
        return all_passed
    
    def check_imports(self):
        """检查导入依赖"""
        print("\n🔍 检查合约导入依赖...")
        
        # 检查CrossChainBridge的导入
        bridge_file = self.contracts_dir / "CrossChainBridge.sol"
        if bridge_file.exists():
            content = bridge_file.read_text(encoding='utf-8')
            if 'import "./CrossChainDIDVerifier.sol";' in content:
                print("   ✅ CrossChainBridge 正确导入 CrossChainDIDVerifier")
            else:
                print("   ❌ CrossChainBridge 缺少 CrossChainDIDVerifier 导入")
            
            if 'import "./IERC20.sol";' in content:
                print("   ✅ CrossChainBridge 正确导入 IERC20")
            else:
                print("   ❌ CrossChainBridge 缺少 IERC20 导入")
        
        # 检查CrossChainToken的导入
        token_file = self.contracts_dir / "CrossChainToken.sol"
        if token_file.exists():
            content = token_file.read_text(encoding='utf-8')
            if 'import "./IERC20.sol";' in content:
                print("   ✅ CrossChainToken 正确导入 IERC20")
            else:
                print("   ❌ CrossChainToken 缺少 IERC20 导入")
            
            if 'import "./CrossChainDIDVerifier.sol";' in content:
                print("   ✅ CrossChainToken 正确导入 CrossChainDIDVerifier")
            else:
                print("   ❌ CrossChainToken 缺少 CrossChainDIDVerifier 导入")
        
        # 检查AssetManager的导入
        asset_file = self.contracts_dir / "AssetManager.sol"
        if asset_file.exists():
            content = asset_file.read_text(encoding='utf-8')
            if 'import "./CrossChainDIDVerifier.sol";' in content:
                print("   ✅ AssetManager 正确导入 CrossChainDIDVerifier")
            else:
                print("   ❌ AssetManager 缺少 CrossChainDIDVerifier 导入")
            
            if 'import "./CrossChainBridge.sol";' in content:
                print("   ✅ AssetManager 正确导入 CrossChainBridge")
            else:
                print("   ❌ AssetManager 缺少 CrossChainBridge 导入")
            
            if 'import "./IERC20.sol";' in content:
                print("   ✅ AssetManager 正确导入 IERC20")
            else:
                print("   ❌ AssetManager 缺少 IERC20 导入")
    
    def check_pragma_versions(self):
        """检查pragma版本声明"""
        print("\n🔍 检查pragma版本声明...")
        
        contract_files = [
            "CrossChainDIDVerifier.sol",
            "CrossChainBridge.sol", 
            "CrossChainToken.sol",
            "AssetManager.sol"
        ]
        
        for contract_file in contract_files:
            file_path = self.contracts_dir / contract_file
            if file_path.exists():
                content = file_path.read_text(encoding='utf-8')
                if 'pragma solidity ^0.8.0;' in content:
                    print(f"   ✅ {contract_file} 使用正确的pragma版本")
                else:
                    print(f"   ⚠️  {contract_file} 可能使用了不兼容的pragma版本")
    
    def generate_syntax_report(self):
        """生成语法检查报告"""
        print("\n📄 生成语法检查报告...")
        
        total_contracts = len(self.check_results)
        passed_contracts = sum(1 for success in self.check_results.values() if success)
        
        report = {
            "syntax_check_summary": {
                "total_contracts": total_contracts,
                "passed_contracts": passed_contracts,
                "failed_contracts": total_contracts - passed_contracts,
                "success_rate": f"{(passed_contracts/total_contracts*100):.1f}%" if total_contracts > 0 else "0%"
            },
            "contract_results": self.check_results,
            "recommendations": []
        }
        
        if passed_contracts == total_contracts:
            report["recommendations"].append("所有合约语法检查通过")
            report["recommendations"].append("可以继续进行编译和部署")
        else:
            report["recommendations"].append("部分合约语法检查未通过")
            report["recommendations"].append("请修复语法错误后重新检查")
        
        # 保存报告
        report_file = self.contracts_dir / "syntax_check_report.json"
        import json
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 语法检查报告已保存到: {report_file}")
        return report
    
    def run_syntax_check(self):
        """运行完整的语法检查"""
        print("🧪 开始合约语法检查...")
        print("=" * 50)
        
        # 检查solc是否可用
        if not self.check_solc_available():
            return False
        
        # 检查所有合约
        all_passed = self.check_all_contracts()
        
        # 检查导入依赖
        self.check_imports()
        
        # 检查pragma版本
        self.check_pragma_versions()
        
        # 生成报告
        report = self.generate_syntax_report()
        
        print("\n" + "=" * 50)
        print("🎉 语法检查完成！")
        
        if all_passed:
            print("✅ 所有合约语法检查通过！")
            print("💡 下一步：可以尝试编译合约")
        else:
            print("⚠️  部分合约语法检查未通过")
            print("💡 请修复语法错误后重新检查")
        
        return all_passed

def main():
    """主函数"""
    print("🧪 合约语法检查工具")
    print("=" * 50)
    print("📝 此工具用于检查Solidity合约的语法正确性")
    print("=" * 50)
    
    checker = ContractSyntaxChecker()
    success = checker.run_syntax_check()
    
    if success:
        print("\n🎉 所有检查通过！合约语法正确。")
    else:
        print("\n⚠️  发现问题，请查看详细报告。")

if __name__ == "__main__":
    main()
