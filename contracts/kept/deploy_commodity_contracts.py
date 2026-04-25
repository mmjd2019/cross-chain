#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大宗货物跨境交易智能合约部署脚本
部署7个成功编译的合约到Chain A和Chain B

Chain A: DIDVerifier, ContractManager, 4 VC Managers, VCCrossChainBridge
Chain B: DIDVerifier, VCCrossChainBridge
"""

import json
import os
import sys
from web3 import Web3
from web3.middleware import geth_poa_middleware
from datetime import datetime

# 读取配置文件
CONFIG_PATH = "/home/manifold/cursor/cross-chain/config/cross_chain_config.json."
CONTRACTS_DIR = "/home/manifold/cursor/cross-chain/contracts/kept"

class ContractDeployer:
    def __init__(self, config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        self.chains = self.config['chains']
        self.deployed_contracts = {}

    def load_contract_artifact(self, contract_name):
        """加载合约编译产物"""
        artifact_path = os.path.join(CONTRACTS_DIR, f"{contract_name}.json")
        if not os.path.exists(artifact_path):
            raise FileNotFoundError(f"合约文件不存在: {artifact_path}")

        with open(artifact_path, 'r', encoding='utf-8') as f:
            artifact = json.load(f)

        return artifact['abi'], artifact['bytecode']

    def connect_to_chain(self, chain_config):
        """连接到区块链"""
        w3 = Web3(Web3.HTTPProvider(chain_config['rpc_url'], request_kwargs={'timeout': 30}))

        # 添加POA中间件（用于IBFT 2.0共识的Besu链）
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        # 检查连接 - 使用更宽松的方式
        try:
            w3.eth.get_block('latest')
        except Exception as e:
            raise ConnectionError(f"无法连接到 {chain_config['name']}: {str(e)}")

        # 检查账户余额
        account_address = chain_config['private_key']
        address = Web3.to_checksum_address(w3.eth.account.from_key(chain_config['private_key']).address)
        balance = w3.eth.get_balance(address)

        print(f"  链: {chain_config['name']}")
        print(f"  RPC: {chain_config['rpc_url']}")
        print(f"  部署账户: {address}")
        print(f"  账户余额: {w3.from_wei(balance, 'ether')} ETH")

        if balance == 0:
            raise ValueError(f"账户 {address} 余额为0，无法部署合约")

        return w3, address

    def deploy_contract(self, w3, account_address, private_key, contract_name, constructor_args=None, chain_config=None):
        """部署单个合约"""
        print(f"\n📦 部署 {contract_name}...")

        # 加载合约ABI和字节码
        abi, bytecode = self.load_contract_artifact(contract_name)

        # 准备构造函数参数
        if constructor_args is None:
            constructor_args = []

        # 获取构造函数
        contract = w3.eth.contract(abi=abi, bytecode=bytecode)

        # 构建交易
        if chain_config:
            transaction = contract.constructor(*constructor_args).build_transaction({
                'from': account_address,
                'gasPrice': chain_config['gas_price'],
                'gas': chain_config['gas_limit'],
                'nonce': w3.eth.get_transaction_count(account_address),
            })
        else:
            transaction = contract.constructor(*constructor_args).build_transaction({
                'from': account_address,
                'gasPrice': 1000000000,
                'gas': 5000000,
                'nonce': w3.eth.get_transaction_count(account_address),
            })

        # 签名交易
        signed_txn = w3.eth.account.sign_transaction(transaction, private_key)

        # 发送交易
        print(f"  交易哈希: {signed_txn.hash.hex()}")
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

        # 等待交易确认
        print(f"  等待确认...")
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if tx_receipt['status'] == 1:
            contract_address = tx_receipt['contractAddress']
            print(f"  ✅ {contract_name} 部署成功!")
            print(f"  合约地址: {contract_address}")
            return contract_address
        else:
            raise Exception(f"{contract_name} 部署失败")

    def deploy_chain_a(self):
        """部署合约到Chain A"""
        print("\n" + "="*70)
        print("🚀 开始部署到 Chain A")
        print("="*70)

        chain_config = self.chains[0]  # Chain A
        w3, account_address = self.connect_to_chain(chain_config)
        private_key = chain_config['private_key']

        chain_contracts = {}

        # 1. 部署DIDVerifier
        print("\n" + "-"*70)
        print("1/6 部署 DIDVerifier")
        print("-"*70)
        did_verifier_address = self.deploy_contract(w3, account_address, private_key, "DIDVerifier")
        chain_contracts['DIDVerifier'] = did_verifier_address

        # 2. 部署ContractManager
        print("\n" + "-"*70)
        print("2/7 部署 ContractManager")
        print("-"*70)
        contract_manager_address = self.deploy_contract(
            w3, account_address, private_key,
            "ContractManager",
            constructor_args=[did_verifier_address]
        )
        chain_contracts['ContractManager'] = contract_manager_address

        # 3. 部署VCCrossChainBridge (需要在VC Managers之前部署)
        print("\n" + "-"*70)
        print("3/7 部署 VCCrossChainBridge")
        print("-"*70)
        bridge_address = self.deploy_contract(
            w3, account_address, private_key,
            "VCCrossChainBridge",
            constructor_args=[did_verifier_address],
            chain_config=chain_config
        )
        chain_contracts['VCCrossChainBridge'] = bridge_address

        # 4. 部署InspectionReportVCManager
        print("\n" + "-"*70)
        print("4/7 部署 InspectionReportVCManager")
        print("-"*70)
        inspection_vc_address = self.deploy_contract(
            w3, account_address, private_key,
            "InspectionReportVCManager",
            constructor_args=[did_verifier_address, bridge_address]
        )
        chain_contracts['InspectionReportVCManager'] = inspection_vc_address

        # 5. 部署InsuranceContractVCManager
        print("\n" + "-"*70)
        print("5/7 部署 InsuranceContractVCManager")
        print("-"*70)
        insurance_vc_address = self.deploy_contract(
            w3, account_address, private_key,
            "InsuranceContractVCManager",
            constructor_args=[did_verifier_address, bridge_address]
        )
        chain_contracts['InsuranceContractVCManager'] = insurance_vc_address

        # 6. 部署CertificateOfOriginVCManager
        print("\n" + "-"*70)
        print("6/7 部署 CertificateOfOriginVCManager")
        print("-"*70)
        origin_vc_address = self.deploy_contract(
            w3, account_address, private_key,
            "CertificateOfOriginVCManager",
            constructor_args=[did_verifier_address, bridge_address]
        )
        chain_contracts['CertificateOfOriginVCManager'] = origin_vc_address

        # 7. 部署BillOfLadingVCManager
        print("\n" + "-"*70)
        print("7/7 部署 BillOfLadingVCManager")
        print("-"*70)
        bol_vc_address = self.deploy_contract(
            w3, account_address, private_key,
            "BillOfLadingVCManager",
            constructor_args=[did_verifier_address, bridge_address]
        )
        chain_contracts['BillOfLadingVCManager'] = bol_vc_address

        self.deployed_contracts['chain_a'] = {
            'name': 'Besu Chain A',
            'rpc_url': chain_config['rpc_url'],
            'contracts': chain_contracts
        }

        print("\n" + "="*70)
        print(f"✅ Chain A 部署完成! 共部署 {len(chain_contracts)} 个合约")
        print("="*70)

        return chain_contracts

    def deploy_chain_b(self):
        """部署合约到Chain B"""
        print("\n" + "="*70)
        print("🚀 开始部署到 Chain B")
        print("="*70)

        chain_config = self.chains[1]  # Chain B
        w3, account_address = self.connect_to_chain(chain_config)
        private_key = chain_config['private_key']

        chain_contracts = {}

        # 1. 部署DIDVerifier
        print("\n" + "-"*70)
        print("1/2 部署 DIDVerifier")
        print("-"*70)
        did_verifier_address = self.deploy_contract(w3, account_address, private_key, "DIDVerifier")
        chain_contracts['DIDVerifier'] = did_verifier_address

        # 2. 部署VCCrossChainBridge
        print("\n" + "-"*70)
        print("2/2 部署 VCCrossChainBridge")
        print("-"*70)
        bridge_address = self.deploy_contract(
            w3, account_address, private_key,
            "VCCrossChainBridge",
            constructor_args=[did_verifier_address],
            chain_config=chain_config
        )
        chain_contracts['VCCrossChainBridge'] = bridge_address

        self.deployed_contracts['chain_b'] = {
            'name': 'Besu Chain B',
            'rpc_url': chain_config['rpc_url'],
            'contracts': chain_contracts
        }

        print("\n" + "="*70)
        print(f"✅ Chain B 部署完成! 共部署 {len(chain_contracts)} 个合约")
        print("="*70)

        return chain_contracts

    def verify_deployment(self):
        """验证部署结果"""
        print("\n" + "="*70)
        print("🔍 验证部署结果")
        print("="*70)

        for chain_key, chain_data in self.deployed_contracts.items():
            print(f"\n{chain_data['name']} ({chain_data['rpc_url']})")
            print("-"*70)

            w3 = Web3(Web3.HTTPProvider(chain_data['rpc_url'], request_kwargs={'timeout': 30}))
            # 添加POA中间件
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)

            for contract_name, contract_address in chain_data['contracts'].items():
                # 检查合约地址的代码
                code = w3.eth.get_code(contract_address)
                if len(code) > 0:
                    print(f"  ✅ {contract_name}: {contract_address}")
                else:
                    print(f"  ❌ {contract_name}: {contract_address} - 未找到代码")

    def save_deployment_info(self):
        """保存部署信息"""
        deployment_info = {
            'deployment_timestamp': datetime.now().isoformat(),
            'chains': self.deployed_contracts,
            'notes': {
                'chain_a': '部署了DIDVerifier, ContractManager, 4个VCManager, VCCrossChainBridge',
                'chain_b': '部署了DIDVerifier, VCCrossChainBridge',
                'vc_verifier': 'VCVerifier合约因栈深度问题未能部署，验证逻辑将在Oracle服务中实现'
            }
        }

        output_path = os.path.join(CONTRACTS_DIR, 'deployment_results', 'deployment_result.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(deployment_info, f, indent=2, ensure_ascii=False)

        print(f"\n📄 部署信息已保存到: {output_path}")

    def deploy_all(self):
        """部署所有合约"""
        try:
            # 部署到Chain A
            self.deploy_chain_a()

            # 部署到Chain B
            self.deploy_chain_b()

            # 验证部署
            self.verify_deployment()

            # 保存部署信息
            self.save_deployment_info()

            print("\n" + "="*70)
            print("🎉 所有合约部署完成!")
            print("="*70)

            # 输出总结
            print("\n📊 部署总结:")
            print(f"  Chain A: {len(self.deployed_contracts['chain_a']['contracts'])} 个合约")
            print(f"  Chain B: {len(self.deployed_contracts['chain_b']['contracts'])} 个合约")
            print(f"  总计: {len(self.deployed_contracts['chain_a']['contracts']) + len(self.deployed_contracts['chain_b']['contracts'])} 个合约")

            return True

        except Exception as e:
            print(f"\n❌ 部署失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    print("="*70)
    print("🚀 大宗货物跨境交易智能合约部署工具")
    print("="*70)
    print("\n📋 部署计划:")
    print("  Chain A: DIDVerifier, ContractManager, 4个VCManager, VCCrossChainBridge")
    print("  Chain B: DIDVerifier, VCCrossChainBridge")
    print("\n⚠️  注意: VCVerifier合约因编译问题暂不部署，验证逻辑由Oracle服务实现")
    print("="*70)

    # 确认配置文件
    if not os.path.exists(CONFIG_PATH):
        print(f"\n❌ 配置文件不存在: {CONFIG_PATH}")
        sys.exit(1)

    # 创建部署器
    deployer = ContractDeployer(CONFIG_PATH)

    # 执行部署
    success = deployer.deploy_all()

    sys.exit(0 if success else 1)
