# -*- coding: utf-8 -*-
"""
智能合约部署脚本
"""
import os
import json
import logging
from pathlib import Path
from web3 import Web3
from config import ContractConfig
from compile_contracts import ContractCompiler

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ContractDeployer")

class ContractDeployer:
    def __init__(self):
        self.config = ContractConfig()
        self.w3 = Web3(Web3.HTTPProvider(self.config.BESU_RPC_URL))
        
        # 检查网络连接
        if not self.w3.is_connected():
            raise Exception(f"无法连接到Besu网络: {self.config.BESU_RPC_URL}")
        
        # 设置部署账户
        if not self.config.DEPLOYER_PRIVATE_KEY:
            raise Exception("未设置部署者私钥")
        
        self.deployer_account = self.w3.eth.account.from_key(self.config.DEPLOYER_PRIVATE_KEY)
        logger.info(f"部署者账户: {self.deployer_account.address}")
        
        # 检查账户余额
        balance = self.w3.eth.get_balance(self.deployer_account.address)
        logger.info(f"账户余额: {self.w3.from_wei(balance, 'ether')} ETH")
    
    def load_compiled_contract(self, contract_name):
        """加载编译后的合约"""
        build_file = Path(self.config.BUILD_DIR) / f"{contract_name}.json"
        
        if not build_file.exists():
            raise FileNotFoundError(f"编译文件不存在: {build_file}")
        
        with open(build_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def deploy_contract(self, contract_name, constructor_args=None):
        """部署单个合约"""
        logger.info(f"开始部署合约: {contract_name}")
        
        # 加载编译后的合约
        contract_interface = self.load_compiled_contract(contract_name)
        
        # 创建合约实例
        contract = self.w3.eth.contract(
            abi=contract_interface['abi'],
            bytecode=contract_interface['bin']
        )
        
        # 构建构造函数参数
        if constructor_args is None:
            constructor_args = []
        
        # 构建部署交易
        deploy_tx = contract.constructor(*constructor_args).build_transaction({
            'from': self.deployer_account.address,
            'nonce': self.w3.eth.get_transaction_count(self.deployer_account.address),
            'gas': self.config.GAS_LIMIT,
            'gasPrice': self.config.GAS_PRICE,
            'chainId': self.config.CHAIN_ID
        })
        
        # 签名交易
        signed_tx = self.w3.eth.account.sign_transaction(deploy_tx, self.config.DEPLOYER_PRIVATE_KEY)
        
        # 发送交易
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        logger.info(f"部署交易已发送，哈希: {tx_hash.hex()}")
        
        # 等待交易确认
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt.status == 1:
            contract_address = receipt.contractAddress
            logger.info(f"合约 {contract_name} 部署成功，地址: {contract_address}")
            return {
                'name': contract_name,
                'address': contract_address,
                'tx_hash': tx_hash.hex(),
                'gas_used': receipt.gasUsed,
                'block_number': receipt.blockNumber
            }
        else:
            raise Exception(f"合约 {contract_name} 部署失败")
    
    def deploy_all_contracts(self):
        """部署所有合约"""
        logger.info("开始部署所有合约")
        
        # 先编译所有合约
        compiler = ContractCompiler()
        compiled_contracts = compiler.compile_all_contracts()
        
        if not compiled_contracts:
            logger.error("没有可部署的合约")
            return {}
        
        deployment_results = {}
        
        # 部署DIDVerifier合约（无构造函数参数）
        try:
            verifier_result = self.deploy_contract("DIDVerifier")
            deployment_results["DIDVerifier"] = verifier_result
        except Exception as e:
            logger.error(f"部署DIDVerifier失败: {e}")
            return {}
        
        # 部署AssetManager合约（需要DIDVerifier地址作为构造函数参数）
        try:
            asset_manager_result = self.deploy_contract(
                "AssetManager", 
                [verifier_result['address']]
            )
            deployment_results["AssetManager"] = asset_manager_result
        except Exception as e:
            logger.error(f"部署AssetManager失败: {e}")
            return {}
        
        # 保存部署结果
        self._save_deployment_results(deployment_results)
        
        logger.info("所有合约部署完成")
        return deployment_results
    
    def _save_deployment_results(self, results):
        """保存部署结果"""
        deployment_file = Path(self.config.BUILD_DIR) / "deployment.json"
        
        with open(deployment_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"部署结果已保存到: {deployment_file}")
    
    def verify_deployment(self, contract_address):
        """验证合约部署"""
        try:
            code = self.w3.eth.get_code(contract_address)
            if len(code) > 2:  # 0x不是空合约
                logger.info(f"合约地址 {contract_address} 验证成功")
                return True
            else:
                logger.error(f"合约地址 {contract_address} 验证失败：无代码")
                return False
        except Exception as e:
            logger.error(f"验证合约时出错: {e}")
            return False

def main():
    """主函数"""
    try:
        deployer = ContractDeployer()
        
        # 部署所有合约
        results = deployer.deploy_all_contracts()
        
        if not results:
            logger.error("部署失败")
            return 1
        
        # 打印部署结果
        print("\n=== 部署结果 ===")
        for name, result in results.items():
            print(f"合约: {name}")
            print(f"  地址: {result['address']}")
            print(f"  交易哈希: {result['tx_hash']}")
            print(f"  Gas使用: {result['gas_used']}")
            print(f"  区块号: {result['block_number']}")
            print()
        
        # 验证部署
        print("=== 验证部署 ===")
        for name, result in results.items():
            if deployer.verify_deployment(result['address']):
                print(f"✓ {name} 验证成功")
            else:
                print(f"✗ {name} 验证失败")
        
        print("\n部署完成！")
        return 0
        
    except Exception as e:
        logger.error(f"部署过程中出错: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
