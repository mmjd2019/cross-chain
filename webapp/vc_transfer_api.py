#!/usr/bin/env python3
"""
VC 跨链传输 API 模块

实现与 test_vc_transfer_oracle.py 脚本相同的功能：
1. 从 uuid.json 读取已发行的 VC 记录
2. 发起跨链传输 (initiateCrossChainTransfer)
3. 等待 Oracle 传输到目标链
4. 验证目标链是否收到
"""

import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
from web3 import Web3
from web3.middleware import geth_poa_middleware

# uuid.json 文件路径
UUID_JSON_PATH = '/home/manifold/cursor/cross-chain-new/VcIssureOracle/logs/uuid.json'

# 配置文件路径
CROSS_CHAIN_ORACLE_CONFIG_PATH = '/home/manifold/cursor/cross-chain-new/config/cross_chain_oracle_config.json'
VC_ISSUANCE_CONFIG_PATH = '/home/manifold/cursor/cross-chain-new/VcIssureOracle/vc_issuance_config.json'

logger = logging.getLogger(__name__)


class VCCrossChainService:
    """VC 跨链传输服务类"""

    def __init__(self):
        """初始化服务"""
        self.config = self._load_config()
        self.vc_issuance_config = self._load_vc_issuance_config()
        self.connections = {}

    def _load_config(self) -> Dict:
        """加载跨链配置"""
        try:
            with open(CROSS_CHAIN_ORACLE_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载跨链配置失败：{e}")
            return {}

    def _load_vc_issuance_config(self) -> Dict:
        """加载 VC 发行配置"""
        try:
            with open(VC_ISSUANCE_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载 VC 发行配置失败：{e}")
            return {}

    def _get_chain_connection(self, chain_key: str) -> Optional[Web3]:
        """获取链连接"""
        if chain_key in self.connections:
            return self.connections[chain_key]

        chain_config = self.config.get('chains', {}).get(chain_key)
        if not chain_config:
            return None

        try:
            w3 = Web3(Web3.HTTPProvider(chain_config['rpc_url']))
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)

            # 测试连接
            chain_id = w3.eth.chain_id
            self.connections[chain_key] = w3
            return w3
        except Exception as e:
            logger.error(f"连接 {chain_key} 失败：{e}")
            return None

    def _get_vc_manager_owner(self) -> Dict:
        """获取 VC Manager Owner 账户配置"""
        return self.config.get('vc_manager_owner', {})

    def _get_vc_manager_config(self, vc_type: str) -> Dict:
        """根据 VC 类型获取对应的 VC Manager 配置"""
        vc_type_to_key = {
            'InspectionReport': 'InspectionReportVCManager',
            'InsuranceContract': 'InsuranceContractVCManager',
            'CertificateOfOrigin': 'CertificateOfOriginVCManager',
            'BillOfLadingCertificate': 'BillOfLadingVCManager'
        }

        config_key = vc_type_to_key.get(vc_type)
        if not config_key:
            raise ValueError(f"未知的 VC 类型：{vc_type}")

        vc_managers = self.config.get('vc_managers', {}).get('chain_a', {})
        if config_key not in vc_managers:
            raise ValueError(f"未找到 VC Manager 配置：{config_key}")

        vc_manager_info = vc_managers[config_key]
        owner_config = self._get_vc_manager_owner()

        return {
            'vc_manager_address': vc_manager_info.get('address'),
            'vc_manager_did': vc_manager_info.get('did'),
            'vc_manager_name': config_key,
            'caller_address': owner_config.get('address'),
            'caller_private_key': owner_config.get('private_key'),
            'vc_type': vc_type
        }

    def _get_vc_type_attributes(self, vc_type: str) -> list:
        """获取指定 VC 类型的属性列表"""
        vc_types = self.vc_issuance_config.get('vc_types', {})
        return vc_types.get(vc_type, {}).get('attributes', [])

    def _get_acapy_config(self) -> Dict:
        """获取 ACA-Py 配置"""
        return self.vc_issuance_config.get('acapy', {})

    def _load_contract_abi(self, contract_name: str) -> list:
        """加载合约 ABI"""
        possible_paths = [
            Path('/home/manifold/cursor/cross-chain-new/contracts/kept/contract_abis') / f"{contract_name}.json",
            Path('/home/manifold/cursor/cross-chain-new/contracts/kept') / f"{contract_name}.json",
        ]

        for path in possible_paths:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)['abi']

        # 返回空 ABI，让调用者处理
        logger.warning(f"未找到合约 ABI 文件：{contract_name}")
        return []

    def get_issued_vcs_from_log(self) -> Dict:
        """
        从 uuid.json 读取已发行的 VC 记录

        Returns:
            包含 VC 列表的字典
        """
        try:
            uuid_file = UUID_JSON_PATH
            if not Path(uuid_file).exists():
                return {
                    'success': False,
                    'error': 'uuid.json 文件不存在',
                    'vcs': []
                }

            with open(uuid_file, 'r', encoding='utf-8') as f:
                uuid_data = json.load(f)

            result = []
            for uuid, vc_info in uuid_data.items():
                result.append({
                    'uuid': uuid,
                    'timestamp': vc_info.get('timestamp', ''),
                    'vc_type': vc_info.get('vc_type', ''),
                    'contract_name': vc_info.get('original_contract_name', ''),
                    'vc_hash': vc_info.get('vc_hash', ''),
                    'tx_hash': vc_info.get('tx_hash', ''),
                    'request_id': vc_info.get('request_id', '')
                })

            # 按时间戳倒序排列（最新的在前）
            result.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

            return {
                'success': True,
                'vcs': result,
                'total': len(result)
            }

        except Exception as e:
            logger.error(f"读取 uuid.json 失败：{e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'vcs': []
            }

    def initiate_cross_chain_transfer(
        self,
        vc_hash: str,
        vc_type: str,
        target_chain: str = "chain_b"
    ) -> Dict:
        """
        发起跨链传输

        Args:
            vc_hash: VC Hash (0x 开头的字符串)
            vc_type: VC 类型
            target_chain: 目标链 ID

        Returns:
            包含 tx_hash, gas_used 等信息的字典
        """
        try:
            auth_config = self._get_vc_manager_config(vc_type)
            w3 = self._get_chain_connection('chain_a')

            if not w3:
                logger.error("无法连接到 Chain A")
                raise ConnectionError("无法连接到 Chain A")

            # ========== 添加预检查 ==========
            # 1. 检查 Chain B 是否已存在
            check_b_result = self.check_vc_on_chain_b(vc_hash)
            if check_b_result.get('exists'):
                logger.warning(f"VC 已存在于 Chain B: {vc_hash}")
                return {
                    'success': False,
                    'error': '该 VC 已存在于 Chain B，无需重复跨链'
                }

            # 2. 检查 Chain A sendList 是否已存在
            check_a_result = self.check_vc_on_chain_a_sendlist(vc_hash)
            if check_a_result.get('exists'):
                logger.warning(f"VC 已在跨链传输中：{vc_hash}")
                return {
                    'success': False,
                    'error': '该 VC 已在跨链传输中，请勿重复发起'
                }
            # =================================

            # 加载 VC Manager 合约
            contract_name = auth_config['vc_manager_name']
            vc_manager_abi = self._load_contract_abi(contract_name)

            if not vc_manager_abi:
                logger.warning(f"未找到合约 ABI 文件：{contract_name}，使用默认 ABI")
                vc_manager_abi = [
                    {
                        "inputs": [
                            {"name": "_vcHash", "type": "bytes32"},
                            {"name": "_targetChain", "type": "string"}
                        ],
                        "name": "initiateCrossChainTransfer",
                        "outputs": [],
                        "stateMutability": "nonpayable",
                        "type": "function"
                    }
                ]

            vc_manager = w3.eth.contract(
                address=Web3.to_checksum_address(auth_config['vc_manager_address']),
                abi=vc_manager_abi
            )

            # 准备交易
            caller_address = Web3.to_checksum_address(auth_config['caller_address'])
            caller_private_key = auth_config['caller_private_key']
            vc_hash_bytes = bytes.fromhex(vc_hash.replace('0x', ''))

            gas_price = self.config.get('blockchain', {}).get('gas_price', 1000000000)
            gas_limit = self.config.get('blockchain', {}).get('gas_limit', 5000000)

            # ========== 添加详细的日志输出 ==========
            logger.info("=" * 60)
            logger.info(f"发起跨链传输：vc_hash={vc_hash}, vc_type={vc_type}, target_chain={target_chain}")
            logger.info(f"使用账户地址：{caller_address}")
            logger.info(f"账户私钥：{caller_private_key[:10]}...{caller_private_key[-8:] if caller_private_key else 'N/A'}")
            logger.info(f"Gas 配置：price={gas_price} wei ({gas_price/1e9} Gwei), limit={gas_limit}")
            logger.info(f"预计最大 Gas 费用：{gas_price * gas_limit} wei ({gas_price * gas_limit / 1e18} ETH)")

            # ========== 添加账户余额检查 ==========
            balance_wei = w3.eth.get_balance(caller_address)
            balance_eth = w3.from_wei(balance_wei, 'ether')
            required_balance_wei = gas_price * gas_limit
            required_balance_eth = w3.from_wei(required_balance_wei, 'ether')

            logger.info(f"账户当前余额：{balance_wei} wei ({balance_eth} ETH)")
            logger.info(f"交易所需余额：{required_balance_wei} wei ({required_balance_eth} ETH)")

            if balance_wei < required_balance_wei:
                error_msg = (
                    f"账户余额不足！"
                    f"当前余额：{balance_eth} ETH ({balance_wei} wei), "
                    f"需要：{required_balance_eth} ETH ({required_balance_wei} wei)"
                )
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'current_balance_wei': balance_wei,
                    'current_balance_eth': str(balance_eth),
                    'required_balance_wei': required_balance_wei,
                    'required_balance_eth': str(required_balance_eth)
                }

            # 检查余额是否充足（至少保留一些 ETH 用于后续交易）
            min_reserve_eth = 0.1  # 保留 0.1 ETH 作为储备
            min_reserve_wei = w3.to_wei(min_reserve_eth, 'ether')
            available_balance_wei = balance_wei - min_reserve_wei

            if available_balance_wei < required_balance_wei:
                warning_msg = (
                    f"账户余额紧张！"
                    f"当前余额：{balance_eth} ETH, "
                    f"扣除储备 ({min_reserve_eth} ETH) 后可用：{w3.from_wei(available_balance_wei, 'ether')} ETH, "
                    f"需要：{required_balance_eth} ETH"
                )
                logger.warning(warning_msg)

            logger.info(f"Nonce: {w3.eth.get_transaction_count(caller_address)}")
            logger.info(f"VC Manager 合约地址：{auth_config['vc_manager_address']}")
            logger.info("=" * 60)

            nonce = w3.eth.get_transaction_count(caller_address)

            # 构建 initiateCrossChainTransfer 交易
            txn = vc_manager.functions.initiateCrossChainTransfer(
                vc_hash_bytes,
                target_chain
            ).build_transaction({
                'from': caller_address,
                'gas': gas_limit,
                'gasPrice': gas_price,
                'nonce': nonce
            })

            logger.info(f"交易构建成功，准备签名并发送...")

            # 签名并发送交易
            signed_txn = w3.eth.account.sign_transaction(txn, caller_private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

            # 确保 tx_hash 是 hex 字符串（Web3 5.x 返回的是 AttributeDict）
            if hasattr(tx_hash, 'hex'):
                tx_hash_hex = tx_hash.hex()
            else:
                tx_hash_hex = tx_hash if isinstance(tx_hash, str) else str(tx_hash)

            logger.info(f"交易已发送！tx_hash={tx_hash_hex}")
            logger.info(f"等待交易确认...")

            # 等待交易确认
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] != 1:
                error_msg = f"initiateCrossChainTransfer 交易失败！tx_hash: {tx_hash_hex}"
                logger.error(error_msg)
                logger.error(f"交易回执：{receipt}")
                return {
                    'success': False,
                    'error': error_msg,
                    'tx_hash': tx_hash_hex
                }

            logger.info(f"交易成功！区块号：{receipt['blockNumber']}, Gas 使用：{receipt['gasUsed']}")

            return {
                'success': True,
                'tx_hash': tx_hash_hex,
                'block_number': receipt['blockNumber'],
                'gas_used': receipt['gasUsed'],
                'caller_address': caller_address,
                'gas_price': gas_price,
                'gas_limit': gas_limit
            }

        except Exception as e:
            logger.error(f"发起跨链传输失败：{e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def wait_for_cross_chain_transfer(
        self,
        vc_hash: str,
        timeout: int = 120
    ) -> Dict:
        """
        等待跨链传输完成并验证目标链

        Args:
            vc_hash: VC Hash
            timeout: 超时时间（秒）

        Returns:
            包含 success, found, record 等信息的字典
        """
        try:
            w3 = self._get_chain_connection('chain_b')

            if not w3:
                raise ConnectionError("无法连接到 Chain B")

            # 加载 Bridge 合约
            chain_b_config = self.config.get('chains', {}).get('chain_b', {})
            bridge_address = chain_b_config.get('bridge_address', '')

            bridge_abi = self._load_contract_abi('VCCrossChainBridgeSimple')

            if not bridge_abi:
                bridge_abi = [
                    {
                        "inputs": [{"name": "_vcHash", "type": "bytes32"}],
                        "name": "receiveList",
                        "outputs": [
                            {"name": "metadata", "type": "tuple"},
                            {"name": "sourceChain", "type": "string"},
                            {"name": "timestamp", "type": "uint256"},
                            {"name": "exists", "type": "bool"}
                        ],
                        "stateMutability": "view",
                        "type": "function"
                    }
                ]

            bridge = w3.eth.contract(
                address=Web3.to_checksum_address(bridge_address),
                abi=bridge_abi
            )

            vc_hash_bytes = bytes.fromhex(vc_hash.replace('0x', ''))

            start_time = time.time()
            check_count = 0

            # ========== 修复 1: 先检查是否已经存在（Oracle 可能已经处理过了）==========
            logger.info(f"开始等待跨链传输，先检查 VC 是否已在 Chain B 存在...")

            try:
                receive_record = bridge.functions.receiveList(vc_hash_bytes).call()
                if receive_record and len(receive_record) > 3 and receive_record[3]:
                    elapsed = time.time() - start_time
                    metadata = receive_record[0]
                    logger.info(f"VC 已在 Chain B 存在！耗时：{elapsed:.2f}秒")

                    return {
                        'success': True,
                        'found': True,
                        'elapsed_time': elapsed,
                        'check_count': 1,
                        'record': {
                            'vc_hash': self._to_hex_string(metadata[0]) if len(metadata) > 0 else '',
                            'vc_name': str(metadata[1]) if len(metadata) > 1 else '',
                            'holder_endpoint': str(metadata[2]) if len(metadata) > 2 else '',
                            'holder_did': str(metadata[3]) if len(metadata) > 3 else '',
                            'source_chain': receive_record[1],
                            'timestamp': str(receive_record[2]),
                            'exists': receive_record[3]
                        }
                    }
            except Exception as e:
                logger.info(f"初次检查失败（VC 可能还未传输到 Chain B）: {e}")

            # ========== 开始轮询等待 ==========
            logger.info(f"开始轮询等待跨链传输完成，超时时间：{timeout}秒...")

            while time.time() - start_time < timeout:
                check_count += 1

                try:
                    receive_record = bridge.functions.receiveList(vc_hash_bytes).call()

                    # receive_record 结构：(metadata, sourceChain, timestamp, exists)
                    if receive_record and len(receive_record) > 3 and receive_record[3]:
                        elapsed = time.time() - start_time
                        metadata = receive_record[0]

                        logger.info(f"跨链传输完成！耗时：{elapsed:.2f}秒，轮询次数：{check_count}")

                        return {
                            'success': True,
                            'found': True,
                            'elapsed_time': elapsed,
                            'check_count': check_count,
                            'record': {
                                'vc_hash': self._to_hex_string(metadata[0]) if len(metadata) > 0 else '',
                                'vc_name': str(metadata[1]) if len(metadata) > 1 else '',
                                'holder_endpoint': str(metadata[2]) if len(metadata) > 2 else '',
                                'holder_did': str(metadata[3]) if len(metadata) > 3 else '',
                                'source_chain': receive_record[1],
                                'timestamp': str(receive_record[2]),
                                'exists': receive_record[3]
                            }
                        }
                except Exception as e:
                    if check_count % 5 == 1:  # 每 5 次检查记录一次日志
                        logger.debug(f"轮询中 (count={check_count}): {e}")
                    pass

                time.sleep(3)  # 3 秒轮询间隔

            logger.warning(f"等待超时！耗时：{timeout}秒，轮询次数：{check_count}")

            return {
                'success': False,
                'found': False,
                'error': f'等待超时 ({timeout}秒)',
                'check_count': check_count,
                'message': '跨链传输可能仍在进行中，请稍后点击"从链 B 读取接收记录"手动检查状态'
            }

        except Exception as e:
            logger.error(f"等待跨链传输失败：{e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def get_vc_metadata_from_chain_a(self, vc_manager_type: str, vc_hash: str) -> Dict:
        """从 Chain A VC Manager 获取 VC 元数据 - 使用 vcMetadataList（不需要验证）"""
        try:
            # 构建 VC 类型到 Manager 配置的映射
            vc_type = None
            for vtype, config in self.vc_issuance_config.get('vc_types', {}).items():
                if config.get('contract_name') == vc_manager_type:
                    vc_type = vtype
                    break

            if not vc_type:
                # 尝试直接匹配
                type_to_name = {
                    'InspectionReport': 'InspectionReportVCManager',
                    'InsuranceContract': 'InsuranceContractVCManager',
                    'CertificateOfOrigin': 'CertificateOfOriginVCManager',
                    'BillOfLadingCertificate': 'BillOfLadingVCManager'
                }
                for vtype, name in type_to_name.items():
                    if name == vc_manager_type:
                        vc_type = vtype
                        break

            if not vc_type:
                vc_type = vc_manager_type  # fallback

            auth_config = self._get_vc_manager_config(vc_type)
            w3 = self._get_chain_connection('chain_a')

            if not w3:
                raise ConnectionError("无法连接到 Chain A")

            # 读取完整的 ABI 文件（包含 vcMetadataList 的 12 字段 struct）
            contract_name = auth_config['vc_manager_name']
            abi_file = Path(f'/home/manifold/cursor/cross-chain-new/contracts/kept/contract_abis/{contract_name}.json')

            if abi_file.exists():
                with open(abi_file, 'r', encoding='utf-8') as f:
                    vc_manager_abi = json.load(f)['abi']
            else:
                logger.warning(f"未找到 ABI 文件：{abi_file}")
                return {
                    'success': False,
                    'error': f'ABI 文件不存在：{contract_name}'
                }

            vc_manager = w3.eth.contract(
                address=Web3.to_checksum_address(auth_config['vc_manager_address']),
                abi=vc_manager_abi
            )

            vc_hash_bytes = bytes.fromhex(vc_hash.replace('0x', ''))

            # 使用 vcMetadataList mapping（public，不需要验证）
            metadata = vc_manager.functions.vcMetadataList(vc_hash_bytes).call()

            return {
                'success': True,
                'metadata': {
                    'vc_hash': '0x' + (metadata[0].hex() if hasattr(metadata[0], 'hex') else metadata[0]),
                    'vc_name': metadata[1],
                    'vc_description': metadata[2],
                    'issuer_endpoint': metadata[3],
                    'issuer_did': metadata[4],
                    'holder_endpoint': metadata[5],
                    'holder_did': metadata[6],
                    'blockchain_endpoint': metadata[7],
                    'vc_manager_address': metadata[8],
                    'blockchain_type': metadata[9],
                    'expiry_time': str(metadata[10]),
                    'exists': metadata[11]
                }
            }

        except Exception as e:
            logger.error(f"获取 VC 元数据失败：{e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def get_all_vc_hashes(self, vc_manager_type: str) -> Dict:
        """从 Chain A VC Manager 获取所有 VC 哈希列表"""
        try:
            # 构建 VC 类型到 Manager 配置的映射
            vc_type = None
            for vtype, config in self.vc_issuance_config.get('vc_types', {}).items():
                if config.get('contract_name') == vc_manager_type:
                    vc_type = vtype
                    break

            if not vc_type:
                type_to_name = {
                    'InspectionReport': 'InspectionReportVCManager',
                    'InsuranceContract': 'InsuranceContractVCManager',
                    'CertificateOfOrigin': 'CertificateOfOriginVCManager',
                    'BillOfLadingCertificate': 'BillOfLadingVCManager'
                }
                for vtype, name in type_to_name.items():
                    if name == vc_manager_type:
                        vc_type = vtype
                        break

            if not vc_type:
                vc_type = vc_manager_type

            auth_config = self._get_vc_manager_config(vc_type)
            w3 = self._get_chain_connection('chain_a')

            if not w3:
                raise ConnectionError("无法连接到 Chain A")

            contract_name = auth_config['vc_manager_name']
            vc_manager_abi = self._load_contract_abi(contract_name)

            if not vc_manager_abi:
                vc_manager_abi = [
                    {
                        "inputs": [],
                        "name": "getAllVCHashes",
                        "outputs": [{"name": "", "type": "bytes32[]"}],
                        "stateMutability": "view",
                        "type": "function"
                    },
                    {
                        "inputs": [{"name": "_vcHash", "type": "bytes32"}],
                        "name": "getVCMetadata",
                        "outputs": [
                            {"name": "vcName", "type": "string"},
                            {"name": "vcDescription", "type": "string"},
                            {"name": "issuerEndpoint", "type": "string"},
                            {"name": "issuerDID", "type": "string"},
                            {"name": "holderEndpoint", "type": "string"},
                            {"name": "holderDID", "type": "string"},
                            {"name": "vcManagerAddress", "type": "address"},
                            {"name": "expiryTime", "type": "uint256"},
                            {"name": "exists", "type": "bool"}
                        ],
                        "stateMutability": "view",
                        "type": "function"
                    }
                ]

            vc_manager = w3.eth.contract(
                address=Web3.to_checksum_address(auth_config['vc_manager_address']),
                abi=vc_manager_abi
            )

            # 获取所有 VC 哈希
            vc_hashes = vc_manager.functions.getAllVCHashes().call()

            # 获取每个 VC 的元数据
            vc_list = []
            for vc_hash in vc_hashes:
                try:
                    metadata = vc_manager.functions.getVCMetadata(vc_hash).call()
                    if metadata[8]:  # exists == True
                        vc_list.append({
                            'hash': vc_hash.hex() if hasattr(vc_hash, 'hex') else vc_hash,
                            'vc_name': metadata[0],
                            'vc_description': metadata[1],
                            'issuer_endpoint': metadata[2],
                            'issuer_did': metadata[3],
                            'holder_endpoint': metadata[4],
                            'holder_did': metadata[5],
                            'vc_manager_address': metadata[6],
                            'expiry_time': metadata[7],
                            'exists': metadata[8]
                        })
                except Exception as e:
                    logger.warning(f"无法读取 VC 元数据：{vc_hash}, 错误：{e}")
                    continue

            return {
                'success': True,
                'vc_manager_type': vc_manager_type,
                'vc_manager_address': auth_config['vc_manager_address'],
                'vc_list': vc_list
            }

        except Exception as e:
            logger.error(f"获取 VC 哈希列表失败：{e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def get_bridge_record_from_chain_b(self, vc_hash: str) -> Dict:
        """从 Chain B 跨链桥合约读取接收记录"""
        try:
            w3 = self._get_chain_connection('chain_b')

            if not w3:
                raise ConnectionError("无法连接到 Chain B")

            chain_b_config = self.config.get('chains', {}).get('chain_b', {})
            bridge_address = chain_b_config.get('bridge_address', '')

            bridge_abi = self._load_contract_abi('VCCrossChainBridgeSimple')

            if not bridge_abi:
                bridge_abi = [
                    {
                        "inputs": [{"name": "_vcHash", "type": "bytes32"}],
                        "name": "receiveList",
                        "outputs": [
                            {"name": "metadata", "type": "tuple"},
                            {"name": "sourceChain", "type": "string"},
                            {"name": "timestamp", "type": "uint256"},
                            {"name": "exists", "type": "bool"}
                        ],
                        "stateMutability": "view",
                        "type": "function"
                    }
                ]

            bridge = w3.eth.contract(
                address=Web3.to_checksum_address(bridge_address),
                abi=bridge_abi
            )

            vc_hash_bytes = bytes.fromhex(vc_hash.replace('0x', ''))
            receive_record = bridge.functions.receiveList(vc_hash_bytes).call()

            if receive_record and len(receive_record) > 3 and receive_record[3]:
                metadata = receive_record[0]
                # ========== 修复：正确处理 metadata 结构 ==========
                # metadata 结构：(vcHash, vcName, holderEndpoint, holderDID, vcManagerAddress, expiryTime, exists)
                return {
                    'success': True,
                    'found': True,
                    'record': {
                        'vc_hash': self._to_hex_string(metadata[0]) if len(metadata) > 0 else '',
                        'vc_name': str(metadata[1]) if len(metadata) > 1 else '',
                        'holder_endpoint': str(metadata[2]) if len(metadata) > 2 else '',
                        'holder_did': str(metadata[3]) if len(metadata) > 3 else '',
                        'vc_manager_address': str(metadata[4]) if len(metadata) > 4 else '',
                        'expiry_time': str(metadata[5]) if len(metadata) > 5 else '',
                        'source_chain': str(receive_record[1]),
                        'timestamp': str(receive_record[2]),
                        'exists': receive_record[3]
                    }
                }
            else:
                return {
                    'success': True,
                    'found': False,
                    'message': '链 B 暂未收到该 VC 记录'
                }

        except Exception as e:
            logger.error(f"读取链 B 桥接记录失败：{e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def check_vc_on_chain_b(self, vc_hash: str) -> Dict:
        """
        检查 VC 是否已存在于 Chain B 的接收列表中

        Args:
            vc_hash: VC Hash (0x 开头的字符串)

        Returns:
            包含 exists, record 等信息的字典
        """
        try:
            w3 = self._get_chain_connection('chain_b')
            if not w3:
                return {'exists': False, 'error': '无法连接到 Chain B'}

            chain_b_config = self.config.get('chains', {}).get('chain_b', {})
            bridge_address = chain_b_config.get('bridge_address', '')
            bridge_abi = self._load_contract_abi('VCCrossChainBridgeSimple')

            if not bridge_abi:
                bridge_abi = [
                    {
                        "inputs": [{"name": "_vcHash", "type": "bytes32"}],
                        "name": "receiveList",
                        "outputs": [
                            {"name": "metadata", "type": "tuple"},
                            {"name": "sourceChain", "type": "string"},
                            {"name": "timestamp", "type": "uint256"},
                            {"name": "exists", "type": "bool"}
                        ],
                        "stateMutability": "view",
                        "type": "function"
                    }
                ]

            bridge = w3.eth.contract(
                address=Web3.to_checksum_address(bridge_address),
                abi=bridge_abi
            )

            vc_hash_bytes = bytes.fromhex(vc_hash.replace('0x', ''))
            receive_record = bridge.functions.receiveList(vc_hash_bytes).call()

            # 如果 exists 字段为 True，说明 VC 已存在
            if receive_record and len(receive_record) > 3 and receive_record[3]:
                return {'exists': True, 'record': receive_record}
            return {'exists': False}
        except Exception as e:
            logger.error(f"检查 Chain B 失败：{e}")
            return {'exists': False, 'error': str(e)}

    def check_vc_on_chain_a_sendlist(self, vc_hash: str) -> Dict:
        """
        检查 VC 是否已在 Chain A 的发送列表中（是否已在跨链传输中）

        Args:
            vc_hash: VC Hash (0x 开头的字符串)

        Returns:
            包含 exists, record 等信息的字典
        """
        try:
            w3 = self._get_chain_connection('chain_a')
            if not w3:
                return {'exists': False, 'error': '无法连接到 Chain A'}

            chain_a_config = self.config.get('chains', {}).get('chain_a', {})
            bridge_address = chain_a_config.get('bridge_address', '')
            bridge_abi = self._load_contract_abi('VCCrossChainBridgeSimple')

            if not bridge_abi:
                bridge_abi = [
                    {
                        "inputs": [{"name": "_vcHash", "type": "bytes32"}],
                        "name": "sendList",
                        "outputs": [
                            {"name": "metadata", "type": "tuple"},
                            {"name": "targetChain", "type": "string"},
                            {"name": "timestamp", "type": "uint256"},
                            {"name": "exists", "type": "bool"}
                        ],
                        "stateMutability": "view",
                        "type": "function"
                    }
                ]

            bridge = w3.eth.contract(
                address=Web3.to_checksum_address(bridge_address),
                abi=bridge_abi
            )

            vc_hash_bytes = bytes.fromhex(vc_hash.replace('0x', ''))
            send_record = bridge.functions.sendList(vc_hash_bytes).call()

            # 如果 exists 字段为 True，说明 VC 已在跨链传输中
            if send_record and len(send_record) > 3 and send_record[3]:
                return {'exists': True, 'record': send_record}
            return {'exists': False}
        except Exception as e:
            logger.error(f"检查 Chain A 发送列表失败：{e}")
            return {'exists': False, 'error': str(e)}

    def _to_hex_string(self, value) -> str:
        """将 bytes 或 AttributeDict 转换为 hex 字符串"""
        if hasattr(value, 'hex'):
            return value.hex()
        elif isinstance(value, bytes):
            return '0x' + value.hex()
        else:
            return str(value)


# 创建全局服务实例
vc_crosschain_service = VCCrossChainService()
