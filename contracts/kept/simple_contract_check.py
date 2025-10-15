#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单合约检查脚本
直接检查合约文件中是否包含关键函数名
"""

import os
from pathlib import Path

class SimpleContractChecker:
    def __init__(self):
        """初始化检查器"""
        self.contracts_dir = Path(__file__).parent
        self.results = {}
        
    def check_contract(self, filename: str, required_functions: list) -> dict:
        """检查单个合约"""
        file_path = self.contracts_dir / filename
        
        if not file_path.exists():
            return {"exists": False, "found_functions": [], "missing_functions": required_functions}
        
        content = file_path.read_text(encoding='utf-8')
        found_functions = []
        missing_functions = []
        
        for func in required_functions:
            if f"function {func}" in content:
                found_functions.append(func)
            else:
                missing_functions.append(func)
        
        return {
            "exists": True,
            "found_functions": found_functions,
            "missing_functions": missing_functions,
            "total_functions": len(required_functions),
            "found_count": len(found_functions)
        }
    
    def run_all_checks(self):
        """运行所有检查"""
        print("🧪 简单合约检查工具")
        print("=" * 50)
        
        # 定义要检查的合约和函数
        contracts_to_check = {
            "CrossChainDIDVerifier.sol": [
                "verifyIdentity",
                "revokeVerification", 
                "recordCrossChainProof",
                "verifyCrossChainProof",
                "addSupportedChain",
                "removeSupportedChain",
                "setCrossChainOracle"
            ],
            "CrossChainBridge.sol": [
                "lockAssets",
                "unlockAssets",
                "addSupportedToken",
                "removeSupportedToken",
                "emergencyUnlock",
                "getLockInfo",
                "getTokenInfo",
                "getBridgeStats"
            ],
            "CrossChainToken.sol": [
                "totalSupply",
                "balanceOf",
                "transfer",
                "allowance",
                "approve",
                "transferFrom",
                "mint",
                "burn",
                "crossChainLock",
                "crossChainUnlock",
                "setMinter",
                "setCrossChainBridge"
            ],
            "AssetManager.sol": [
                "deposit",
                "withdraw",
                "transfer",
                "depositToken",
                "withdrawToken",
                "transferToken",
                "initiateCrossChainTransfer",
                "completeCrossChainTransfer",
                "addSupportedToken",
                "removeSupportedToken",
                "getTokenBalance",
                "getETHBalance",
                "isTokenSupported",
                "getTokenInfo",
                "getUserDID",
                "isUserVerified"
            ],
            "IERC20.sol": [
                "totalSupply",
                "balanceOf",
                "transfer",
                "allowance",
                "approve",
                "transferFrom"
            ]
        }
        
        all_passed = True
        
        for filename, functions in contracts_to_check.items():
            print(f"\n📋 检查 {filename}:")
            result = self.check_contract(filename, functions)
            self.results[filename] = result
            
            if not result["exists"]:
                print(f"   ❌ 文件不存在")
                all_passed = False
                continue
            
            print(f"   📊 函数统计: {result['found_count']}/{result['total_functions']}")
            
            # 显示找到的函数
            if result["found_functions"]:
                print(f"   ✅ 找到的函数:")
                for func in result["found_functions"]:
                    print(f"      - {func}")
            
            # 显示缺失的函数
            if result["missing_functions"]:
                print(f"   ❌ 缺失的函数:")
                for func in result["missing_functions"]:
                    print(f"      - {func}")
                all_passed = False
            else:
                print(f"   ✅ 所有函数都存在")
        
        # 生成总结
        print("\n" + "=" * 50)
        print("📊 检查总结:")
        
        total_contracts = len(contracts_to_check)
        successful_contracts = sum(1 for result in self.results.values() if result["exists"] and len(result["missing_functions"]) == 0)
        
        print(f"   总合约数: {total_contracts}")
        print(f"   成功: {successful_contracts}")
        print(f"   失败: {total_contracts - successful_contracts}")
        print(f"   成功率: {(successful_contracts/total_contracts*100):.1f}%")
        
        if all_passed:
            print("\n🎉 所有检查通过！")
            print("✅ 合约结构完整，可以进入下一阶段")
        else:
            print("\n⚠️  部分检查未通过")
            print("❌ 请检查缺失的函数")
        
        return all_passed

def main():
    """主函数"""
    checker = SimpleContractChecker()
    checker.run_all_checks()

if __name__ == "__main__":
    main()
