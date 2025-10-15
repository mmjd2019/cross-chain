#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合约功能验证脚本
验证合约函数定义和逻辑完整性
"""

import re
import json
from pathlib import Path

class ContractFunctionValidator:
    def __init__(self):
        """初始化验证器"""
        self.contracts_dir = Path(__file__).parent
        self.validation_results = {}
        
    def extract_functions(self, content: str) -> list:
        """提取合约中的函数定义"""
        # 匹配函数定义的正则表达式 - 支持跨行
        function_pattern = r'function\s+(\w+)\s*\([^)]*\)\s*(?:public|private|internal|external)?\s*(?:view|pure|payable)?\s*(?:returns\s*\([^)]*\))?\s*{'
        functions = re.findall(function_pattern, content, re.MULTILINE | re.DOTALL)
        return functions
    
    def extract_events(self, content: str) -> list:
        """提取合约中的事件定义"""
        event_pattern = r'event\s+(\w+)\s*\([^)]*\);'
        events = re.findall(event_pattern, content, re.MULTILINE)
        return events
    
    def extract_modifiers(self, content: str) -> list:
        """提取合约中的修饰符定义"""
        modifier_pattern = r'modifier\s+(\w+)\s*\([^)]*\)\s*{'
        modifiers = re.findall(modifier_pattern, content, re.MULTILINE)
        return modifiers
    
    def validate_crosschain_did_verifier(self):
        """验证CrossChainDIDVerifier合约"""
        print("🔍 验证 CrossChainDIDVerifier 合约...")
        
        file_path = self.contracts_dir / "CrossChainDIDVerifier.sol"
        if not file_path.exists():
            print("❌ 文件不存在")
            return False
        
        content = file_path.read_text(encoding='utf-8')
        functions = self.extract_functions(content)
        events = self.extract_events(content)
        modifiers = self.extract_modifiers(content)
        
        print(f"   函数数量: {len(functions)}")
        print(f"   事件数量: {len(events)}")
        print(f"   修饰符数量: {len(modifiers)}")
        
        # 检查关键函数
        required_functions = [
            'verifyIdentity',
            'revokeVerification', 
            'recordCrossChainProof',
            'verifyCrossChainProof',
            'addSupportedChain',
            'removeSupportedChain',
            'setCrossChainOracle'
        ]
        
        missing_functions = []
        for func in required_functions:
            if func in functions:
                print(f"   ✅ {func}")
            else:
                print(f"   ❌ {func}")
                missing_functions.append(func)
        
        # 检查关键事件
        required_events = [
            'IdentityVerified',
            'IdentityRevoked',
            'CrossChainProofRecorded',
            'CrossChainProofVerified'
        ]
        
        missing_events = []
        for event in required_events:
            if event in events:
                print(f"   ✅ {event}")
            else:
                print(f"   ❌ {event}")
                missing_events.append(event)
        
        # 检查关键修饰符
        required_modifiers = [
            'onlyOwner',
            'onlyCrossChainOracle',
            'onlyAuthorizedOracle'
        ]
        
        missing_modifiers = []
        for modifier in required_modifiers:
            if modifier in modifiers:
                print(f"   ✅ {modifier}")
            else:
                print(f"   ❌ {modifier}")
                missing_modifiers.append(modifier)
        
        success = len(missing_functions) == 0 and len(missing_events) == 0 and len(missing_modifiers) == 0
        self.validation_results['CrossChainDIDVerifier'] = {
            'success': success,
            'missing_functions': missing_functions,
            'missing_events': missing_events,
            'missing_modifiers': missing_modifiers
        }
        
        return success
    
    def validate_crosschain_bridge(self):
        """验证CrossChainBridge合约"""
        print("\n🔍 验证 CrossChainBridge 合约...")
        
        file_path = self.contracts_dir / "CrossChainBridge.sol"
        if not file_path.exists():
            print("❌ 文件不存在")
            return False
        
        content = file_path.read_text(encoding='utf-8')
        functions = self.extract_functions(content)
        events = self.extract_events(content)
        modifiers = self.extract_modifiers(content)
        
        print(f"   函数数量: {len(functions)}")
        print(f"   事件数量: {len(events)}")
        print(f"   修饰符数量: {len(modifiers)}")
        
        # 检查关键函数
        required_functions = [
            'lockAssets',
            'unlockAssets',
            'addSupportedToken',
            'removeSupportedToken',
            'emergencyUnlock',
            'getLockInfo',
            'getTokenInfo',
            'getBridgeStats'
        ]
        
        missing_functions = []
        for func in required_functions:
            if func in functions:
                print(f"   ✅ {func}")
            else:
                print(f"   ❌ {func}")
                missing_functions.append(func)
        
        # 检查关键事件
        required_events = [
            'AssetLocked',
            'AssetUnlocked',
            'TokenSupported',
            'TokenUnsupported'
        ]
        
        missing_events = []
        for event in required_events:
            if event in events:
                print(f"   ✅ {event}")
            else:
                print(f"   ❌ {event}")
                missing_events.append(event)
        
        success = len(missing_functions) == 0 and len(missing_events) == 0
        self.validation_results['CrossChainBridge'] = {
            'success': success,
            'missing_functions': missing_functions,
            'missing_events': missing_events
        }
        
        return success
    
    def validate_crosschain_token(self):
        """验证CrossChainToken合约"""
        print("\n🔍 验证 CrossChainToken 合约...")
        
        file_path = self.contracts_dir / "CrossChainToken.sol"
        if not file_path.exists():
            print("❌ 文件不存在")
            return False
        
        content = file_path.read_text(encoding='utf-8')
        functions = self.extract_functions(content)
        events = self.extract_events(content)
        modifiers = self.extract_modifiers(content)
        
        print(f"   函数数量: {len(functions)}")
        print(f"   事件数量: {len(events)}")
        print(f"   修饰符数量: {len(modifiers)}")
        
        # 检查ERC20标准函数
        erc20_functions = [
            'totalSupply',
            'balanceOf',
            'transfer',
            'allowance',
            'approve',
            'transferFrom'
        ]
        
        missing_erc20 = []
        for func in erc20_functions:
            if func in functions:
                print(f"   ✅ {func} (ERC20)")
            else:
                print(f"   ❌ {func} (ERC20)")
                missing_erc20.append(func)
        
        # 检查跨链函数
        crosschain_functions = [
            'mint',
            'burn',
            'crossChainLock',
            'crossChainUnlock',
            'setMinter',
            'setCrossChainBridge'
        ]
        
        missing_crosschain = []
        for func in crosschain_functions:
            if func in functions:
                print(f"   ✅ {func} (跨链)")
            else:
                print(f"   ❌ {func} (跨链)")
                missing_crosschain.append(func)
        
        success = len(missing_erc20) == 0 and len(missing_crosschain) == 0
        self.validation_results['CrossChainToken'] = {
            'success': success,
            'missing_erc20': missing_erc20,
            'missing_crosschain': missing_crosschain
        }
        
        return success
    
    def validate_asset_manager(self):
        """验证AssetManager合约"""
        print("\n🔍 验证 AssetManager 合约...")
        
        file_path = self.contracts_dir / "AssetManager.sol"
        if not file_path.exists():
            print("❌ 文件不存在")
            return False
        
        content = file_path.read_text(encoding='utf-8')
        functions = self.extract_functions(content)
        events = self.extract_events(content)
        modifiers = self.extract_modifiers(content)
        
        print(f"   函数数量: {len(functions)}")
        print(f"   事件数量: {len(events)}")
        print(f"   修饰符数量: {len(modifiers)}")
        
        # 检查基础功能函数
        basic_functions = [
            'deposit',
            'withdraw',
            'transfer',
            'depositToken',
            'withdrawToken',
            'transferToken'
        ]
        
        missing_basic = []
        for func in basic_functions:
            if func in functions:
                print(f"   ✅ {func} (基础)")
            else:
                print(f"   ❌ {func} (基础)")
                missing_basic.append(func)
        
        # 检查跨链功能函数
        crosschain_functions = [
            'initiateCrossChainTransfer',
            'completeCrossChainTransfer',
            'addSupportedToken',
            'removeSupportedToken'
        ]
        
        missing_crosschain = []
        for func in crosschain_functions:
            if func in functions:
                print(f"   ✅ {func} (跨链)")
            else:
                print(f"   ❌ {func} (跨链)")
                missing_crosschain.append(func)
        
        # 检查查询函数
        query_functions = [
            'getTokenBalance',
            'getETHBalance',
            'isTokenSupported',
            'getTokenInfo',
            'getUserDID',
            'isUserVerified'
        ]
        
        missing_query = []
        for func in query_functions:
            if func in functions:
                print(f"   ✅ {func} (查询)")
            else:
                print(f"   ❌ {func} (查询)")
                missing_query.append(func)
        
        success = len(missing_basic) == 0 and len(missing_crosschain) == 0 and len(missing_query) == 0
        self.validation_results['AssetManager'] = {
            'success': success,
            'missing_basic': missing_basic,
            'missing_crosschain': missing_crosschain,
            'missing_query': missing_query
        }
        
        return success
    
    def generate_validation_report(self):
        """生成验证报告"""
        print("\n📄 生成验证报告...")
        
        total_contracts = len(self.validation_results)
        successful_contracts = sum(1 for result in self.validation_results.values() if result['success'])
        
        report = {
            "validation_summary": {
                "total_contracts": total_contracts,
                "successful_contracts": successful_contracts,
                "success_rate": f"{(successful_contracts/total_contracts*100):.1f}%" if total_contracts > 0 else "0%"
            },
            "contract_details": self.validation_results,
            "recommendations": []
        }
        
        # 添加建议
        if successful_contracts == total_contracts:
            report["recommendations"].append("所有合约验证通过，可以进入部署阶段")
        else:
            report["recommendations"].append("部分合约验证未通过，请检查缺失的函数和事件")
        
        report["recommendations"].extend([
            "建议在部署前进行完整的编译测试",
            "建议在测试网络上进行功能验证",
            "建议配置完整的测试环境进行集成测试"
        ])
        
        # 保存报告
        report_file = self.contracts_dir / "contract_validation_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 验证报告已保存到: {report_file}")
        return report
    
    def run_validation(self):
        """运行所有验证"""
        print("🧪 开始合约功能验证...")
        print("=" * 50)
        
        # 验证各个合约
        verifier_ok = self.validate_crosschain_did_verifier()
        bridge_ok = self.validate_crosschain_bridge()
        token_ok = self.validate_crosschain_token()
        asset_ok = self.validate_asset_manager()
        
        # 生成报告
        report = self.generate_validation_report()
        
        print("\n" + "=" * 50)
        print("🎉 验证完成！")
        print(f"\n📊 验证结果:")
        print(f"   CrossChainDIDVerifier: {'✅' if verifier_ok else '❌'}")
        print(f"   CrossChainBridge: {'✅' if bridge_ok else '❌'}")
        print(f"   CrossChainToken: {'✅' if token_ok else '❌'}")
        print(f"   AssetManager: {'✅' if asset_ok else '❌'}")
        
        overall_success = all([verifier_ok, bridge_ok, token_ok, asset_ok])
        print(f"\n总体结果: {'✅ 全部通过' if overall_success else '⚠️ 部分未通过'}")
        
        return overall_success

def main():
    """主函数"""
    print("🧪 合约功能验证工具")
    print("=" * 50)
    print("📝 此工具用于验证合约的函数定义和逻辑完整性")
    print("=" * 50)
    
    validator = ContractFunctionValidator()
    success = validator.run_validation()
    
    if success:
        print("\n✅ 所有合约验证通过！")
        print("💡 下一步：可以尝试编译和部署合约")
    else:
        print("\n⚠️  部分合约验证未通过，请检查相关文件")

if __name__ == "__main__":
    main()
