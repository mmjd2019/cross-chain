#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大宗货物跨境交易智能合约验证脚本
验证已部署合约的正确性并进行读取操作测试
"""

import json
import os
import sys
from web3 import Web3
from web3.middleware import geth_poa_middleware

# 配置路径
CONTRACTS_DIR = "/home/manifold/cursor/cross-chain/contracts/kept"
CONFIG_PATH = "/home/manifold/cursor/cross-chain/config/deployed_contracts_config.json"

class ContractVerifier:
    def __init__(self, config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        self.chain_a = self.config['chain_a']
        self.chain_b = self.config['chain_b']

    def connect_to_chain(self, chain_config):
        """连接到区块链"""
        w3 = Web3(Web3.HTTPProvider(chain_config['rpc_url'], request_kwargs={'timeout': 30}))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        # 检查连接
        try:
            block_number = w3.eth.block_number
            print(f"  ✅ 成功连接到 {chain_config['name']}")
            print(f"  当前区块: {block_number}")
            return w3
        except Exception as e:
            print(f"  ❌ 连接失败: {str(e)}")
            return None

    def load_contract(self, w3, contract_name, contract_address):
        """加载合约"""
        abi_file = os.path.join(CONTRACTS_DIR, f"{contract_name}.json")
        if not os.path.exists(abi_file):
            print(f"  ❌ ABI文件不存在: {abi_file}")
            return None

        with open(abi_file, 'r', encoding='utf-8') as f:
            artifact = json.load(f)

        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=artifact['abi']
        )
        return contract

    def verify_contract_code(self, w3, contract_address, contract_name):
        """验证合约代码是否存在"""
        code = w3.eth.get_code(contract_address)
        if len(code) > 0:
            print(f"  ✅ {contract_name} 代码已部署")
            return True
        else:
            print(f"  ❌ {contract_name} 代码未找到")
            return False

    def verify_did_verifier(self, w3, contract_address, chain_name):
        """验证DIDVerifier合约"""
        print(f"\n{'='*70}")
        print(f"验证 {chain_name} - DIDVerifier")
        print(f"{'='*70}")

        contract = self.load_contract(w3, "DIDVerifier", contract_address)
        if not contract:
            return False

        # 验证代码
        self.verify_contract_code(w3, contract_address, "DIDVerifier")

        try:
            # 读取owner
            owner = contract.functions.owner().call()
            print(f"  ✅ Owner: {owner}")

            # 检查admin状态
            is_admin = contract.functions.isAdmin(owner).call()
            print(f"  ✅ Owner是管理员: {is_admin}")

            # 尝试查询不存在的地址
            test_addr = "0x0000000000000000000000000000000000000001"
            is_verified = contract.functions.isVerified(test_addr).call()
            print(f"  ✅ 测试地址验证状态: {is_verified}")

            # 查询owner的验证状态
            owner_verified = contract.functions.isVerified(owner).call()
            print(f"  ✅ Owner验证状态: {owner_verified}")

            return True
        except Exception as e:
            print(f"  ❌ DIDVerifier验证失败: {str(e)}")
            return False

    def verify_contract_manager(self, w3, contract_address, chain_name):
        """验证ContractManager合约"""
        print(f"\n{'='*70}")
        print(f"验证 {chain_name} - ContractManager")
        print(f"{'='*70}")

        contract = self.load_contract(w3, "ContractManager", contract_address)
        if not contract:
            return False

        self.verify_contract_code(w3, contract_address, "ContractManager")

        try:
            # 读取owner
            owner = contract.functions.owner().call()
            print(f"  ✅ Owner: {owner}")

            # 读取didVerifier地址
            did_verifier = contract.functions.didVerifier().call()
            print(f"  ✅ DIDVerifier地址: {did_verifier}")

            # 检查admin状态
            is_admin = contract.functions.isAdmin(owner).call()
            print(f"  ✅ Owner是管理员: {is_admin}")

            # 尝试读取合约数量（可能需要调用权限）
            try:
                count = contract.functions.getContractCount().call()
                print(f"  ✅ 合约数量: {count}")
            except Exception as e:
                if "User not verified" in str(e):
                    print(f"  ⚠️  需要验证权限才能读取合约数量（正常）")
                else:
                    raise

            return True
        except Exception as e:
            print(f"  ❌ ContractManager验证失败: {str(e)}")
            return False

    def verify_vc_cross_chain_bridge(self, w3, contract_address, chain_name):
        """验证VCCrossChainBridge合约"""
        print(f"\n{'='*70}")
        print(f"验证 {chain_name} - VCCrossChainBridge")
        print(f"{'='*70}")

        contract = self.load_contract(w3, "VCCrossChainBridge", contract_address)
        if not contract:
            return False

        self.verify_contract_code(w3, contract_address, "VCCrossChainBridge")

        try:
            # 读取owner
            owner = contract.functions.owner().call()
            print(f"  ✅ Owner: {owner}")

            # 读取didVerifier地址
            did_verifier = contract.functions.didVerifier().call()
            print(f"  ✅ DIDVerifier地址: {did_verifier}")

            # 检查admin状态
            is_admin = contract.functions.isAdmin(owner).call()
            print(f"  ✅ Owner是管理员: {is_admin}")

            # 尝试读取VC数量
            try:
                send_count = contract.functions.getSendVCCount().call()
                print(f"  ✅ 发送VC数量: {send_count}")
            except Exception:
                print(f"  ⚠️  发送VC列表为空或需要权限")

            try:
                receive_count = contract.functions.getReceiveVCCount().call()
                print(f"  ✅ 接收VC数量: {receive_count}")
            except Exception:
                print(f"  ⚠️  接收VC列表为空或需要权限")

            return True
        except Exception as e:
            print(f"  ❌ VCCrossChainBridge验证失败: {str(e)}")
            return False

    def verify_vc_manager(self, w3, contract_address, contract_name, vc_type, chain_name):
        """验证VCManager合约"""
        print(f"\n{'='*70}")
        print(f"验证 {chain_name} - {contract_name}")
        print(f"{'='*70}")

        contract = self.load_contract(w3, contract_name, contract_address)
        if not contract:
            return False

        self.verify_contract_code(w3, contract_address, contract_name)

        try:
            # 读取owner
            owner = contract.functions.owner().call()
            print(f"  ✅ Owner: {owner}")

            # 读取didVerifier地址
            did_verifier = contract.functions.didVerifier().call()
            print(f"  ✅ DIDVerifier地址: {did_verifier}")

            # 读取bridge地址
            bridge = contract.functions.vcCrossChainBridge().call()
            print(f"  ✅ Bridge地址: {bridge}")

            # 检查admin状态
            is_admin = contract.functions.isAdmin(owner).call()
            print(f"  ✅ Owner是管理员: {is_admin}")

            # 尝试读取VC数量
            try:
                vc_count = contract.functions.getVCCount().call()
                print(f"  ✅ VC数量: {vc_count}")
            except Exception as e:
                if "not verified" in str(e).lower():
                    print(f"  ⚠️  需要验证权限才能读取VC数量（正常）")
                else:
                    print(f"  ⚠️  VC列表为空或需要权限")

            return True
        except Exception as e:
            print(f"  ❌ {contract_name}验证失败: {str(e)}")
            return False

    def verify_chain_a(self):
        """验证Chain A的所有合约"""
        print("\n" + "="*70)
        print("🔍 开始验证 Chain A")
        print("="*70)

        w3 = self.connect_to_chain(self.chain_a)
        if not w3:
            return False

        contracts = self.chain_a['contracts']
        results = {}

        # 验证DIDVerifier
        results['DIDVerifier'] = self.verify_did_verifier(
            w3,
            contracts['DIDVerifier']['address'],
            "Chain A"
        )

        # 验证ContractManager
        results['ContractManager'] = self.verify_contract_manager(
            w3,
            contracts['ContractManager']['address'],
            "Chain A"
        )

        # 验证VCCrossChainBridge
        results['VCCrossChainBridge'] = self.verify_vc_cross_chain_bridge(
            w3,
            contracts['VCCrossChainBridge']['address'],
            "Chain A"
        )

        # 验证4个VCManager
        for vc_name in ['InspectionReportVCManager', 'InsuranceContractVCManager',
                       'CertificateOfOriginVCManager', 'BillOfLadingVCManager']:
            results[vc_name] = self.verify_vc_manager(
                w3,
                contracts[vc_name]['address'],
                vc_name,
                contracts[vc_name]['vc_type'],
                "Chain A"
            )

        # 统计结果
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)

        print(f"\n{'='*70}")
        print(f"Chain A 验证完成: {success_count}/{total_count} 个合约验证通过")
        print(f"{'='*70}")

        return success_count == total_count

    def verify_chain_b(self):
        """验证Chain B的所有合约"""
        print("\n" + "="*70)
        print("🔍 开始验证 Chain B")
        print("="*70)

        w3 = self.connect_to_chain(self.chain_b)
        if not w3:
            return False

        contracts = self.chain_b['contracts']
        results = {}

        # 验证DIDVerifier
        results['DIDVerifier'] = self.verify_did_verifier(
            w3,
            contracts['DIDVerifier']['address'],
            "Chain B"
        )

        # 验证VCCrossChainBridge
        results['VCCrossChainBridge'] = self.verify_vc_cross_chain_bridge(
            w3,
            contracts['VCCrossChainBridge']['address'],
            "Chain B"
        )

        # 统计结果
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)

        print(f"\n{'='*70}")
        print(f"Chain B 验证完成: {success_count}/{total_count} 个合约验证通过")
        print(f"{'='*70}")

        return success_count == total_count

    def verify_all(self):
        """验证所有合约"""
        print("="*70)
        print("🔍 大宗货物跨境交易智能合约验证工具")
        print("="*70)

        try:
            # 验证Chain A
            chain_a_success = self.verify_chain_a()

            # 验证Chain B
            chain_b_success = self.verify_chain_b()

            # 最终结果
            print("\n" + "="*70)
            print("🎉 验证总结")
            print("="*70)
            print(f"Chain A: {'✅ 通过' if chain_a_success else '❌ 失败'}")
            print(f"Chain B: {'✅ 通过' if chain_b_success else '❌ 失败'}")

            if chain_a_success and chain_b_success:
                print("\n✅ 所有合约验证通过！系统可以正常使用。")
                return True
            else:
                print("\n⚠️  部分合约验证失败，请检查部署。")
                return False

        except Exception as e:
            print(f"\n❌ 验证过程出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ 配置文件不存在: {CONFIG_PATH}")
        sys.exit(1)

    verifier = ContractVerifier(CONFIG_PATH)
    success = verifier.verify_all()
    sys.exit(0 if success else 1)
