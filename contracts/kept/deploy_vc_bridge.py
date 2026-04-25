#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCCrossChainBridge合约部署脚本
部署VCCrossChainBridge到Chain A和Chain B
"""

import json
import os
import sys
from web3 import Web3
from web3.middleware import geth_poa_middleware
from datetime import datetime

# 配置路径
CONFIG_PATH = "/home/manifold/cursor/cross-chain/config/cross_chain_config.json."
CONTRACTS_DIR = "/home/manifold/cursor/cross-chain/contracts/kept"
DID_ADDRESS_MAP_PATH = "/home/manifold/cursor/cross-chain/config/did_address_map.json"


class VCBridgeDeployer:
    def __init__(self, config_path, did_address_map_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.chains = self.config['chains']
        self.deployed_contracts = {}

        # 加载DID地址映射
        with open(did_address_map_path, 'r', encoding='utf-8') as f:
            did_map = json.load(f)

        # 提取各链的DIDVerifier地址
        self.did_verifier_addresses = {}
        for mapping in did_map['mappings']:
            if mapping['address_type'] == 'contract_chain_a' and mapping['address_label'] == 'Chain A Did Verifier':
                self.did_verifier_addresses['Besu Chain A'] = mapping['address']
            elif mapping['address_type'] == 'contract_chain_b' and mapping['address_label'] == 'Chain B Did Verifier':
                self.did_verifier_addresses['Besu Chain B'] = mapping['address']

        print(f"\n📍 从did_address_map.json读取到的DIDVerifier地址:")
        for chain, addr in self.did_verifier_addresses.items():
            print(f"  {chain}: {addr}")

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
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        try:
            w3.eth.get_block('latest')
        except Exception as e:
            raise ConnectionError(f"无法连接到 {chain_config['name']}: {str(e)}")

        account_address = Web3.to_checksum_address(
            w3.eth.account.from_key(chain_config['private_key']).address
        )
        balance = w3.eth.get_balance(account_address)

        print(f"  链: {chain_config['name']}")
        print(f"  RPC: {chain_config['rpc_url']}")
        print(f"  部署账户: {account_address}")
        print(f"  账户余额: {w3.from_wei(balance, 'ether')} ETH")

        if balance == 0:
            raise ValueError(f"账户 {account_address} 余额为0，无法部署合约")

        return w3, account_address

    def deploy_contract(self, w3, account_address, private_key, contract_name, constructor_args, chain_config):
        """部署单个合约"""
        print(f"\n📦 部署 {contract_name}...")

        # 加载合约ABI和字节码
        abi, bytecode = self.load_contract_artifact(contract_name)
        contract = w3.eth.contract(abi=abi, bytecode=bytecode)

        # 构建交易
        transaction = contract.constructor(*constructor_args).build_transaction({
            'from': account_address,
            'gasPrice': chain_config['gas_price'],
            'gas': chain_config['gas_limit'],
            'nonce': w3.eth.get_transaction_count(account_address),
        })

        # 签名并发送交易
        signed_txn = w3.eth.account.sign_transaction(transaction, private_key)
        print(f"  交易哈希: {signed_txn.hash.hex()}")
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

        # 等待确认
        print(f"  等待确认...")
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if tx_receipt['status'] == 1:
            contract_address = tx_receipt['contractAddress']
            print(f"  ✅ {contract_name} 部署成功!")
            print(f"  合约地址: {contract_address}")
            return contract_address
        else:
            raise Exception(f"{contract_name} 部署失败")

    def deploy_to_chain(self, chain_name):
        """部署到指定链"""
        print("\n" + "="*70)
        print(f"🚀 开始部署到 {chain_name}")
        print("="*70)

        chain_config = None
        for chain in self.chains:
            if chain['name'] == chain_name:
                chain_config = chain
                break

        if not chain_config:
            raise ValueError(f"未找到链配置: {chain_name}")

        w3, account_address = self.connect_to_chain(chain_config)
        private_key = chain_config['private_key']

        chain_contracts = {}

        # 使用该链自己的DIDVerifier地址
        did_verifier_address = self.did_verifier_addresses.get(chain_name)
        if did_verifier_address:
            print(f"\n✅ 使用该链的DIDVerifier: {did_verifier_address}")
        else:
            raise ValueError(f"未找到 {chain_name} 的DIDVerifier地址")

        chain_contracts['DIDVerifier'] = did_verifier_address

        # 部署VCCrossChainBridge
        print("\n" + "-"*70)
        print("1/1 部署 VCCrossChainBridge")
        print("-"*70)
        bridge_address = self.deploy_contract(
            w3, account_address, private_key,
            "VCCrossChainBridge",
            [did_verifier_address],  # 构造函数参数
            chain_config
        )
        chain_contracts['VCCrossChainBridge'] = bridge_address

        self.deployed_contracts[chain_name] = {
            'name': chain_name,
            'rpc_url': chain_config['rpc_url'],
            'contracts': chain_contracts
        }

        print("\n" + "="*70)
        print(f"✅ {chain_name} 部署完成! 共部署 {len(chain_contracts)} 个合约")
        print("="*70)

        return chain_contracts

    def save_deployment_info(self):
        """保存部署信息"""
        deployment_info = {
            'deployment_timestamp': datetime.now().isoformat(),
            'chains': self.deployed_contracts
        }

        output_path = os.path.join(CONTRACTS_DIR, 'vc_bridge_deployment.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(deployment_info, f, indent=2, ensure_ascii=False)

        print(f"\n📄 部署信息已保存到: {output_path}")


def main():
    print("="*70)
    print("🚀 VCCrossChainBridge合约部署工具")
    print("="*70)
    print("\n📋 部署计划:")
    print("  Chain A: VCCrossChainBridge (使用Chain A的DIDVerifier)")
    print("  Chain B: VCCrossChainBridge (使用Chain B的DIDVerifier)")
    print("="*70)

    deployer = VCBridgeDeployer(CONFIG_PATH, DID_ADDRESS_MAP_PATH)

    try:
        # 部署到Chain A（使用Chain A的DIDVerifier）
        chain_a_contracts = deployer.deploy_to_chain("Besu Chain A")

        # 部署到Chain B（使用Chain B的DIDVerifier）
        chain_b_contracts = deployer.deploy_to_chain("Besu Chain B")

        # 保存部署信息
        deployer.save_deployment_info()

        print("\n" + "="*70)
        print("🎉 所有合约部署完成!")
        print("="*70)
        print(f"\n📊 部署总结:")
        print(f"  Chain A DIDVerifier: {chain_a_contracts['DIDVerifier']}")
        print(f"  Chain A VCCrossChainBridge: {chain_a_contracts['VCCrossChainBridge']}")
        print(f"  Chain B DIDVerifier: {chain_b_contracts['DIDVerifier']}")
        print(f"  Chain B VCCrossChainBridge: {chain_b_contracts['VCCrossChainBridge']}")

        return True

    except Exception as e:
        print(f"\n❌ 部署失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
