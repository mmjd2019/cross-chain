#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
注册合约地址到DIDVerifier
将新部署的合约地址和DID映射注册到两个链的DIDVerifier合约中
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


class DIDMappingRegister:
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

    def load_did_verifier_abi(self):
        """加载DIDVerifier ABI"""
        abi_path = f"{CONTRACTS_DIR}/build/DIDVerifier.abi"
        with open(abi_path, 'r') as f:
            return json.load(f)

    def get_chain_contracts(self, chain_name):
        """从did_address_map.json中获取指定链的合约"""
        chain_key = 'chain_a' if 'Chain A' in chain_name else 'chain_b'

        # 获取DIDVerifier地址
        did_verifier_key = f"Besu Chain {chain_key.split('_')[1].upper()}"
        did_verifier_address = None

        for mapping in self.did_map['mappings']:
            if mapping['address_type'].startswith(f'contract_{chain_key}') and 'Did Verifier' in mapping['address_label']:
                did_verifier_address = mapping['address']
                break

        # 获取需要注册的合约
        contracts_to_register = []

        if chain_key == 'chain_a':
            # Chain A: 5个合约（跨链桥 + 4个VC管理合约）
            target_indices = [22, 24, 25, 26, 27]  # 跨链桥和4个VC Manager
        else:
            # Chain B: 1个合约（跨链桥）
            target_indices = [29]  # Chain B 跨链桥

        for mapping in self.did_map['mappings']:
            if mapping['index'] in target_indices:
                contracts_to_register.append({
                    'address': mapping['address'],
                    'did': mapping['did'],
                    'label': mapping['address_label']
                })

        return did_verifier_address, contracts_to_register

    def register_chain(self, chain_name):
        """注册指定链的合约到DIDVerifier"""
        print(f"\n{'='*70}")
        print(f"📍 注册 {chain_name} 合约到DIDVerifier")
        print(f"{'='*70}")

        w3, chain_config = self.connect_to_chain(chain_name)
        private_key = chain_config['private_key']
        account_address = Web3.to_checksum_address(
            w3.eth.account.from_key(private_key).address
        )

        print(f"\n  部署账户: {account_address}")
        print(f"  账户余额: {w3.from_wei(w3.eth.get_balance(account_address), 'ether')} ETH")

        # 获取合约信息
        did_verifier_address, contracts = self.get_chain_contracts(chain_name)

        print(f"\n  DIDVerifier地址: {did_verifier_address}")
        print(f"\n  需要注册的合约数量: {len(contracts)}")

        # 加载DIDVerifier合约
        abi = self.load_did_verifier_abi()
        did_verifier = w3.eth.contract(address=did_verifier_address, abi=abi)

        # 检查是否是admin
        try:
            is_admin = did_verifier.functions.isAdmin(account_address).call()
            if not is_admin:
                print(f"\n❌ 账户 {account_address} 不是DIDVerifier的admin")
                return False
        except Exception as e:
            print(f"\n⚠️  无法检查admin状态: {str(e)}")

        # 准备批量注册数据
        addresses = []
        dids = []

        for contract in contracts:
            print(f"\n  - {contract['label']}")
            print(f"    地址: {contract['address']}")
            print(f"    DID: {contract['did']}")

            addresses.append(Web3.to_checksum_address(contract['address']))
            dids.append(contract['did'])

        # 批量注册
        print(f"\n📝 开始批量注册...")

        try:
            # 构建交易
            transaction = did_verifier.functions.verifyIdentityBatch(
                addresses, dids
            ).build_transaction({
                'from': account_address,
                'gasPrice': chain_config['gas_price'],
                'gas': chain_config['gas_limit'],
                'nonce': w3.eth.get_transaction_count(account_address),
            })

            # 签名并发送
            signed_txn = w3.eth.account.sign_transaction(transaction, private_key)
            print(f"  交易哈希: {signed_txn.hash.hex()}")

            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            print(f"  等待确认...")

            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if tx_receipt['status'] == 1:
                print(f"  ✅ 批量注册成功!")
            else:
                print(f"  ❌ 注册失败")
                return False

        except Exception as e:
            print(f"  ❌ 注册失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

        # 验证注册结果
        print(f"\n🔍 验证注册结果...")
        all_verified = True

        for i, contract in enumerate(contracts):
            contract_addr = addresses[i]
            expected_did = dids[i]

            try:
                registered_did = did_verifier.functions.getUserDID(contract_addr).call()
                if registered_did == expected_did:
                    print(f"  ✅ {contract['label']}: DID正确")
                else:
                    print(f"  ❌ {contract['label']}: DID不匹配 (期望: {expected_did}, 实际: {registered_did})")
                    all_verified = False
            except Exception as e:
                print(f"  ⚠️  {contract['label']}: 无法验证 ({str(e)})")

        return all_verified

    def register_all(self):
        """注册所有链的合约"""
        print("="*70)
        print("🚀 开始注册合约到DIDVerifier")
        print("="*70)

        results = {
            'registration_timestamp': datetime.now().isoformat(),
            'chains': {}
        }

        # 注册Chain A
        try:
            success = self.register_chain("Besu Chain A")
            results['chains']['chain_a'] = {
                'name': 'Besu Chain A',
                'success': success
            }
        except Exception as e:
            print(f"\n❌ Chain A 注册失败: {str(e)}")
            results['chains']['chain_a'] = {
                'name': 'Besu Chain A',
                'success': False,
                'error': str(e)
            }

        # 注册Chain B
        try:
            success = self.register_chain("Besu Chain B")
            results['chains']['chain_b'] = {
                'name': 'Besu Chain B',
                'success': success
            }
        except Exception as e:
            print(f"\n❌ Chain B 注册失败: {str(e)}")
            results['chains']['chain_b'] = {
                'name': 'Besu Chain B',
                'success': False,
                'error': str(e)
            }

        # 保存结果
        output_path = f"{CONTRACTS_DIR}/did_mapping_registration.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n📄 注册结果已保存到: {output_path}")

        # 打印摘要
        print(f"\n{'='*70}")
        print("📊 注册摘要")
        print(f"{'='*70}")
        for chain_key, chain_result in results['chains'].items():
            status = "✅ 成功" if chain_result['success'] else "❌ 失败"
            print(f"  {chain_result['name']}: {status}")

        return all(r['success'] for r in results['chains'].values())


def main():
    print("🚀 DID映射注册工具")
    print("="*70)

    registrar = DIDMappingRegister(CONFIG_PATH, DID_ADDRESS_MAP_PATH)
    success = registrar.register_all()

    if success:
        print("\n✅ 所有合约注册成功！")
        return 0
    else:
        print("\n❌ 部分合约注册失败！")
        return 1


if __name__ == "__main__":
    sys.exit(main())
