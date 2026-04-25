#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证VC管理合约部署
检查所有合约的部署状态、配置和权限
"""

import json
import sys
from web3 import Web3
from web3.middleware import geth_poa_middleware
from datetime import datetime

# 配置路径
CONTRACTS_DIR = "/home/manifold/cursor/cross-chain/contracts/kept"
DEPLOYMENT_INFO = f"{CONTRACTS_DIR}/vc_managers_deployment.json"
CONFIG_PATH = "/home/manifold/cursor/cross-chain/config/cross_chain_config.json."


class VCManagerVerifier:
    def __init__(self, deployment_path, config_path):
        with open(deployment_path, 'r', encoding='utf-8') as f:
            self.deployment = json.load(f)

        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

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

        return w3

    def load_contract_abi(self, contract_name):
        """加载合约ABI"""
        abi_path = f"{CONTRACTS_DIR}/build/{contract_name}.abi"
        with open(abi_path, 'r') as f:
            return json.load(f)

    def verify_contract(self, w3, chain_name, contract_name, contract_address):
        """验证单个合约"""
        print(f"\n{'='*70}")
        print(f"🔍 验证 {chain_name} - {contract_name}")
        print(f"{'='*70}")

        try:
            # 检查合约地址的代码
            code = w3.eth.get_code(contract_address)
            if len(code) == 0:
                print(f"❌ {contract_address} - 未部署合约代码")
                return False

            print(f"✅ 合约地址: {contract_address}")
            print(f"✅ 字节码长度: {len(code)} 字节")

            # 加载ABI并读取状态变量
            abi = self.load_contract_abi(contract_name)
            contract = w3.eth.contract(address=contract_address, abi=abi)

            # 读取公共变量
            print(f"\n📊 状态变量:")
            print("-" * 70)

            # 读取DIDVerifier
            try:
                did_verifier = contract.functions.didVerifier().call()
                print(f"  didVerifier: {did_verifier}")
            except:
                pass

            # 读取跨链桥地址
            try:
                bridge = contract.functions.vcCrossChainBridge().call()
                print(f"  vcCrossChainBridge: {bridge}")
            except:
                pass

            # 读取owner
            try:
                owner = contract.functions.owner().call()
                print(f"  owner: {owner}")
            except:
                pass

            # 读取VC数量
            try:
                vc_count = contract.functions.getVCCount().call()
                print(f"  VC数量: {vc_count}")
            except:
                pass

            return True

        except Exception as e:
            print(f"❌ 验证失败: {str(e)}")
            return False

    def verify_all(self):
        """验证所有合约"""
        print("="*70)
        print("🔍 VC管理合约验证")
        print("="*70)

        results = {
            'verification_timestamp': datetime.now().isoformat(),
            'chains': {}
        }

        # 验证Chain A
        chain_a = self.deployment['chains']['chain_a']
        print(f"\n{'='*70}")
        print(f"📍 验证链: {chain_a['name']}")
        print(f"{'='*70}")

        print(f"\n  DIDVerifier: {chain_a['did_verifier']}")

        w3_a = self.connect_to_chain(chain_a['name'])
        chain_a_results = {'contracts': {}}

        for contract_name, contract_address in chain_a['contracts'].items():
            success = self.verify_contract(
                w3_a,
                chain_a['name'],
                contract_name,
                contract_address
            )
            chain_a_results['contracts'][contract_name] = {
                'address': contract_address,
                'verified': success
            }

        results['chains']['chain_a'] = chain_a_results

        # 验证Chain B
        chain_b = self.deployment['chains']['chain_b']
        print(f"\n{'='*70}")
        print(f"📍 验证链: {chain_b['name']}")
        print(f"{'='*70}")

        print(f"\n  DIDVerifier: {chain_b['did_verifier']}")

        w3_b = self.connect_to_chain(chain_b['name'])
        chain_b_results = {'contracts': {}}

        for contract_name, contract_address in chain_b['contracts'].items():
            success = self.verify_contract(
                w3_b,
                chain_b['name'],
                contract_name,
                contract_address
            )
            chain_b_results['contracts'][contract_name] = {
                'address': contract_address,
                'verified': success
            }

        results['chains']['chain_b'] = chain_b_results

        # 保存结果
        output_path = f"{CONTRACTS_DIR}/vc_managers_verification.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*70}")
        print(f"💾 验证结果已保存到: {output_path}")
        print(f"{'='*70}")

        # 输出摘要
        self.print_summary(results)

        return True

    def print_summary(self, results):
        """打印验证摘要"""
        print(f"\n📊 验证摘要:")
        for chain_key, chain_data in results['chains'].items():
            chain_name = self.deployment['chains'][chain_key]['name']
            print(f"\n  {chain_name}:")
            for contract_name, contract_result in chain_data['contracts'].items():
                status = "✅" if contract_result['verified'] else "❌"
                print(f"    {status} {contract_name}: {contract_result['address']}")


def main():
    print("🚀 VC管理合约验证工具")
    print("="*70)

    verifier = VCManagerVerifier(DEPLOYMENT_INFO, CONFIG_PATH)
    success = verifier.verify_all()

    if success:
        print("\n✅ 验证完成！")
        return 0
    else:
        print("\n❌ 验证失败！")
        return 1


if __name__ == "__main__":
    sys.exit(main())
