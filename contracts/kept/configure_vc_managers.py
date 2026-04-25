#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置VC管理合约的DID许可列表
1. Oracle服务允许列表
2. 跨链用户许可DID列表
"""

import json
import sys
from web3 import Web3
from web3.middleware import geth_poa_middleware
from datetime import datetime

# 配置路径
CONFIG_PATH = "/home/manifold/cursor/cross-chain/config/cross_chain_config.json."
DID_ADDRESS_MAP_PATH = "/home/manifold/cursor/cross-chain/config/did_address_map.json"
CONTRACTS_DIR = "/home/manifold/cursor/cross-chain/contracts/kept"


class VCManagerConfigurator:
    def __init__(self, config_path, did_address_map_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        with open(did_address_map_path, 'r', encoding='utf-8') as f:
            self.did_map = json.load(f)

        self.chains = self.config['chains']

    def connect_to_chain(self, chain_name):
        """连接到区块链"""
        chain_config = None
        for chain in self.chains:
            if chain['name'] == chain_name:
                chain_config = chain
                break

        if not chain_config:
            raise ValueError(f"未找到链配置: {chain_name}")

        w3 = Web3(Web3.HTTPProvider(chain_config['rpc_url'], request_kwargs={'timeout': 30}))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        try:
            w3.eth.get_block('latest')
        except Exception as e:
            raise ConnectionError(f"无法连接到 {chain_name}: {str(e)}")

        return w3, chain_config

    def load_contract_abi(self, contract_name):
        """加载合约ABI"""
        abi_path = f"{CONTRACTS_DIR}/build/{contract_name}.abi"
        with open(abi_path, 'r') as f:
            return json.load(f)

    def get_oracle_and_trader_dids(self):
        """从did_address_map.json中提取Oracle和交易商DID"""
        oracles = {}
        traders = {}

        for mapping in self.did_map['mappings']:
            # Oracle DIDs (索引2-5: 质检、保险、原产地、提单)
            if mapping['index'] in [2, 3, 4, 5]:
                role = mapping['description'].split('的')[0]  # 提取角色名
                oracles[mapping['index']] = {
                    'did': mapping['did'],
                    'role': role,
                    'address': mapping['address']
                }

            # 交易商DIDs (索引6-7: 进口商、出口商)
            elif mapping['index'] in [6, 7]:
                role = mapping['description'].split('的')[0]  # 提取角色名
                traders[mapping['index']] = {
                    'did': mapping['did'],
                    'role': role,
                    'address': mapping['address']
                }

        return oracles, traders

    def get_vc_managers_config(self):
        """获取VC管理合约的配置信息"""
        # 从部署信息中读取
        deployment_path = f"{CONTRACTS_DIR}/vc_managers_deployment.json"
        with open(deployment_path, 'r') as f:
            deployment = json.load(f)

        chain_a_contracts = deployment['chains']['chain_a']['contracts']

        return {
            'InsuranceContractVCManager': {
                'address': chain_a_contracts['InsuranceContractVCManager'],
                'oracle_index': 3,  # 保险oracle
                'oracle_did': 'FbninXVQUEGnyLMEV4Lp6w'
            },
            'InspectionReportVCManager': {
                'address': chain_a_contracts['InspectionReportVCManager'],
                'oracle_index': 2,  # 质检oracle
                'oracle_did': '8mybikcWR9Bc2iJtnYckPU'
            },
            'CertificateOfOriginVCManager': {
                'address': chain_a_contracts['CertificateOfOriginVCManager'],
                'oracle_index': 4,  # 原产地oracle
                'oracle_did': 'NrpRoUbCVrxAUhW6xBfDhm'
            },
            'BillOfLadingVCManager': {
                'address': chain_a_contracts['BillOfLadingVCManager'],
                'oracle_index': 5,  # 提单oracle
                'oracle_did': 'TUsBvWLvuRpUBK7r7Sen9c'
            }
        }

    def configure_contract(self, w3, contract_address, contract_name, oracle_did, trader_dids, chain_config):
        """配置单个VC管理合约"""
        print(f"\n{'='*70}")
        print(f"📝 配置 {contract_name}")
        print(f"{'='*70}")
        print(f"  合约地址: {contract_address}")

        # 加载合约
        abi = self.load_contract_abi(contract_name)
        contract = w3.eth.contract(address=contract_address, abi=abi)

        private_key = chain_config['private_key']
        account_address = Web3.to_checksum_address(
            w3.eth.account.from_key(private_key).address
        )

        # 需要添加的DID列表
        dids_to_add = [oracle_did] + trader_dids

        print(f"\n  需要配置的DID数量: {len(dids_to_add)}")

        # 1. 添加Oracle DID到许可列表
        print(f"\n  1. 添加Oracle DID:")
        print(f"     DID: {oracle_did}")

        try:
            # 构建交易
            transaction = contract.functions.addOracleDID(oracle_did).build_transaction({
                'from': account_address,
                'gasPrice': chain_config['gas_price'],
                'gas': chain_config['gas_limit'],
                'nonce': w3.eth.get_transaction_count(account_address),
            })

            # 签名并发送
            signed_txn = w3.eth.account.sign_transaction(transaction, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            print(f"     交易哈希: {signed_txn.hash.hex()}")

            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if tx_receipt['status'] == 1:
                print(f"     ✅ Oracle DID添加成功")
            else:
                print(f"     ❌ Oracle DID添加失败")
                return False

        except Exception as e:
            print(f"     ❌ 添加Oracle DID失败: {str(e)}")
            return False

        # 2. 添加跨链用户DID（Oracle + 进口商 + 出口商）
        print(f"\n  2. 添加跨链用户DID:")

        for did in dids_to_add:
            print(f"\n     DID: {did}")
            try:
                transaction = contract.functions.addCrossChainDID(did).build_transaction({
                    'from': account_address,
                    'gasPrice': chain_config['gas_price'],
                    'gas': chain_config['gas_limit'],
                    'nonce': w3.eth.get_transaction_count(account_address),
                })

                signed_txn = w3.eth.account.sign_transaction(transaction, private_key)
                tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                print(f"       交易哈希: {signed_txn.hash.hex()}")

                tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                if tx_receipt['status'] == 1:
                    print(f"       ✅ 跨链用户DID添加成功")
                else:
                    print(f"       ❌ 跨链用户DID添加失败")
                    return False

            except Exception as e:
                print(f"       ❌ 添加跨链用户DID失败: {str(e)}")
                return False

        # 3. 验证配置
        print(f"\n  3. 验证配置:")
        try:
            # 检查Oracle DID
            is_allowed = contract.functions.oracleAllowedDIDs(oracle_did).call()
            status = "✅" if is_allowed else "❌"
            print(f"     {status} Oracle DID许可: {is_allowed}")

            # 检查跨链用户DID
            for did in dids_to_add:
                is_allowed = contract.functions.crossChainAllowedDIDs(did).call()
                status = "✅" if is_allowed else "❌"
                print(f"     {status} 跨链用户 {did}: {is_allowed}")

        except Exception as e:
            print(f"     ⚠️  无法验证配置: {str(e)}")

        return True

    def configure_all_contracts(self):
        """配置所有VC管理合约"""
        print("="*70)
        print("🚀 配置VC管理合约DID许可列表")
        print("="*70)

        # 获取Oracle和交易商DID
        oracles, traders = self.get_oracle_and_trader_dids()

        print("\n📋 Oracle DIDs:")
        for idx, oracle in oracles.items():
            print(f"  Index {idx}: {oracle['role']} - {oracle['did']}")

        print("\n📋 交易商 DIDs:")
        for idx, trader in traders.items():
            print(f"  Index {idx}: {trader['role']} - {trader['did']}")

        # 获取VC管理合约配置
        vc_managers = self.get_vc_managers_config()

        # 连接到Chain A
        w3, chain_config = self.connect_to_chain("Besu Chain A")

        # 提取交易商DIDs
        trader_dids = [t['did'] for t in traders.values()]

        results = {
            'configuration_timestamp': datetime.now().isoformat(),
            'contracts': {}
        }

        # 配置每个VC管理合约
        for contract_name, config in vc_managers.items():
            success = self.configure_contract(
                w3,
                config['address'],
                contract_name,
                config['oracle_did'],
                trader_dids,
                chain_config
            )

            results['contracts'][contract_name] = {
                'address': config['address'],
                'oracle_did': config['oracle_did'],
                'trader_dids': trader_dids,
                'success': success
            }

        # 保存结果
        output_path = f"{CONTRACTS_DIR}/vc_managers_configuration.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*70}")
        print(f"📄 配置结果已保存到: {output_path}")
        print(f"{'='*70}")

        # 打印摘要
        print(f"\n📊 配置摘要:")
        all_success = True
        for contract_name, result in results['contracts'].items():
            status = "✅ 成功" if result['success'] else "❌ 失败"
            print(f"  {contract_name}: {status}")
            if not result['success']:
                all_success = False

        return all_success


def main():
    print("🚀 VC管理合约配置工具")
    print("="*70)

    configurator = VCManagerConfigurator(CONFIG_PATH, DID_ADDRESS_MAP_PATH)
    success = configurator.configure_all_contracts()

    if success:
        print("\n✅ 所有合约配置成功！")
        return 0
    else:
        print("\n❌ 部分合约配置失败！")
        return 1


if __name__ == "__main__":
    sys.exit(main())
