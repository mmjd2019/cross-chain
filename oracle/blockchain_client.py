#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
区块链查询客户端
从区块链查询VC元数据并提取UUID

参考实现: vp_verifier_old.py 第154-273行
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

from web3_fixed_connection import FixedWeb3
from web3 import Web3


logger = logging.getLogger(__name__)


class BlockchainClient:
    """
    区块链查询客户端

    参考 vp_verifier_old.py 实现，负责：
    - 使用 FixedWeb3 建立区块链连接
    - 加载 VC Manager 合约
    - 从区块链查询 VC 元数据并提取 UUID
    """

    def __init__(self, blockchain_config: Dict, vc_config: Dict, use_local_cache: bool = True):
        """
        初始化区块链客户端

        参数:
            blockchain_config: 区块链配置 {"rpc_url": "...", "chain_id": "..."}
            vc_config: VC类型配置字典
            use_local_cache: 是否使用本地uuid.json作为备选查询（默认True）
        """
        self.blockchain_config = blockchain_config
        self.vc_config = vc_config
        self.use_local_cache = use_local_cache
        self.web3_fixed = None
        self.w3 = None
        self.vc_manager_contracts: Dict = {}

        # 初始化 Web3 和合约
        self._init_blockchain_connection()

    def _init_blockchain_connection(self):
        """
        初始化 Web3 连接和 VC Manager 合约

        参考 vp_verifier_old.py:154-194
        """
        try:
            rpc_url = self.blockchain_config.get('rpc_url', 'http://localhost:8545')
            chain_name = self.blockchain_config.get('chain_id', 'chain_a')

            # 使用 FixedWeb3（与 vp_verifier_old.py 一致）
            self.web3_fixed = FixedWeb3(rpc_url, chain_name)
            if not self.web3_fixed.is_connected():
                logger.warning(f"区块链连接失败: {rpc_url}")
                return

            self.w3 = self.web3_fixed.w3

            # 设置默认账户（使用第一个VC类型的oracle私钥）
            for vc_type, config in self.vc_config.items():
                private_key = config.get('oracle_private_key')
                if private_key:
                    from eth_account import Account
                    Account.enable_unaudited_hdwallet_features()
                    self.w3.eth.default_account = Account.from_key(private_key).address
                    logger.info(f"设置默认账户: {self.w3.eth.default_account}")
                    break

            # 初始化各 VC 类型的 Manager 合约
            for vc_type, config in self.vc_config.items():
                contract_address = config.get('contract_address')
                contract_name = config.get('contract_name')

                if not contract_address or not contract_name:
                    continue

                # 加载合约 ABI
                abi = self._load_contract_abi(contract_name)
                if not abi:
                    logger.warning(f"无法加载 {contract_name} 的 ABI")
                    continue

                # 创建合约实例
                self.vc_manager_contracts[vc_type] = self.w3.eth.contract(
                    address=Web3.to_checksum_address(contract_address),
                    abi=abi
                )
                logger.info(f"合约 {contract_name} 初始化成功: {contract_address}")

        except Exception as e:
            logger.error(f"初始化区块链连接失败: {e}", exc_info=True)

    def _load_contract_abi(self, contract_name: str) -> list:
        """
        加载合约 ABI

        参考 vp_verifier_old.py:195-214

        参数:
            contract_name: 合约名称（如 "InspectionReportVCManager"）

        返回:
            ABI列表，如果加载失败返回空列表
        """
        try:
            possible_paths = [
                Path(__file__).parent.parent / "contracts" / "kept" / "contract_abis" / f"{contract_name}.json",
                Path(__file__).parent.parent / "contracts" / "kept" / f"{contract_name}.json",
            ]

            for abi_path in possible_paths:
                if abi_path.exists():
                    with open(abi_path, 'r', encoding='utf-8') as f:
                        abi_data = json.load(f)
                        if isinstance(abi_data, dict) and 'abi' in abi_data:
                            return abi_data['abi']
                        else:
                            return abi_data
            return []
        except Exception as e:
            logger.error(f"加载合约 ABI {contract_name} 失败: {e}")
            return []

    def get_vc_uuid(self, vc_type: str, vc_hash: str) -> Optional[str]:
        """
        从区块链获取 VC 元数据并提取 UUID

        参考 vp_verifier_old.py:216-273 实现

        参数:
            vc_type: VC 类型（如 "InspectionReport"）
            vc_hash: VC 哈希值（66位十六进制，含0x前缀）

        返回:
            UUID 字符串，如果未找到则返回 None
        """
        try:
            if vc_type not in self.vc_manager_contracts:
                logger.error(f"未找到 VC 类型 {vc_type} 的合约实例")
                return None

            contract = self.vc_manager_contracts[vc_type]

            # 移除 0x 前缀（合约需要 bytes32）
            if vc_hash.startswith('0x'):
                vc_hash_bytes = bytes.fromhex(vc_hash[2:])
            else:
                vc_hash_bytes = bytes.fromhex(vc_hash)

            # 直接调用 getVCMetadata 函数（接受 bytes32 _vcHash）
            try:
                # 调用合约获取 VC 元数据
                # 返回: (vcHash, vcName, vcDescription, issuerEndpoint, issuerDID,
                #       holderEndpoint, holderDID, blockchainEndpoint, vcManagerAddress,
                #       blockchainType, expiryTime, exists)
                metadata = contract.functions.getVCMetadata(vc_hash_bytes).call()

                vc_hash_result = metadata[0]  # bytes32 vcHash
                vc_name = metadata[1]  # string vcName
                holder_did = metadata[6]  # string holderDID
                exists = metadata[11]  # bool exists

                if not exists:
                    logger.warning(f"VC不存在: vc_hash={vc_hash}")
                    return None

                logger.info(f"找到VC记录: vcHash={vc_hash_result.hex()}")
                logger.debug(f"  vcName: {vc_name}")
                logger.debug(f"  holderDID: {holder_did}")

                # 从 vcName 中提取 UUID
                # 格式: "质检证书 (UUID: xxx-xxx-xxx)"
                if '(UUID:' in vc_name:
                    uuid_start = vc_name.find('(UUID:') + 6
                    uuid_end = vc_name.find(')', uuid_start)
                    uuid = vc_name[uuid_start:uuid_end].strip()
                    logger.info(f"从区块链提取 UUID: {uuid}")
                    return uuid
                else:
                    logger.warning(f"vcName中未找到UUID格式: {vc_name}")
                    return None

            except Exception as e:
                logger.error(f"查询合约失败: {e}")
                return None

        except Exception as e:
            logger.error(f"从区块链获取 UUID 失败: {e}", exc_info=True)
            return None

    def get_vc_metadata(self, vc_type: str, vc_hash: str) -> Optional[Dict]:
        """
        获取完整的VC元数据

        参数:
            vc_type: VC 类型
            vc_hash: VC 哈希值

        返回:
            包含vcHash, vcName, holderDID, timestamp, uuid的字典，未找到返回None
        """
        try:
            if vc_type not in self.vc_manager_contracts:
                logger.error(f"未找到 VC 类型 {vc_type} 的合约实例")
                return None

            contract = self.vc_manager_contracts[vc_type]

            # 移除 0x 前缀
            if vc_hash.startswith('0x'):
                vc_hash_bytes = bytes.fromhex(vc_hash[2:])
            else:
                vc_hash_bytes = bytes.fromhex(vc_hash)

            vc_count = contract.functions.getVCCount().call()
            for i in range(vc_count):
                try:
                    metadata = contract.functions.getVCMetadata(i).call()
                    stored_hash = metadata[0]

                    if stored_hash == vc_hash_bytes or stored_hash.hex() == vc_hash[2:]:
                        result = {
                            'vcHash': stored_hash.hex(),
                            'vcName': metadata[1],
                            'holderDID': metadata[2],
                            'timestamp': metadata[3],
                            'index': i
                        }

                        # 提取UUID
                        if '(UUID:' in metadata[1]:
                            uuid_start = metadata[1].find('(UUID:') + 6
                            uuid_end = metadata[1].find(')', uuid_start)
                            result['uuid'] = metadata[1][uuid_start:uuid_end].strip()

                        return result
                except Exception:
                    continue

            return None

        except Exception as e:
            logger.error(f"获取VC元数据失败: {e}")
            return None

    def is_connected(self) -> bool:
        """检查区块链连接状态"""
        if self.web3_fixed:
            return self.web3_fixed.is_connected()
        return False

    def get_chain_id(self) -> Optional[int]:
        """获取链ID"""
        if self.w3:
            try:
                return self.w3.eth.chain_id
            except Exception:
                pass
        return None
