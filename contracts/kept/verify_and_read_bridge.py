#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCCrossChainBridge合约验证和状态读取脚本
验证部署是否成功，并读取合约变量和映射值
"""

import json
import sys
from web3 import Web3
from web3.middleware import geth_poa_middleware
from datetime import datetime

# 配置路径
CONFIG_PATH = "/home/manifold/cursor/cross-chain/config/cross_chain_config.json."
CONTRACTS_DIR = "/home/manifold/cursor/cross-chain/contracts/kept"
DEPLOYMENT_INFO = f"{CONTRACTS_DIR}/vc_bridge_deployment.json"


class BridgeContractVerifier:
    def __init__(self, config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

    def connect_to_chain(self, chain_name):
        """连接到区块链"""
        chain_config = None
        for chain in self.config['chains']:
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

    def verify_deployment(self, chain_name, contract_address, contract_name):
        """验证合约是否部署成功"""
        print(f"\n{'='*70}")
        print(f"🔍 验证 {chain_name} - {contract_name}")
        print(f"{'='*70}")

        w3 = self.connect_to_chain(chain_name)
        abi = self.load_contract_abi(contract_name)
        contract = w3.eth.contract(address=contract_address, abi=abi)

        # 1. 检查合约地址的代码
        code = w3.eth.get_code(contract_address)
        if len(code) == 0:
            print(f"❌ {contract_address} - 未部署合约代码")
            return False

        print(f"✅ 合约地址: {contract_address}")
        print(f"✅ 字节码长度: {len(code)} 字节")

        # 2. 读取状态变量
        print(f"\n📊 状态变量:")
        print("-" * 70)

        state_vars = self.read_state_variables(w3, contract)
        for key, value in state_vars.items():
            print(f"  {key}: {value}")

        # 3. 读取映射数据
        print(f"\n📋 映射数据:")
        print("-" * 70)

        mappings = self.read_mappings(w3, contract)
        for key, value in mappings.items():
            print(f"  {key}: {value}")

        return {
            'chain': chain_name,
            'contract': contract_name,
            'address': contract_address,
            'bytecode_length': len(code),
            'state_variables': state_vars,
            'mappings': mappings
        }

    def read_state_variables(self, w3, contract):
        """读取状态变量"""
        state_vars = {}

        try:
            # 读取owner
            state_vars['owner'] = contract.functions.owner().call()

            # 读取didVerifier地址
            state_vars['didVerifier'] = contract.functions.didVerifier().call()

            # 读取sendListIndexes数组长度
            send_count = contract.functions.getSendListCount().call()
            state_vars['sendListCount'] = send_count

            # 读取receiveListIndexes数组长度
            receive_count = contract.functions.getReceiveListCount().call()
            state_vars['receiveListCount'] = receive_count

        except Exception as e:
            print(f"  ⚠️  读取状态变量时出错: {str(e)}")

        return state_vars

    def read_mappings(self, w3, contract):
        """读取映射数据"""
        mappings = {}

        try:
            # 读取管理员列表（需要遍历）
            mappings['adminList'] = []

            # 读取Oracle DID列表
            # 注意：这是mapping(string => bool)，无法直接遍历
            mappings['oracleDIDList_note'] = "mapping(string => bool) - 无法直接遍历"

            # 读取VC管理合约列表
            # 注意：这是mapping(address => bool)，无法直接遍历
            mappings['vcManagerList_note'] = "mapping(address => bool) - 无法直接遍历"

            # 读取sendListIndexes
            try:
                send_indexes = contract.functions.getSendListIndexes().call()
                mappings['sendListIndexes'] = send_indexes
                mappings['sendListIndexes_count'] = len(send_indexes)
            except:
                mappings['sendListIndexes'] = []

            # 读取receiveListIndexes
            try:
                receive_indexes = contract.functions.getReceiveListIndexes().call()
                mappings['receiveListIndexes'] = receive_indexes
                mappings['receiveListIndexes_count'] = len(receive_indexes)
            except:
                mappings['receiveListIndexes'] = []

            # 读取具体的发送列表记录（如果有数据）
            if send_indexes:
                first_vc_hash = send_indexes[0]
                try:
                    send_record = contract.functions.getSendRecord(first_vc_hash).call()
                    mappings['sampleSendRecord'] = {
                        'vcHash': first_vc_hash,
                        'vcName': send_record[0],
                        'holderDID': send_record[1],
                        'targetChain': send_record[2],
                        'status': 'InProgress' if send_record[3] == 0 else 'Completed',
                        'timestamp': send_record[4],
                        'exists': send_record[5]
                    }
                except Exception as e:
                    mappings['sampleSendRecord'] = f"读取失败: {str(e)}"

        except Exception as e:
            print(f"  ⚠️  读取映射数据时出错: {str(e)}")

        return mappings

    def verify_all_chains(self):
        """验证所有链的合约"""
        print("="*70)
        print("🔍 VCCrossChainBridge 合约验证和状态读取")
        print("="*70)

        # 加载部署信息
        try:
            with open(DEPLOYMENT_INFO, 'r') as f:
                deployment = json.load(f)
        except FileNotFoundError:
            print(f"❌ 找不到部署信息文件: {DEPLOYMENT_INFO}")
            print("   请先运行部署脚本")
            return False

        results = {
            'verification_timestamp': datetime.now().isoformat(),
            'chains': {}
        }

        # 验证每条链
        for chain_key, chain_data in deployment['chains'].items():
            chain_name = chain_data['name']
            contracts = chain_data['contracts']

            print(f"\n{'='*70}")
            print(f"📍 验证链: {chain_name}")
            print(f"{'='*70}")

            chain_results = {}

            # 验证VCCrossChainBridge
            if 'VCCrossChainBridge' in contracts:
                bridge_address = contracts['VCCrossChainBridge']
                result = self.verify_deployment(chain_name, bridge_address, 'VCCrossChainBridge')
                chain_results['VCCrossChainBridge'] = result

            # 验证DIDVerifier
            if 'DIDVerifier' in contracts:
                did_verifier_address = contracts['DIDVerifier']
                result = self.verify_deployment(chain_name, did_verifier_address, 'DIDVerifier')
                chain_results['DIDVerifier'] = result

            results['chains'][chain_key] = {
                'name': chain_name,
                'contracts': chain_results
            }

        # 保存结果到JSON
        self.save_results(results)

        return True

    def save_results(self, results):
        """保存验证结果到JSON"""
        output_path = f"{CONTRACTS_DIR}/bridge_contract_state.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*70}")
        print(f"💾 验证结果已保存到: {output_path}")
        print(f"{'='*70}")

        # 输出摘要
        print(f"\n📊 验证摘要:")
        for chain_key, chain_data in results['chains'].items():
            print(f"\n  {chain_data['name']}:")
            for contract_name, contract_result in chain_data['contracts'].items():
                if isinstance(contract_result, dict) and contract_result.get('bytecode_length'):
                    status = "✅ 部署成功"
                    print(f"    ✅ {contract_name}: {contract_result['address']}")
                    print(f"       - 字节码: {contract_result['bytecode_length']} 字节")
                    print(f"       - 发送列表数量: {contract_result['state_variables'].get('sendListCount', 0)}")
                    print(f"       - 接收列表数量: {contract_result['state_variables'].get('receiveListCount', 0)}")
                else:
                    print(f"    ❌ {contract_name}: {contract_result}")


def main():
    print("🚀 VCCrossChainBridge 合约验证工具")
    print("="*70)

    verifier = BridgeContractVerifier(CONFIG_PATH)
    success = verifier.verify_all_chains()

    if success:
        print("\n✅ 验证完成！")
        return 0
    else:
        print("\n❌ 验证失败！")
        return 1


if __name__ == "__main__":
    sys.exit(main())
