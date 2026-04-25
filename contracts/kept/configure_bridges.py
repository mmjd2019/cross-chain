#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置VC跨链桥合约
1. 配置Oracle服务允许列表
2. 配置VC管理合约地址列表
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


class BridgeContractConfigurator:
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

    def get_oracle_dids(self):
        """获取Oracle DIDs"""
        oracle_dids = []

        # Index 1: 验证服务（合同管理oracle）
        # Index 8: 跨链Oracle
        # Index 9: 海关验证账户
        for mapping in self.did_map['mappings']:
            if mapping['index'] == 1:
                oracle_dids.append({
                    'did': mapping['did'],
                    'role': '验证服务',
                    'description': mapping['description']
                })
            elif mapping['index'] == 8:
                oracle_dids.append({
                    'did': mapping['did'],
                    'role': '跨链Oracle',
                    'description': mapping['description']
                })
            elif mapping['index'] == 9:
                oracle_dids.append({
                    'did': mapping['did'],
                    'role': '海关验证',
                    'description': mapping['description']
                })

        return oracle_dids

    def get_vc_managers(self):
        """获取VC管理合约地址"""
        # 从部署信息中读取
        deployment_path = f"{CONTRACTS_DIR}/vc_managers_deployment.json"
        with open(deployment_path, 'r') as f:
            deployment = json.load(f)

        chain_a_contracts = deployment['chains']['chain_a']['contracts']

        return {
            'InsuranceContractVCManager': {
                'address': chain_a_contracts['InsuranceContractVCManager'],
                'did_index': 25,
                'did': 'NigJ7PhGbxabxoPWMUNKhR'
            },
            'InspectionReportVCManager': {
                'address': chain_a_contracts['InspectionReportVCManager'],
                'did_index': 24,
                'did': '6tYmkBxgNiUjC82eA6LtJD'
            },
            'CertificateOfOriginVCManager': {
                'address': chain_a_contracts['CertificateOfOriginVCManager'],
                'did_index': 26,
                'did': '2Zpf3vvLM8S4skc36ejWQ6'
            },
            'BillOfLadingVCManager': {
                'address': chain_a_contracts['BillOfLadingVCManager'],
                'did_index': 27,
                'did': 'HxYJF4jQQcw5c1AUDJFAKf'
            }
        }

    def get_bridge_addresses(self):
        """获取跨链桥地址"""
        deployment_path = f"{CONTRACTS_DIR}/vc_managers_deployment.json"
        with open(deployment_path, 'r') as f:
            deployment = json.load(f)

        return {
            'chain_a': deployment['chains']['chain_a']['contracts']['VCCrossChainBridgeSimple'],
            'chain_b': deployment['chains']['chain_b']['contracts']['VCCrossChainBridgeSimple']
        }

    def configure_bridge(self, w3, bridge_address, chain_name, vc_managers=None, chain_config=None):
        """配置跨链桥合约"""
        print(f"\n{'='*70}")
        print(f"📝 配置 {chain_name} VCCrossChainBridgeSimple")
        print(f"{'='*70}")
        print(f"  合约地址: {bridge_address}")

        # 加载合约
        abi = self.load_contract_abi('VCCrossChainBridgeSimple')
        bridge = w3.eth.contract(address=bridge_address, abi=abi)

        private_key = chain_config['private_key']
        account_address = Web3.to_checksum_address(
            w3.eth.account.from_key(private_key).address
        )

        # 获取Oracle DIDs
        oracle_dids = self.get_oracle_dids()

        # 1. 配置Oracle DIDs
        print(f"\n  1. 配置Oracle服务允许列表 ({len(oracle_dids)}个):")

        for oracle_info in oracle_dids:
            did = oracle_info['did']
            print(f"\n     - {oracle_info['role']}")
            print(f"       DID: {did}")

            try:
                transaction = bridge.functions.addOracleDID(did).build_transaction({
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
                    print(f"       ✅ 添加成功")
                else:
                    print(f"       ❌ 添加失败")
                    return False

            except Exception as e:
                print(f"       ❌ 添加失败: {str(e)}")
                return False

        # 2. 配置VC Managers（如果提供）
        if vc_managers:
            print(f"\n  2. 配置VC管理合约地址列表 ({len(vc_managers)}个):")

            for contract_name, manager_info in vc_managers.items():
                address = manager_info['address']
                print(f"\n     - {contract_name}")
                print(f"       地址: {address}")
                print(f"       DID: {manager_info['did']}")

                try:
                    transaction = bridge.functions.addVCManager(address).build_transaction({
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
                        print(f"       ✅ 添加成功")
                    else:
                        print(f"       ❌ 添加失败")
                        return False

                except Exception as e:
                    print(f"       ❌ 添加失败: {str(e)}")
                    return False

        # 3. 验证配置
        print(f"\n  3. 验证配置:")
        try:
            # 验证Oracle DIDs
            print(f"\n     Oracle DIDs:")
            for oracle_info in oracle_dids:
                is_allowed = bridge.functions.oracleDIDList(oracle_info['did']).call()
                status = "✅" if is_allowed else "❌"
                print(f"     {status} {oracle_info['role']}: {is_allowed}")

            # 验证VC Managers
            if vc_managers:
                print(f"\n     VC Managers:")
                for contract_name, manager_info in vc_managers.items():
                    is_allowed = bridge.functions.vcManagerList(manager_info['address']).call()
                    status = "✅" if is_allowed else "❌"
                    print(f"     {status} {contract_name}: {is_allowed}")

        except Exception as e:
            print(f"     ⚠️  无法验证配置: {str(e)}")

        return True

    def configure_all_bridges(self):
        """配置所有跨链桥合约"""
        print("="*70)
        print("🚀 配置VC跨链桥合约")
        print("="*70)

        # 获取Oracle DIDs和VC Managers
        oracle_dids = self.get_oracle_dids()
        vc_managers = self.get_vc_managers()
        bridge_addresses = self.get_bridge_addresses()

        print("\n📋 Oracle DIDs:")
        for oracle_info in oracle_dids:
            print(f"  {oracle_info['role']}: {oracle_info['did']}")

        print("\n📋 VC管理合约:")
        for name, info in vc_managers.items():
            print(f"  {name}: {info['address']}")

        results = {
            'configuration_timestamp': datetime.now().isoformat(),
            'chains': {}
        }

        # 配置Chain A
        try:
            w3_a, chain_a_config = self.connect_to_chain("Besu Chain A")
            success = self.configure_bridge(
                w3_a,
                bridge_addresses['chain_a'],
                "Besu Chain A",
                vc_managers,
                chain_a_config
            )
            results['chains']['chain_a'] = {
                'bridge_address': bridge_addresses['chain_a'],
                'oracle_dids': [o['did'] for o in oracle_dids],
                'vc_managers': list(vc_managers.keys()),
                'success': success
            }
        except Exception as e:
            print(f"\n❌ Chain A 配置失败: {str(e)}")
            results['chains']['chain_a'] = {
                'success': False,
                'error': str(e)
            }

        # 配置Chain B
        try:
            w3_b, chain_b_config = self.connect_to_chain("Besu Chain B")
            success = self.configure_bridge(
                w3_b,
                bridge_addresses['chain_b'],
                "Besu Chain B",
                None,  # Chain B暂不添加VC Manager
                chain_b_config
            )
            results['chains']['chain_b'] = {
                'bridge_address': bridge_addresses['chain_b'],
                'oracle_dids': [o['did'] for o in oracle_dids],
                'vc_managers': [],
                'success': success
            }
        except Exception as e:
            print(f"\n❌ Chain B 配置失败: {str(e)}")
            results['chains']['chain_b'] = {
                'success': False,
                'error': str(e)
            }

        # 保存结果
        output_path = f"{CONTRACTS_DIR}/bridge_configuration.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*70}")
        print(f"📄 配置结果已保存到: {output_path}")
        print(f"{'='*70}")

        # 打印摘要
        print(f"\n📊 配置摘要:")
        all_success = True
        for chain_key, chain_result in results['chains'].items():
            chain_name = "Besu Chain " + chain_key.split('_')[1].upper()
            status = "✅ 成功" if chain_result['success'] else "❌ 失败"
            print(f"  {chain_name}: {status}")
            if not chain_result['success']:
                all_success = False

        return all_success


def main():
    print("🚀 VC跨链桥合约配置工具")
    print("="*70)

    configurator = BridgeContractConfigurator(CONFIG_PATH, DID_ADDRESS_MAP_PATH)
    success = configurator.configure_all_bridges()

    if success:
        print("\n✅ 所有跨链桥合约配置成功！")
        return 0
    else:
        print("\n❌ 部分跨链桥合约配置失败！")
        return 1


if __name__ == "__main__":
    sys.exit(main())
