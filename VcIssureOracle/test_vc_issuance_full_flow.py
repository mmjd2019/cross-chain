#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VC发行验证脚本
从 uuid.json 读取最新的 n 个记录，验证 Holder 存储和链上写入

使用方法:
    python3 test_vc_issuance_full_flow.py              # 验证最新1条记录
    python3 test_vc_issuance_full_flow.py -n 5          # 验证最新5条记录
    python3 test_vc_issuance_full_flow.py --all         # 验证所有记录
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from web3 import Web3

# 配置
ORACLE_URL = "http://localhost:6000"
HOLDER_URL = "http://localhost:8081"
ISSUER_URL = "http://localhost:8080"
UUID_FILE = Path(__file__).parent / "logs" / "uuid.json"
CONFIG_FILE = Path(__file__).parent / "vc_issuance_config.json"
OUTPUT_DIR = Path(__file__).parent / "logs"


class VCVerifier:
    """VC验证器"""

    def __init__(self):
        self.config = self._load_config()
        self.w3 = None
        self.contracts = {}
        self._init_web3()
        self._init_contracts()

    def _load_config(self) -> Dict:
        """加载配置"""
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _init_web3(self):
        """初始化Web3"""
        rpc_url = self.config.get('blockchain', {}).get('rpc_url', 'http://localhost:8545')
        try:
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
            # 尝试实际调用来验证连接（is_connected() 可能不可靠）
            self.w3.eth.block_number
        except Exception:
            self.w3 = None

    def _load_contract_abi(self, contract_name: str) -> Optional[List]:
        """加载合约ABI"""
        abi_path = Path(__file__).parent.parent / "contracts" / "kept" / "contract_abis" / f"{contract_name}.json"
        if abi_path.exists():
            with open(abi_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('abi', data)
        return None

    def _init_contracts(self):
        """初始化合约实例"""
        if not self.w3:
            return

        for vc_type, vc_config in self.config.get('vc_types', {}).items():
            contract_address = vc_config.get('contract_address')
            contract_name = vc_config.get('contract_name')

            if contract_address and contract_name:
                abi = self._load_contract_abi(contract_name)
                if abi:
                    self.contracts[vc_type] = self.w3.eth.contract(
                        address=Web3.to_checksum_address(contract_address),
                        abi=abi
                    )

    def load_uuid_records(self, n: int = 1) -> List[Tuple[str, Dict]]:
        """从uuid.json加载最新的n条记录"""
        if not UUID_FILE.exists():
            return []

        with open(UUID_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 按时间戳排序（最新的在前）
        records = []
        for uuid, info in data.items():
            records.append((uuid, info))

        records.sort(key=lambda x: x[1].get('timestamp', ''), reverse=True)

        if n > 0:
            return records[:n]
        return records

    def find_uuid_by_vc_hash(self, vc_hash: str) -> Optional[Tuple[str, Dict]]:
        """通过vc_hash反向查找uuid（不需要区块链连接）"""
        if not UUID_FILE.exists():
            return None

        with open(UUID_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 遍历查找匹配的vc_hash
        for uuid, info in data.items():
            if info.get('vc_hash', '').lower() == vc_hash.lower():
                return (uuid, info)

        return None

    def get_holder_credentials(self, start: int = 0, count: int = 1000) -> List[Dict]:
        """获取 Holder 的所有凭证（支持分页）

        重要：ACA-Py 使用 start/count 参数，不是 limit/offset
        默认 count=1000 确保获取所有凭证

        Args:
            start: 起始索引，默认 0
            count: 返回记录数，默认 1000

        Returns:
            凭证列表
        """
        try:
            resp = requests.get(
                f"{HOLDER_URL}/credentials",
                params={"start": start, "count": count},
                timeout=30
            )
            if resp.status_code == 200:
                return resp.json().get('results', [])
        except Exception as e:
            print(f"获取凭证失败：{e}")
        return []


    def verify_holder_storage(self, vc_uuid: str) -> Tuple[bool, Optional[Dict]]:
        """验证 Holder 是否存储了 VC（使用正确的分页参数）

        Args:
            vc_uuid: 凭证 UUID（即 contractName）

        Returns:
            Tuple[是否找到，凭证信息]
        """
        # 使用 start/count 参数获取所有凭证（默认最多 1000 条）
        creds = self.get_holder_credentials(start=0, count=1000)

        for cred in creds:
            attrs = cred.get('attrs', {})
            # 通过 contractName 字段匹配 UUID
            if attrs.get('contractName') == vc_uuid:
                return True, {
                    'referent': cred.get('referent'),
                    'schema_id': cred.get('schema_id'),
                    'cred_def_id': cred.get('cred_def_id'),
                    'attrs': attrs
                }
        return False, None


    def verify_blockchain(self, tx_hash: str) -> Tuple[bool, Optional[Dict]]:
        """验证区块链交易"""
        if not self.w3:
            return False, {'error': 'Web3未连接'}

        try:
            # tx_hash 已经是 0x 开头的格式，直接使用
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            if receipt and receipt.status == 1:
                return True, {
                    'block_number': receipt.blockNumber,
                    'gas_used': receipt.gasUsed,
                    'contract_address': receipt.contractAddress
                }
            return False, {'error': '交易未确认或失败'}
        except Exception as e:
            return False, {'error': str(e)}

    def get_vc_metadata_from_chain(self, vc_hash: str, vc_type: str = 'InspectionReport') -> Tuple[bool, Optional[Dict]]:
        """从链上通过vc_hash获取VC元数据（真正的链上验证）"""
        if not self.w3:
            return False, {'error': 'Web3未连接', 'uuid': None}

        if vc_type not in self.contracts:
            return False, {'error': f'合约 {vc_type} 未初始化', 'uuid': None}

        try:
            contract = self.contracts[vc_type]

            # 将 vc_hash 转换为 bytes32
            if vc_hash.startswith('0x'):
                vc_hash_bytes = bytes.fromhex(vc_hash[2:])
            else:
                vc_hash_bytes = bytes.fromhex(vc_hash)

            # 获取 Oracle 地址（已验证的用户）作为调用者
            vc_config = self.config.get('vc_types', {}).get(vc_type, {})
            oracle_address = vc_config.get('oracle_address')

            # 调用合约的 getVCMetadata 方法
            if oracle_address:
                result = contract.functions.getVCMetadata(vc_hash_bytes).call({
                    'from': Web3.to_checksum_address(oracle_address)
                })
            else:
                result = contract.functions.getVCMetadata(vc_hash_bytes).call()

            # 解析返回值
            (vc_hash_ret, vc_name, vc_description, issuer_endpoint, issuer_did,
             holder_endpoint, holder_did, blockchain_endpoint, vc_manager_address,
             blockchain_type, expiry_time, exists) = result

            if not exists:
                return False, {'error': 'VC不存在于链上', 'uuid': None}

            # 从 vcName 中解析 UUID（格式: "{vcName} (UUID: {uuid})"）
            uuid = None
            if vc_name and 'UUID:' in vc_name:
                import re
                match = re.search(r'UUID:\s*([a-f0-9\-]{36})', vc_name)
                if match:
                    uuid = match.group(1)

            metadata = {
                'vc_hash': vc_hash_ret.hex() if isinstance(vc_hash_ret, bytes) else vc_hash_ret,
                'vc_name': vc_name,
                'vc_description': vc_description,
                'issuer_endpoint': issuer_endpoint,
                'issuer_did': issuer_did,
                'holder_endpoint': holder_endpoint,
                'holder_did': holder_did,
                'blockchain_endpoint': blockchain_endpoint,
                'vc_manager_address': vc_manager_address,
                'blockchain_type': blockchain_type,
                'expiry_time': expiry_time,
                'uuid': uuid
            }

            return True, metadata

        except Exception as e:
            return False, {'error': str(e), 'uuid': None}

    def check_services(self) -> Dict[str, bool]:
        """检查服务状态"""
        services = {
            'oracle': False,
            'issuer': False,
            'holder': False,
            'blockchain': False
        }

        # Oracle
        try:
            resp = requests.get(f"{ORACLE_URL}/health", timeout=5)
            services['oracle'] = resp.status_code == 200
        except Exception:
            pass

        # Issuer
        try:
            resp = requests.get(f"{ISSUER_URL}/status", timeout=5)
            services['issuer'] = resp.status_code == 200
        except Exception:
            pass

        # Holder
        try:
            resp = requests.get(f"{HOLDER_URL}/status", timeout=5)
            services['holder'] = resp.status_code == 200
        except Exception:
            pass

        # Blockchain
        if self.w3:
            try:
                self.w3.eth.block_number
                services['blockchain'] = True
            except Exception:
                services['blockchain'] = False

        return services


def generate_markdown_report(results: List[Dict], output_path: Path) -> None:
    """生成Markdown验证报告"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    lines = [
        "# VC发行验证报告",
        "",
        f"**验证时间**: {now}",
        f"**验证数量**: {len(results)}",
        "",
        "---",
        ""
    ]

    # 汇总统计
    success_count = sum(1 for r in results if r.get('holder_verified') and r.get('blockchain_verified'))
    holder_success = sum(1 for r in results if r.get('holder_verified'))
    blockchain_success = sum(1 for r in results if r.get('blockchain_verified'))

    lines.extend([
        "## 验证汇总",
        "",
        "| 指标 | 结果 |",
        "|------|------|",
        f"| 完全验证成功 | {success_count}/{len(results)} |",
        f"| Holder存储验证 | {holder_success}/{len(results)} |",
        f"| 区块链验证 | {blockchain_success}/{len(results)} |",
        "",
        "---",
        ""
    ])

    # 详细结果
    lines.append("## 详细验证结果")
    lines.append("")

    for i, result in enumerate(results, 1):
        vc_uuid = result.get('vc_uuid', 'unknown')
        record = result.get('record', {})

        lines.append(f"### {i}. VC UUID: `{vc_uuid}`")
        lines.append("")
        lines.append("**基本信息**:")
        lines.append("")
        lines.append(f"- 时间戳: {record.get('timestamp', 'N/A')}")
        lines.append(f"- VC类型: {record.get('vc_type', 'N/A')}")
        lines.append(f"- 原始合同名: {record.get('original_contract_name', 'N/A')}")
        lines.append(f"- Request ID: `{record.get('request_id', 'N/A')}`")
        lines.append("")
        lines.append(f"- VC Hash: `{record.get('vc_hash', 'N/A')}`")
        lines.append(f"- TX Hash: `{record.get('tx_hash', 'N/A')}`")
        lines.append("")

        # 链上元数据验证结果
        chain_status = "✅ 通过" if result.get('chain_metadata_verified') else "❌ 失败"
        lines.append(f"**链上元数据验证**: {chain_status}")
        lines.append("")

        chain_info = result.get('chain_metadata', {})
        if chain_info and not chain_info.get('error'):
            lines.append("| 字段 | 值 |")
            lines.append("|------|-----|")
            lines.append(f"| 链上UUID | `{chain_info.get('uuid', 'N/A')}` |")
            lines.append(f"| vcName | {chain_info.get('vc_name', 'N/A')[:60]}... |")
            lines.append(f"| Issuer DID | `{chain_info.get('issuer_did', 'N/A')}` |")
            lines.append(f"| Holder DID | `{chain_info.get('holder_did', 'N/A')}` |")
            lines.append(f"| 过期时间 | {chain_info.get('expiry_time', 'N/A')} |")

            uuid_match = result.get('uuid_match')
            if uuid_match is True:
                lines.append(f"| UUID一致性 | ✅ 匹配 |")
            elif uuid_match is False:
                lines.append(f"| UUID一致性 | ❌ 不匹配 |")
            else:
                lines.append(f"| UUID一致性 | ⚠️ 无法验证 |")
            lines.append("")
        elif chain_info.get('error'):
            lines.append(f"错误: {chain_info.get('error')}")
            lines.append("")

        # Holder验证结果
        holder_status = "✅ 通过" if result.get('holder_verified') else "❌ 失败"
        lines.append(f"**Holder存储验证**: {holder_status}")
        lines.append("")

        holder_info = result.get('holder_info', {})
        if holder_info:
            lines.append("| 字段 | 值 |")
            lines.append("|------|-----|")
            lines.append(f"| Referent | `{holder_info.get('referent', 'N/A')}` |")
            lines.append(f"| Schema ID | `{holder_info.get('schema_id', 'N/A')}` |")
            lines.append(f"| CredDef ID | `{holder_info.get('cred_def_id', 'N/A')}` |")
            lines.append("")

            if holder_info.get('attrs'):
                lines.append("**凭证属性**:")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(holder_info.get('attrs'), ensure_ascii=False, indent=2))
                lines.append("```")
                lines.append("")
        elif result.get('holder_error'):
            lines.append(f"错误: {result.get('holder_error')}")
            lines.append("")

        # 区块链验证结果
        bc_status = "✅ 通过" if result.get('blockchain_verified') else "❌ 失败"
        lines.append(f"**交易验证**: {bc_status}")
        lines.append("")

        bc_info = result.get('blockchain_info', {})
        if bc_info and not bc_info.get('error'):
            lines.append("| 字段 | 值 |")
            lines.append("|------|-----|")
            lines.append(f"| 区块高度 | {bc_info.get('block_number', 'N/A')} |")
            lines.append(f"| Gas消耗 | {bc_info.get('gas_used', 'N/A')} |")
            lines.append("")
        elif bc_info.get('error'):
            lines.append(f"错误: {bc_info.get('error')}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description='VC发行验证脚本')
    parser.add_argument('-n', '--count', type=int, default=1,
                        help='验证最新n条记录 (默认: 1)')
    parser.add_argument('--all', action='store_true',
                        help='验证所有记录')
    parser.add_argument('--vc-hash', type=str, default=None,
                        help='通过vc_hash查找并验证指定记录')
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='输出文件路径 (默认: logs/vc_verification_report.md)')
    parser.add_argument('--skip-services', action='store_true',
                        help='跳过服务检查')

    args = parser.parse_args()

    print("=" * 60)
    print(" VC发行验证脚本")
    print("=" * 60)

    # 初始化验证器
    verifier = VCVerifier()

    # 检查服务
    if not args.skip_services:
        print("\n[检查服务状态]")
        services = verifier.check_services()
        for name, status in services.items():
            mark = "✅" if status else "❌"
            print(f"  {mark} {name}: {'运行中' if status else '未连接'}")

        # 只有验证Holder需要服务在线，区块链验证可以离线
        if not services.get('holder'):
            print("\n警告: Holder服务未连接，无法验证Holder存储")

    # 加载记录
    print(f"\n[加载UUID记录]")

    # 确定加载方式
    if args.vc_hash:
        # 通过vc_hash查找
        result = verifier.find_uuid_by_vc_hash(args.vc_hash)
        if result:
            records = [result]
            print(f"  通过vc_hash找到记录: {result[0]}")
        else:
            print(f"  错误: 未找到vc_hash={args.vc_hash}的记录")
            sys.exit(1)
    else:
        # 按数量加载最新记录
        n = 0 if args.all else args.count
        records = verifier.load_uuid_records(n)
        print(f"  找到 {len(records)} 条记录")

    if not records:
        print("\n错误: 没有找到任何VC记录")
        sys.exit(1)

    # 验证每条记录
    print(f"\n[开始验证]")
    results = []

    for i, (vc_uuid, record) in enumerate(records, 1):
        print(f"\n  验证 {i}/{len(records)}: {vc_uuid[:20]}...")

        result = {
            'vc_uuid': vc_uuid,
            'record': record,
            'holder_verified': False,
            'blockchain_verified': False,
            'chain_metadata_verified': False
        }

        vc_hash = record.get('vc_hash', '')
        vc_type = record.get('vc_type', 'InspectionReport')

        # 步骤1: 从链上获取VC元数据（真正的链上验证）
        print(f"    [步骤1] 从链上查询VC元数据...")
        if vc_hash:
            chain_ok, chain_info = verifier.get_vc_metadata_from_chain(vc_hash, vc_type)
            result['chain_metadata_verified'] = chain_ok
            result['chain_metadata'] = chain_info

            if chain_ok:
                # 从链上获取的 uuid
                chain_uuid = chain_info.get('uuid')
                print(f"    ✅ 链上元数据查询成功")
                print(f"       vcName: {chain_info.get('vc_name', '')[:50]}...")
                print(f"       链上UUID: {chain_uuid}")

                # 验证链上UUID与本地UUID是否一致
                if chain_uuid and chain_uuid == vc_uuid:
                    print(f"       ✅ UUID一致性验证通过")
                    result['uuid_match'] = True
                elif chain_uuid:
                    print(f"       ⚠️ UUID不一致! 本地={vc_uuid}, 链上={chain_uuid}")
                    result['uuid_match'] = False
                else:
                    print(f"       ⚠️ 链上未找到UUID")
                    result['uuid_match'] = None

                # 使用链上的UUID验证Holder
                verify_uuid = chain_uuid or vc_uuid
            else:
                print(f"    ❌ 链上元数据查询失败: {chain_info.get('error')}")
                verify_uuid = vc_uuid
        else:
            print(f"    ⚠️ 跳过链上查询 (无vc_hash)")
            verify_uuid = vc_uuid

        # 步骤2: 验证Holder存储
        print(f"    [步骤2] 验证Holder存储...")
        holder_ok, holder_info = verifier.verify_holder_storage(verify_uuid)
        result['holder_verified'] = holder_ok
        if holder_ok:
            result['holder_info'] = holder_info
            print(f"    ✅ Holder存储验证通过")
        else:
            result['holder_error'] = '未找到匹配的凭证'
            print(f"    ❌ Holder存储验证失败")

        # 步骤3: 验证区块链交易
        print(f"    [步骤3] 验证区块链交易...")
        tx_hash = record.get('tx_hash', '')
        if tx_hash:
            bc_ok, bc_info = verifier.verify_blockchain(tx_hash)
            result['blockchain_verified'] = bc_ok
            result['blockchain_info'] = bc_info
            if bc_ok:
                print(f"    ✅ 交易验证通过 (区块: {bc_info.get('block_number')})")
            else:
                print(f"    ❌ 交易验证失败: {bc_info.get('error')}")
        else:
            result['blockchain_error'] = '缺少tx_hash'
            print(f"    ⚠️ 跳过交易验证 (无tx_hash)")

        results.append(result)

    # 生成报告
    output_path = Path(args.output) if args.output else OUTPUT_DIR / "vc_verification_report.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generate_markdown_report(results, output_path)

    print(f"\n{'=' * 60}")
    print(f" 验证完成")
    print(f"{'=' * 60}")

    # 汇总
    success = sum(1 for r in results if r.get('holder_verified') and r.get('blockchain_verified'))
    print(f"  验证数量: {len(results)}")
    print(f"  完全成功: {success}")
    print(f"  报告文件: {output_path}")

    sys.exit(0 if success == len(results) else 1)


if __name__ == "__main__":
    main()
