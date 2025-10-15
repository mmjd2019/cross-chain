# -*- coding: utf-8 -*-
"""
智能合约编译脚本
"""
import os
import json
import logging
from pathlib import Path
from solcx import compile_source, install_solc, set_solc_version
from config import ContractConfig

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ContractCompiler")

class ContractCompiler:
    def __init__(self):
        self.config = ContractConfig()
        self.contracts_dir = Path(".")
        self.build_dir = Path(self.config.BUILD_DIR)
        self.abi_dir = Path(self.config.ABI_DIR)
        
        # 创建构建目录
        self.build_dir.mkdir(exist_ok=True)
        self.abi_dir.mkdir(exist_ok=True)
        
        # 安装并设置Solidity版本
        self._setup_solc()
    
    def _setup_solc(self):
        """设置Solidity编译器"""
        try:
            # 安装Solidity 0.8.19版本
            install_solc('0.8.19')
            set_solc_version('0.8.19')
            logger.info("Solidity编译器设置成功")
        except Exception as e:
            logger.error(f"设置Solidity编译器失败: {e}")
            raise
    
    def compile_contract(self, contract_file):
        """编译单个合约"""
        contract_path = self.contracts_dir / contract_file
        
        if not contract_path.exists():
            raise FileNotFoundError(f"合约文件不存在: {contract_path}")
        
        logger.info(f"开始编译合约: {contract_file}")
        
        # 读取合约源码
        with open(contract_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        # 编译合约
        compiled_sol = compile_source(
            source_code,
            output_values=['abi', 'bin'],
            solc_version='0.8.19'
        )
        
        # 获取合约名称（从文件名推断）
        contract_name = contract_path.stem
        
        # 提取编译结果
        contract_interface = compiled_sol[f'<stdin>:{contract_name}']
        
        # 保存编译结果
        self._save_compiled_contract(contract_name, contract_interface)
        
        logger.info(f"合约 {contract_name} 编译成功")
        return contract_interface
    
    def _save_compiled_contract(self, contract_name, contract_interface):
        """保存编译后的合约"""
        # 保存完整的编译结果
        build_file = self.build_dir / f"{contract_name}.json"
        with open(build_file, 'w', encoding='utf-8') as f:
            json.dump(contract_interface, f, indent=2, ensure_ascii=False)
        
        # 保存ABI文件
        abi_file = self.abi_dir / f"{contract_name}.abi"
        with open(abi_file, 'w', encoding='utf-8') as f:
            json.dump(contract_interface['abi'], f, indent=2, ensure_ascii=False)
        
        # 保存字节码文件
        bytecode_file = self.build_dir / f"{contract_name}.bin"
        with open(bytecode_file, 'w', encoding='utf-8') as f:
            f.write(contract_interface['bin'])
        
        logger.info(f"合约 {contract_name} 编译结果已保存")
    
    def compile_all_contracts(self):
        """编译所有合约"""
        logger.info("开始编译所有合约")
        
        # 获取所有.sol文件
        sol_files = list(self.contracts_dir.glob("*.sol"))
        
        if not sol_files:
            logger.warning("未找到任何.sol文件")
            return {}
        
        compiled_contracts = {}
        
        for sol_file in sol_files:
            try:
                contract_interface = self.compile_contract(sol_file.name)
                compiled_contracts[sol_file.stem] = contract_interface
            except Exception as e:
                logger.error(f"编译合约 {sol_file.name} 失败: {e}")
        
        logger.info(f"编译完成，共编译 {len(compiled_contracts)} 个合约")
        return compiled_contracts

def main():
    """主函数"""
    compiler = ContractCompiler()
    
    try:
        # 编译所有合约
        compiled_contracts = compiler.compile_all_contracts()
        
        # 打印编译结果摘要
        print("\n=== 编译结果摘要 ===")
        for name, interface in compiled_contracts.items():
            print(f"合约: {name}")
            print(f"  ABI长度: {len(interface['abi'])} 项")
            print(f"  字节码长度: {len(interface['bin'])} 字符")
            print()
        
        print("编译完成！")
        
    except Exception as e:
        logger.error(f"编译过程中出错: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
