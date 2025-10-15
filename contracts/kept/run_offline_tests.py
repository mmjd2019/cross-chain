#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合离线测试脚本
在链连接不可用时进行全面的合约测试
"""

import subprocess
import sys
from pathlib import Path

class OfflineTestRunner:
    def __init__(self):
        """初始化测试运行器"""
        self.contracts_dir = Path(__file__).parent
        self.test_scripts = [
            "check_contract_syntax.py",
            "validate_contract_functions.py", 
            "test_contracts_offline.py"
        ]
        self.results = {}
        
    def run_script(self, script_name: str) -> bool:
        """运行单个测试脚本"""
        print(f"\n🚀 运行 {script_name}...")
        print("-" * 40)
        
        script_path = self.contracts_dir / script_name
        if not script_path.exists():
            print(f"❌ 脚本不存在: {script_name}")
            return False
        
        try:
            result = subprocess.run([
                sys.executable, str(script_path)
            ], capture_output=True, text=True, cwd=str(self.contracts_dir))
            
            # 打印输出
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)
            
            success = result.returncode == 0
            self.results[script_name] = {
                'success': success,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
            if success:
                print(f"✅ {script_name} 执行成功")
            else:
                print(f"❌ {script_name} 执行失败 (返回码: {result.returncode})")
            
            return success
            
        except Exception as e:
            print(f"❌ 运行 {script_name} 时出错: {e}")
            self.results[script_name] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def check_prerequisites(self):
        """检查前置条件"""
        print("🔍 检查前置条件...")
        
        # 检查合约文件
        required_files = [
            "CrossChainDIDVerifier.sol",
            "CrossChainBridge.sol",
            "CrossChainToken.sol", 
            "AssetManager.sol",
            "IERC20.sol"
        ]
        
        missing_files = []
        for file in required_files:
            if not (self.contracts_dir / file).exists():
                missing_files.append(file)
        
        if missing_files:
            print(f"❌ 缺少文件: {', '.join(missing_files)}")
            return False
        
        print("✅ 所有合约文件存在")
        
        # 检查Python环境
        print(f"✅ Python版本: {sys.version}")
        
        # 检查必要的Python包
        try:
            import json
            print("✅ json 模块可用")
        except ImportError:
            print("❌ json 模块不可用")
            return False
        
        return True
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🧪 开始综合离线测试...")
        print("=" * 60)
        
        # 检查前置条件
        if not self.check_prerequisites():
            print("❌ 前置条件检查失败")
            return False
        
        # 运行各个测试脚本
        all_passed = True
        for script in self.test_scripts:
            success = self.run_script(script)
            if not success:
                all_passed = False
        
        # 生成综合报告
        self.generate_comprehensive_report()
        
        return all_passed
    
    def generate_comprehensive_report(self):
        """生成综合测试报告"""
        print("\n📄 生成综合测试报告...")
        
        total_scripts = len(self.test_scripts)
        successful_scripts = sum(1 for result in self.results.values() if result.get('success', False))
        
        report = {
            "test_summary": {
                "total_scripts": total_scripts,
                "successful_scripts": successful_scripts,
                "failed_scripts": total_scripts - successful_scripts,
                "success_rate": f"{(successful_scripts/total_scripts*100):.1f}%" if total_scripts > 0 else "0%"
            },
            "script_results": self.results,
            "recommendations": []
        }
        
        # 添加建议
        if successful_scripts == total_scripts:
            report["recommendations"].extend([
                "所有离线测试通过",
                "合约结构完整，功能设计合理",
                "可以尝试编译合约",
                "建议在链连接可用后进行部署测试"
            ])
        else:
            report["recommendations"].extend([
                "部分测试未通过，请检查相关文件",
                "修复问题后重新运行测试",
                "确保所有依赖文件存在"
            ])
        
        # 保存报告
        import json
        report_file = self.contracts_dir / "comprehensive_test_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 综合测试报告已保存到: {report_file}")
        
        # 打印总结
        print("\n" + "=" * 60)
        print("📊 测试总结:")
        print(f"   总测试脚本: {total_scripts}")
        print(f"   成功: {successful_scripts}")
        print(f"   失败: {total_scripts - successful_scripts}")
        print(f"   成功率: {(successful_scripts/total_scripts*100):.1f}%")
        
        return report
    
    def print_next_steps(self):
        """打印后续步骤建议"""
        print("\n💡 后续步骤建议:")
        print("1. 确保Besu链正常运行")
        print("   - 链A: docker-compose -f docker-compose1.yml up -d")
        print("   - 链B: docker-compose -f docker-compose2.yml up -d")
        print("")
        print("2. 编译合约")
        print("   - python3 compile_crosschain_contracts.py")
        print("")
        print("3. 部署系统")
        print("   - python3 deploy_crosschain_system.py")
        print("")
        print("4. 配置Oracle服务")
        print("   - 启动VON Network")
        print("   - 配置ACA-Py服务")
        print("")
        print("5. 运行完整测试")
        print("   - python3 test_crosschain_system.py")

def main():
    """主函数"""
    print("🧪 综合离线测试工具")
    print("=" * 60)
    print("📝 此工具用于在链连接不可用时进行全面的合约测试")
    print("=" * 60)
    
    runner = OfflineTestRunner()
    success = runner.run_all_tests()
    
    if success:
        print("\n🎉 所有离线测试通过！")
        print("✅ 合约准备就绪，可以进入下一阶段")
    else:
        print("\n⚠️  部分测试未通过")
        print("❌ 请检查并修复问题后重新测试")
    
    runner.print_next_steps()

if __name__ == "__main__":
    main()
