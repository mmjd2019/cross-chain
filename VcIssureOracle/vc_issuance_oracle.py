#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VC发行Oracle服务 - 同步版
基于simple_vc_issuance_test.py已验证的核心逻辑

架构说明:
- 使用同步requests库（与simple_vc_issuance_test.py一致）
- 使用Flask作为HTTP服务框架
- 核心VC发行逻辑完全采用simple_vc_issuance_test.py的实现
"""

import json
import logging
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, List

import requests
from flask import Flask, request, jsonify
from web3 import Web3
from eth_account import Account

from web3_fixed_connection import FixedWeb3

# 配置日志
def setup_logging(log_dir: str):
    """设置日志配置"""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    log_format = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'

    # 主日志
    main_handler = logging.FileHandler(log_path / 'vc_issuance_oracle.log', encoding='utf-8')
    main_handler.setLevel(logging.INFO)
    main_handler.setFormatter(logging.Formatter(log_format))

    # 成功日志
    success_handler = logging.FileHandler(log_path / 'vc_issuance_success.log', encoding='utf-8')
    success_handler.setLevel(logging.INFO)
    success_handler.setFormatter(logging.Formatter('%(message)s'))

    # 错误日志
    error_handler = logging.FileHandler(log_path / 'vc_issuance_errors.log', encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(log_format))

    # 控制台
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))

    # 配置根logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(main_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)

    return logging.getLogger('vc_issuance_oracle'), success_handler


# 日志目录将在 main() 中从配置文件加载
logger, success_log_handler = setup_logging('./logs')  # 临时值，会在 main() 中重新配置

# Flask应用
app = Flask(__name__)


class VCIssuanceCore:
    """
    VC发行核心类 - 基于simple_vc_issuance_test.py的已验证逻辑
    使用同步requests库
    """

    def __init__(self, config_path: str = "vc_issuance_config.json"):
        """初始化"""
        logger.info("=" * 80)
        logger.info("初始化VC发行Oracle服务 (同步版)")
        logger.info("=" * 80)

        # 加载配置
        self.config = self._load_config(config_path)
        self.vc_type_configs = self.config.get('vc_types', {})

        # 验证配置
        if not self._validate_config():
            raise ValueError("配置文件验证失败，请检查日志中的错误信息")
        self.acapy_config = self.config.get('acapy', {})
        self.blockchain_config = self.config.get('blockchain', {})
        self.service_config = self.config.get('service', {})

        # ACA-Py配置
        self.issuer_admin_url = self.acapy_config.get('issuer', {}).get('admin_url', 'http://localhost:8080').rstrip('/')
        self.holder_admin_url = self.acapy_config.get('holder', {}).get('admin_url', 'http://localhost:8081').rstrip('/')
        self.issuer_did = self.acapy_config.get('issuer', {}).get('did', '')
        self.holder_did = self.acapy_config.get('holder', {}).get('did', '')

        # Web3 & 合约
        self.web3_fixed: Optional[FixedWeb3] = None
        self.w3: Optional[Web3] = None
        self.contracts: Dict[str, Any] = {}
        self.oracle_accounts: Dict[str, Account] = {}

        # 连接管理
        self.issuer_connection_id: Optional[str] = None
        self._connection_lock = threading.Lock()

        # UUID日志文件锁
        self._uuid_file_lock = threading.Lock()
        self._uuid_log_path = Path('./logs/uuid.json')

        # 初始化
        self._init_web3()
        self._init_contracts()
        self._init_oracle_accounts()

        logger.info("VC发行Oracle服务初始化完成")
        logger.info(f"支持的VC类型: {list(self.vc_type_configs.keys())}")
        logger.info("=" * 80)

    def _load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        try:
            possible_paths = [
                Path(__file__).parent / config_file,
                Path(__file__).parent / "vc_issuance_docs" / config_file,
                Path.cwd() / config_file,
            ]

            for config_path in possible_paths:
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    logger.info(f"配置文件加载成功: {config_path}")
                    return config

            logger.error(f"配置文件 {config_file} 未找到")
            return {}
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            return {}

    def _validate_config(self) -> bool:
        """验证配置文件完整性"""
        required_sections = ['acapy', 'vc_types', 'blockchain']

        for section in required_sections:
            if section not in self.config:
                logger.error(f"配置缺少必需部分：{section}")
                return False

        # 验证 acapy 配置
        if 'issuer' not in self.config['acapy'] or 'holder' not in self.config['acapy']:
            logger.error("配置缺少必需部分：acapy.issuer 或 acapy.holder")
            return False

        # 验证至少有一个 VC 类型
        if not self.config['vc_types']:
            logger.error("配置中至少需要一个 VC 类型")
            return False

        # 验证每个 VC 类型的必需配置
        required_vc_fields = ['cred_def_id', 'contract_address', 'contract_name',
                             'oracle_address', 'oracle_private_key']
        for vc_type, config in self.vc_type_configs.items():
            for field in required_vc_fields:
                if field not in config:
                    logger.error(f"VC 类型 {vc_type} 缺少必需配置：{field}")
                    return False

        logger.info("配置文件验证通过")
        return True

    def _load_contract_abi(self, contract_name: str) -> list:
        """加载合约ABI"""
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
                            abi = abi_data['abi']
                        else:
                            abi = abi_data
                        return abi

            logger.error(f"合约ABI {contract_name} 未找到")
            return []
        except Exception as e:
            logger.error(f"加载合约ABI失败: {e}")
            return []

    def _init_web3(self):
        """初始化Web3连接"""
        try:
            rpc_url = self.blockchain_config.get('rpc_url', 'http://localhost:8545')
            chain_name = self.blockchain_config.get('chain_id', 'chain_a')

            self.web3_fixed = FixedWeb3(rpc_url, chain_name)
            if not self.web3_fixed.is_connected():
                logger.error(f"区块链连接失败: {rpc_url}")
                return

            self.w3 = self.web3_fixed.w3
            logger.info(f"区块链连接成功: {rpc_url}")
        except Exception as e:
            logger.error(f"初始化Web3连接失败: {e}")

    def _init_contracts(self):
        """初始化VC Manager合约"""
        try:
            for vc_type, config in self.vc_type_configs.items():
                contract_address = config.get('contract_address')
                contract_name = config.get('contract_name')

                if not contract_address or not contract_name:
                    continue

                abi = self._load_contract_abi(contract_name)
                if not abi:
                    continue

                self.contracts[vc_type] = self.w3.eth.contract(
                    address=Web3.to_checksum_address(contract_address),
                    abi=abi
                )
                logger.info(f"合约 {contract_name} 初始化成功")
        except Exception as e:
            logger.error(f"初始化合约失败: {e}")

    def _ensure_contracts_initialized(self):
        """懒加载：当合约未初始化时自动重新连接区块链并加载合约"""
        if self.contracts:
            return True
        logger.warning("合约未初始化，尝试重新连接区块链...")
        try:
            self._init_web3()
            if self.w3 is None:
                logger.error("重新连接区块链失败：Web3 对象为 None")
                return False
            self._init_contracts()
            if not self.contracts:
                logger.error("重新初始化合约后仍为空")
                return False
            logger.info(f"合约重新初始化成功，共 {len(self.contracts)} 个合约")
            return True
        except Exception as e:
            logger.error(f"合约重新初始化失败: {e}")
            return False

    def _init_oracle_accounts(self):
        """初始化Oracle账户"""
        try:
            for vc_type, config in self.vc_type_configs.items():
                private_key = config.get('oracle_private_key')
                if private_key:
                    account = Account.from_key(private_key)
                    self.oracle_accounts[vc_type] = account
                    logger.info(f"Oracle账户 {vc_type} 初始化成功")
        except Exception as e:
            logger.error(f"初始化Oracle账户失败: {e}")

    # ==================== 连接管理（来自simple_vc_issuance_test.py）====================

    def get_existing_connection(self) -> Optional[str]:
        """获取已有的DID匹配的active或response连接"""
        try:
            # 1. 获取Issuer的连接列表
            resp = requests.get(f"{self.issuer_admin_url}/connections", timeout=10)
            if resp.status_code != 200:
                return None

            issuer_data = resp.json()
            for issuer_conn in issuer_data.get('results', []):
                state = issuer_conn.get('state')
                their_label = issuer_conn.get('their_label', '')

                if state in ['active', 'response'] and 'Holder' in their_label:
                    issuer_conn_id = issuer_conn.get('connection_id')
                    issuer_their_did = issuer_conn.get('their_did')

                    # 2. 验证Holder端是否也有对应的连接（通过DID匹配）
                    holder_resp = requests.get(f"{self.holder_admin_url}/connections", timeout=10)
                    if holder_resp.status_code == 200:
                        holder_data = holder_resp.json()
                        for holder_conn in holder_data.get('results', []):
                            holder_state = holder_conn.get('state')
                            holder_label = holder_conn.get('their_label', '')
                            holder_my_did = holder_conn.get('my_did')

                            # 检查DID是否匹配：Issuer的Their DID == Holder的My DID
                            if (holder_state in ['active', 'response'] and
                                'Issuer' in holder_label and
                                holder_my_did == issuer_their_did):
                                logger.info(f"找到DID匹配的连接: {issuer_conn_id} (DID: {issuer_their_did})")
                                return issuer_conn_id

            logger.info("未找到DID匹配的有效连接")
            return None

        except Exception as e:
            logger.warning(f"检查现有连接失败: {e}")
            return None

    def create_connection(self) -> Optional[str]:
        """创建新连接（来自simple_vc_issuance_test.py）"""
        logger.info("创建新连接...")

        # 1. Issuer创建邀请
        payload = {
            "auto_accept": True,
            "multi_use": False,
            "alias": "oracle-issuer"
        }

        try:
            resp = requests.post(
                f"{self.issuer_admin_url}/connections/create-invitation",
                json=payload,
                timeout=30
            )
            if resp.status_code not in [200, 201]:
                logger.error(f"创建邀请失败: {resp.status_code}")
                return None

            data = resp.json()
            issuer_conn_id = data.get('connection_id')
            invitation = data.get('invitation')
            logger.info(f"Issuer邀请创建成功: {issuer_conn_id}")

        except Exception as e:
            logger.error(f"创建邀请异常: {e}")
            return None

        # 2. Holder接受邀请
        params = {"auto_accept": "true", "alias": "oracle-holder"}

        try:
            resp = requests.post(
                f"{self.holder_admin_url}/connections/receive-invitation",
                params=params,
                json=invitation,
                timeout=30
            )
            if resp.status_code not in [200, 201]:
                logger.error(f"Holder接受邀请失败: {resp.status_code}")
                return None

            logger.info("Holder接受邀请成功")

        except Exception as e:
            logger.error(f"Holder接受邀请异常: {e}")
            return None

        # 3. 等待连接就绪
        if self._wait_for_connection(issuer_conn_id):
            self.issuer_connection_id = issuer_conn_id
            return issuer_conn_id

        return None

    def _wait_for_connection(self, conn_id: str, timeout: int = 30) -> bool:
        """等待连接变为active或response状态"""
        logger.info(f"等待连接就绪: {conn_id}")
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            try:
                resp = requests.get(
                    f"{self.issuer_admin_url}/connections/{conn_id}",
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    state = data.get('state')

                    if state in ['active', 'response']:
                        logger.info(f"连接已就绪({state}): {conn_id}")
                        return True
                    logger.debug(f"连接状态: {state}")

            except Exception as e:
                logger.warning(f"检查连接状态失败: {e}")

            time.sleep(1)

        logger.error(f"等待连接就绪超时({timeout}秒)")
        return False

    def _is_connection_valid(self, conn_id: str) -> bool:
        """验证连接是否仍然有效（active 或 response 状态）"""
        try:
            resp = requests.get(
                f"{self.issuer_admin_url}/connections/{conn_id}",
                timeout=5
            )
            if resp.status_code == 200:
                state = resp.json().get('state')
                return state in ['active', 'response']
            return False
        except Exception:
            return False

    def get_or_create_connection(self) -> Optional[str]:
        """获取或创建连接（增强版：验证缓存连接有效性）"""
        with self._connection_lock:
            # 新增：验证缓存的连接是否仍然有效
            if self.issuer_connection_id:
                if self._is_connection_valid(self.issuer_connection_id):
                    logger.info(f"缓存的连接仍然有效: {self.issuer_connection_id}")
                    return self.issuer_connection_id
                else:
                    logger.warning(f"缓存的连接已失效: {self.issuer_connection_id}，将重新获取")
                    self.issuer_connection_id = None

            # 获取现有连接或创建新连接
            conn_id = self.get_existing_connection()
            if conn_id:
                self.issuer_connection_id = conn_id
                return conn_id

            # 没有现有连接，创建新连接
            logger.info("无可用连接，创建新连接...")
            return self.create_connection()

    # ==================== VC发行核心（来自simple_vc_issuance_test.py）====================

    def _find_cred_ex_by_thread_id(self, thread_id: str) -> Optional[str]:
        """通过thread_id查找cred_ex_id"""
        try:
            resp = requests.get(
                f"{self.issuer_admin_url}/issue-credential-2.0/records",
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                for record in data.get('results', []):
                    cred_ex = record.get('cred_ex_record', record)
                    if cred_ex.get('thread_id') == thread_id:
                        cred_ex_id = cred_ex.get('cred_ex_id')
                        logger.info(f"通过thread_id找到cred_ex_id: {cred_ex_id}")
                        return cred_ex_id
        except Exception as e:
            logger.warning(f"查找cred_ex_id失败: {e}")
        return None

    def send_vc_offer(self, conn_id: str, cred_def_id: str, attributes: Dict) -> Optional[str]:
        """发送VC Offer (AIP 2.0)"""
        attr_list = [{"name": k, "value": str(v)} for k, v in attributes.items()]

        payload = {
            "connection_id": conn_id,
            "comment": "VC Issuance via Oracle (AIP 2.0)",
            "credential_preview": {
                "@type": "issue-credential/2.0/credential-preview",
                "attributes": attr_list
            },
            "filter": {
                "indy": {
                    "cred_def_id": cred_def_id
                }
            }
        }

        try:
            resp = requests.post(
                f"{self.issuer_admin_url}/issue-credential-2.0/send-offer",
                json=payload,
                timeout=30
            )

            if resp.status_code in [200, 201]:
                data = resp.json()
                # 优先使用cred_ex_id
                cred_ex_id = data.get("cred_ex_id")
                thread_id = data.get("thread_id")

                # 如果没有cred_ex_id但有thread_id，通过查询找到cred_ex_id
                if not cred_ex_id and thread_id:
                    time.sleep(1)  # 等待记录创建
                    cred_ex_id = self._find_cred_ex_by_thread_id(thread_id)

                if cred_ex_id:
                    logger.info(f"VC Offer已发送 (AIP 2.0): cred_ex_id={cred_ex_id}")
                else:
                    logger.info(f"VC Offer已发送 (AIP 2.0): thread_id={thread_id}")

                return cred_ex_id or thread_id
            else:
                logger.error(f"发送VC Offer失败: {resp.status_code} - {resp.text}")

        except Exception as e:
            logger.error(f"发送VC Offer异常: {e}")

        return None

    def check_and_trigger_holder(self) -> bool:
        """检查Holder状态并触发send-request（来自simple_vc_issuance_test.py）"""
        results = []
        api_version = None

        # 先尝试新API
        try:
            resp = requests.get(
                f"{self.holder_admin_url}/issue-credential-2.0/records",
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get('results', [])
                api_version = "v2"
        except Exception:
            pass

        # 如果新API没有结果，尝试旧API
        if not results:
            try:
                resp = requests.get(
                    f"{self.holder_admin_url}/issue-credential/records",
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get('results', [])
                    api_version = "v1"
            except Exception as e:
                logger.error(f"查询Holder记录失败: {e}")
                return False

        if not results:
            logger.warning("Holder端未找到credential exchange记录")
            return False

        for record in reversed(results):
            state = record.get('state')
            cred_ex_id = record.get('cred_ex_id')

            offer_states = ['offer-received', 'offer_received']
            progress_states = ['request-sent', 'request_sent', 'credential-received',
                              'credential_received', 'done', 'credential_acked']

            # 如果Holder处于offer-received状态，触发send-request
            if state in offer_states and cred_ex_id:
                logger.info(f"Holder处于{state}状态，触发send-request")

                if api_version == "v2":
                    endpoint = f"{self.holder_admin_url}/issue-credential-2.0/records/{cred_ex_id}/send-request"
                else:
                    endpoint = f"{self.holder_admin_url}/issue-credential/records/{cred_ex_id}/send-request"

                post_resp = requests.post(endpoint, json={}, timeout=10)

                if post_resp.status_code in [200, 201]:
                    logger.info("成功触发Holder发送request")
                    return True
                else:
                    logger.error(f"触发send-request失败: {post_resp.status_code}")
                    return False

            # 如果状态已经是request-sent或更高
            if state in progress_states:
                logger.info(f"Holder已自动响应，当前状态: {state}")
                return True

        return False

    def trigger_issuer_issue(self, cred_ex_id: str) -> bool:
        """触发Issuer颁发凭证"""
        # 先尝试新API
        try:
            resp = requests.post(
                f"{self.issuer_admin_url}/issue-credential-2.0/records/{cred_ex_id}/issue",
                json={},
                timeout=30
            )
            if resp.status_code in [200, 201]:
                logger.info(f"Credential已颁发：{cred_ex_id}")
                return True
        except Exception:
            pass

        # 尝试旧API
        try:
            resp = requests.post(
                f"{self.issuer_admin_url}/issue-credential/records/{cred_ex_id}/issue",
                json={},
                timeout=30
            )
            return resp.status_code in [200, 201]
        except Exception:
            return False

    def trigger_holder_store(self, cred_ex_id: str) -> bool:
        """触发 Holder 存储凭证（调用 /store 端点）

        注意：必须提供空 body {}，与 curl 脚本中的 -d '{}' 一致
        """
        try:
            # 关键：必须提供空 body，即使是 {}
            resp = requests.post(
                f"{self.holder_admin_url}/issue-credential-2.0/records/{cred_ex_id}/store",
                json={},  # 关键：必须提供空 body，与 curl -d '{}' 一致
                timeout=10
            )
            if resp.status_code in [200, 201]:
                logger.info(f"Holder 已存储凭证：{cred_ex_id}")
                return True
            else:
                logger.warning(f"Holder store 请求返回：{resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            logger.warning(f"Holder store 异常：{e}")
            return False

    def get_issuer_state(self, cred_ex_id: str) -> Optional[str]:
        """获取Issuer状态"""
        # 先尝试新API (AIP 2.0)
        try:
            resp = requests.get(
                f"{self.issuer_admin_url}/issue-credential-2.0/records/{cred_ex_id}",
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                # AIP 2.0的state在cred_ex_record中
                cred_ex_record = data.get('cred_ex_record', data)
                state = cred_ex_record.get('state') or data.get('state')
                return state
        except Exception:
            pass

        # 尝试旧API
        try:
            resp = requests.get(
                f"{self.issuer_admin_url}/issue-credential/records/{cred_ex_id}",
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get('state')
        except Exception:
            pass

        return None

    def get_holder_cred_ex_by_thread_id(self, thread_id: str) -> tuple:
        """通过 thread_id 获取 Holder 端 cred_ex_id 和状态（支持 AIP 1.0 和 2.0）

        返回：
            tuple: (cred_ex_id, state) - 如果找到，否则 (None, None)
        """
        # 先尝试新 API (AIP 2.0)
        try:
            resp = requests.get(
                f"{self.holder_admin_url}/issue-credential-2.0/records",
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                for record in data.get('results', []):
                    cred_ex = record.get('cred_ex_record', record)
                    if cred_ex.get('thread_id') == thread_id:
                        return cred_ex.get('cred_ex_id'), cred_ex.get('state')
        except Exception:
            pass

        # 尝试旧 API (AIP 1.0)
        try:
            resp = requests.get(
                f"{self.holder_admin_url}/issue-credential/records",
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                for record in data.get('results', []):
                    if record.get('thread_id') == thread_id:
                        return record.get('cred_ex_id'), record.get('state')
        except Exception as e:
            logger.warning(f"获取 Holder cred_ex_id 失败：{e}")
        return None, None

    def get_holder_state_by_thread(self, thread_id: str) -> Optional[str]:
        """通过 thread_id 获取 Holder 端凭证交换状态"""
        cred_ex_id, state = self.get_holder_cred_ex_by_thread_id(thread_id)
        return state

    def get_holder_state(self, cred_ex_id: str) -> Optional[str]:
        """获取 Holder 端凭证交换状态"""
        try:
            resp = requests.get(
                f"{self.holder_admin_url}/issue-credential-2.0/records/{cred_ex_id}",
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                cred_ex_record = data.get('cred_ex_record', data)
                return cred_ex_record.get('state') or data.get('state')
        except Exception:
            pass
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
                f"{self.holder_admin_url}/credentials",
                params={"start": start, "count": count},
                timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get('results', [])
        except Exception as e:
            logger.error(f"获取凭证失败：{e}")
        return []

    def get_holder_credentials_count(self) -> int:
        """获取 Holder 凭证总数"""
        try:
            creds = self.get_holder_credentials(start=0, count=10000)
            return len(creds)
        except Exception as e:
            logger.error(f"统计凭证数量失败：{e}")
            return 0

    def get_holder_credentials_sorted_by_date(self, descending: bool = True) -> List[Dict]:
        """获取 Holder 凭证并按 Date 字段排序

        Args:
            descending: True 表示从新到旧，False 表示从旧到新

        Returns:
            按 Date 排序的凭证列表
        """
        try:
            all_creds = self.get_holder_credentials(start=0, count=10000)
            sorted_creds = sorted(
                all_creds,
                key=lambda x: x.get('attrs', {}).get('Date', '') or '',
                reverse=descending
            )
            return sorted_creds
        except Exception as e:
            logger.error(f"排序凭证失败：{e}")
            return []

    def get_holder_credentials_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """按日期范围查询凭证

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            指定日期范围内的凭证列表
        """
        try:
            all_creds = self.get_holder_credentials(start=0, count=10000)
            filtered_creds = [
                cred for cred in all_creds
                if start_date <= (cred.get('attrs', {}).get('Date', '') or '') <= end_date
            ]
            return filtered_creds
        except Exception as e:
            logger.error(f"按日期范围查询失败：{e}")
            return []

    def get_credentials_grouped_by_date(self) -> List[Dict]:
        """按日期分组统计凭证数量

        Returns:
            包含日期和数量的列表，按日期降序
        """
        try:
            all_creds = self.get_holder_credentials(start=0, count=10000)
            date_groups = {}
            for cred in all_creds:
                date = cred.get('attrs', {}).get('Date', 'unknown')
                if date not in date_groups:
                    date_groups[date] = 0
                date_groups[date] += 1

            result = [{"Date": date, "count": count} for date, count in date_groups.items()]
            result.sort(key=lambda x: x['Date'], reverse=True)
            return result
        except Exception as e:
            logger.error(f"分组统计失败：{e}")
            return []


    def wait_for_holder_response(self, thread_id: str, timeout: int = 30) -> tuple:
        """等待 Holder 响应，通过 thread_id 轮询

        参数:
            thread_id: 凭证交换的 thread ID
            timeout: 超时时间（秒）

        返回:
            tuple: (success, holder_cred_ex_id)
                - success: True 表示 Holder 已响应，False 表示超时或失败
                - holder_cred_ex_id: Holder 端的 cred_ex_id，如果成功则非 None
        """
        logger.info(f"等待 Holder 响应 (最多{timeout}秒)...")
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            holder_cred_ex_id, holder_state = self.get_holder_cred_ex_by_thread_id(thread_id)

            if holder_state == 'credential-received':
                logger.info(f"Holder 已响应 (状态：credential-received), cred_ex_id: {holder_cred_ex_id}")
                return True, holder_cred_ex_id
            elif holder_state in ['request-sent', 'request_sent']:
                logger.info(f"Holder 已发送请求 (状态：{holder_state})")
                return True, holder_cred_ex_id
            elif holder_state == 'abandoned':
                logger.error("凭证交换被废弃")
                return False, None
            elif holder_state == 'done':
                logger.info(f"Holder 已存储凭证 (状态：done)")
                return True, holder_cred_ex_id

            logger.info(f"等待中... 当前状态：{holder_state or 'unknown'}")
            time.sleep(5)  # 每 5 秒检查一次

        logger.error("Holder 响应超时")
        return False, None

    def monitor_issuance(self, cred_ex_id: str, vc_uuid: str = None, timeout: int = 90) -> bool:
        """监控 VC 发行进度 - 基于 curl 脚本流程

        阶段划分:
        1. 获取 thread_id
        2. 等待 Holder 响应 (credential-received)
        3. 触发 Issuer 颁发凭证
        4. 等待凭证颁发完成并调用 Holder store
        5. 验证 VC 存储（UUID 匹配）
        """
        logger.info(f"开始监控 VC 发行进度：{cred_ex_id}")
        start_time = time.time()

        thread_id = None
        holder_cred_ex_id = None

        # ========== 阶段 1: 获取 thread_id ==========
        logger.info("阶段 1: 获取 thread_id...")
        thread_timeout = min(30, timeout // 3)
        while thread_id is None and (time.time() - start_time) < thread_timeout:
            try:
                resp = requests.get(
                    f"{self.issuer_admin_url}/issue-credential-2.0/records/{cred_ex_id}",
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    cred_ex_record = data.get('cred_ex_record', data)
                    thread_id = cred_ex_record.get('thread_id')
                    if thread_id:
                        logger.info(f"Thread ID: {thread_id}")
            except Exception as e:
                logger.warning(f"获取 thread_id 失败：{e}")
            time.sleep(1)

        if not thread_id:
            logger.error("未能获取 thread_id")
            return False

        # ========== 阶段 2: 等待 Holder 响应 (credential-received) ==========
        logger.info("阶段 2: 等待 Holder 响应...")
        holder_timeout = min(30, timeout // 3)
        wait_start = time.time()
        holder_responded = False

        while not holder_responded and (time.time() - wait_start) < holder_timeout:
            holder_cred_ex_id, holder_state = self.get_holder_cred_ex_by_thread_id(thread_id)

            if holder_state == 'credential-received':
                logger.info(f"Holder 已响应 (状态：credential-received), cred_ex_id: {holder_cred_ex_id}")
                holder_responded = True
                break
            elif holder_state in ['request-sent', 'request_sent']:
                logger.info(f"Holder 已发送请求 (状态：{holder_state})")
                holder_responded = True
                break
            elif holder_state == 'abandoned':
                logger.error("凭证交换被废弃")
                return False

            time.sleep(5)

        if not holder_responded:
            logger.error("等待 Holder 响应超时")
            return False

        # ========== 阶段 3: 触发 Issuer 颁发凭证 ==========
        logger.info("阶段 3: 触发 Issuer 颁发凭证...")
        issuer_state = self.get_issuer_state(cred_ex_id)

        if issuer_state == 'request-received':
            logger.info("Issuer 收到请求，触发颁发凭证...")
            if not self.trigger_issuer_issue(cred_ex_id):
                logger.error("凭证颁发失败")
                return False
            logger.info("凭证颁发成功")
        elif issuer_state in ['credential-issued', 'credential_issued']:
            logger.info(f"Issuer 已颁发凭证 (状态：{issuer_state})，跳过触发步骤")
        elif issuer_state is None:
            logger.warning("无法获取 Issuer 状态，尝试继续流程")
        else:
            logger.warning(f"Issuer 状态异常：{issuer_state}，尝试触发颁发")
            if not self.trigger_issuer_issue(cred_ex_id):
                logger.error("凭证颁发失败")
                return False
            logger.info("凭证颁发成功")

        # ========== 阶段 4: 等待凭证颁发完成并调用 Holder store ==========
        logger.info("阶段 4: 等待凭证颁发并调用 Holder store...")
        store_timeout = min(30, timeout // 3)
        issue_start = time.time()
        store_triggered = False

        while not store_triggered and (time.time() - issue_start) < store_timeout:
            holder_cred_ex_id, holder_state = self.get_holder_cred_ex_by_thread_id(thread_id)

            # 优先检查是否已完成
            if holder_state == 'done':
                logger.info("Holder 已存储凭证 (状态：done)")
                store_triggered = True
                break
            elif holder_state == 'credential-received' and holder_cred_ex_id:
                logger.info(f"找到 Holder credential-received 记录：{holder_cred_ex_id}")
                # 调用 store 端点，必须带空 body
                if self.trigger_holder_store(holder_cred_ex_id):
                    logger.info("Holder store 触发成功，等待 VC 存储...")
                    time.sleep(2)  # 等待存储完成
                    store_triggered = True
                    break
                else:
                    logger.warning("Holder store 调用失败，继续等待")
            elif holder_state is None:
                logger.debug("等待 Holder 记录...")

            time.sleep(2)

        if not store_triggered:
            logger.warning("未能触发 Holder store，但继续验证 VC 存储")

        # ========== 阶段 5: 验证 VC 存储（UUID 匹配） ==========
        logger.info("阶段 5: 验证 VC 存储...")
        if vc_uuid:
            verify_start = time.time()
            verify_timeout = min(10, timeout // 9)
            vc_stored = False

            while not vc_stored and (time.time() - verify_start) < verify_timeout:
                current_creds = self.get_holder_credentials()
                for cred in current_creds:
                    if cred.get('attrs', {}).get('contractName') == vc_uuid:
                        logger.info(f"Holder 已存储 VC (找到 UUID: {vc_uuid})!")
                        vc_stored = True
                        break
                if not vc_stored:
                    time.sleep(1)

            return vc_stored

        return True

    # ==================== 区块链写入 ====================

    def calculate_vc_hash(self, vc_content: dict) -> str:
        """计算 VC 内容的 Hash（确定性哈希）"""
        try:
            # 使用凭证属性计算子哈希，确保相同内容生成相同哈希
            attributes = vc_content.get("values", {})
            attr_string = json.dumps(attributes, sort_keys=True, separators=(',', ':'))
            subject_hash = Web3.keccak(text=attr_string).hex()

            hash_data = {
                "schema_id": vc_content.get("schema_id"),
                "cred_def_id": vc_content.get("cred_def_id"),
                "issuer_did": self.issuer_did,
                "credential_exchange_id": vc_content.get("credential_exchange_id"),
                "subject_hash": subject_hash  # 使用属性哈希代替时间戳
            }

            canonical_json = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
            hash_bytes = Web3.keccak(text=canonical_json)
            hex_hash = hash_bytes.hex()

            return hex_hash if hex_hash.startswith('0x') else "0x" + hex_hash
        except Exception as e:
            logger.error(f"计算VC Hash失败: {e}")
            raise Exception(f"Hash计算失败: {e}")

    def write_to_blockchain(self, vc_type: str, vc_hash: str, metadata: Dict) -> str:
        """写入区块链"""
        try:
            # 懒加载：合约未初始化时自动重连
            if vc_type not in self.contracts:
                if not self._ensure_contracts_initialized():
                    raise Exception(f"未找到VC类型 {vc_type} 的合约（重连后仍无可用合约）")
            if vc_type not in self.contracts:
                raise Exception(f"未找到VC类型 {vc_type} 的合约")

            if vc_type not in self.oracle_accounts:
                raise Exception(f"未找到VC类型 {vc_type} 的Oracle账户")

            contract = self.contracts[vc_type]
            oracle_address = self.vc_type_configs[vc_type]['oracle_address']

            function_call = contract.functions.addVCMetadata(
                bytes.fromhex(vc_hash[2:]),
                metadata.get('vcName', ''),
                metadata.get('vcDescription', ''),
                self.acapy_config.get('issuer', {}).get('endpoint', ''),
                self.issuer_did,
                self.acapy_config.get('holder', {}).get('endpoint', ''),
                self.holder_did,
                self.blockchain_config.get('rpc_url', ''),
                'Hyperledger Besu',
                metadata.get('expiryTime', 0)
            )

            gas_price = self.blockchain_config.get('gas_price', 1000000000)
            nonce = self.w3.eth.get_transaction_count(oracle_address)

            try:
                gas_estimate = function_call.estimate_gas({'from': oracle_address})
                gas_limit = int(gas_estimate * 1.2)
                logger.info(f"Gas 估算：{gas_estimate}，限制：{gas_limit}")
            except Exception as e:
                logger.warning(f"Gas 估算失败，使用默认值：{e}")
                gas_limit = self.blockchain_config.get('gas_limit', 300000)

            transaction = function_call.build_transaction({
                'from': oracle_address,
                'gas': gas_limit,
                'gasPrice': gas_price,
                'nonce': nonce
            })

            private_key = self.vc_type_configs[vc_type]['oracle_private_key']
            signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)

            logger.info(f"交易已发送: {tx_hash.hex()}")

            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt.status == 1:
                logger.info(f"交易确认成功, 区块: {receipt.blockNumber}")
                return tx_hash.hex()
            else:
                raise Exception(f"交易失败, 状态: {receipt.status}")

        except Exception as e:
            logger.error(f"写入合约失败: {e}")
            raise

    # ==================== 日志和UUID管理 ====================

    def log_uuid_to_file(self, vc_uuid: str, vc_type: str, original_contract_name: str,
                         vc_hash: str, tx_hash: str, request_id: str):
        """记录UUID到文件"""
        try:
            self._uuid_log_path.parent.mkdir(parents=True, exist_ok=True)

            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "vc_type": vc_type,
                "original_contract_name": original_contract_name,
                "vc_hash": vc_hash,
                "tx_hash": tx_hash,
                "request_id": request_id
            }

            with self._uuid_file_lock:
                if self._uuid_log_path.exists():
                    try:
                        with open(self._uuid_log_path, 'r', encoding='utf-8') as f:
                            uuid_data = json.load(f)
                    except (json.JSONDecodeError, IOError):
                        uuid_data = {}
                else:
                    uuid_data = {}

                uuid_data[vc_uuid] = log_entry

                with open(self._uuid_log_path, 'w', encoding='utf-8') as f:
                    json.dump(uuid_data, f, ensure_ascii=False, indent=2)

            logger.info(f"UUID已记录: {vc_uuid}")

        except Exception as e:
            logger.error(f"记录UUID失败: {e}")

    # ==================== 主发行流程 ====================

    def issue_vc(self, vc_type: str, metadata: Dict, attributes: Dict) -> Dict:
        """完整的VC发行流程"""
        request_id = str(uuid.uuid4())
        logger.info(f"[{request_id}] 开始发行 {vc_type} VC")

        try:
            # 验证VC类型
            if vc_type not in self.vc_type_configs:
                return {"status": "failed", "request_id": request_id, "error": f"不支持的VC类型: {vc_type}"}

            config = self.vc_type_configs[vc_type]
            cred_def_id = config.get('cred_def_id')

            if not cred_def_id:
                return {"status": "failed", "request_id": request_id, "error": "缺少cred_def_id配置"}

            # 步骤1: 获取连接
            logger.info(f"[{request_id}] 步骤1: 获取连接")
            connection_id = self.get_or_create_connection()
            if not connection_id:
                return {"status": "failed", "request_id": request_id, "error": "无法建立ACA-Py连接"}

            # 生成UUID
            original_contract_name = attributes.get('contractName', '')
            vc_uuid = str(uuid.uuid4())
            attributes['contractName'] = vc_uuid
            logger.info(f"[{request_id}] 生成UUID: {vc_uuid}")

            # 自动生成productBatch
            if not attributes.get('productBatch'):
                attributes['productBatch'] = f"BATCH-{str(uuid.uuid4())[:8].upper()}"

            # 步骤2: 发送VC Offer
            logger.info(f"[{request_id}] 步骤2: 发送VC Offer (AIP 2.0)")
            cred_ex_id = self.send_vc_offer(connection_id, cred_def_id, attributes)
            if not cred_ex_id:
                return {"status": "failed", "request_id": request_id, "error": "发送VC Offer失败"}

            # 步骤3: 监控发行进度（增加超时到90秒，传入vc_uuid）
            logger.info(f"[{request_id}] 步骤3: 监控发行进度")
            if not self.monitor_issuance(cred_ex_id, vc_uuid=vc_uuid, timeout=90):
                return {"status": "failed", "request_id": request_id, "error": "VC发行超时或失败"}

            # 步骤4: 计算VC Hash
            logger.info(f"[{request_id}] 步骤4: 计算VC Hash")
            vc_content = {
                "schema_id": config.get('schema_id', ''),
                "cred_def_id": cred_def_id,
                "values": attributes,
                "credential_exchange_id": cred_ex_id
            }
            vc_hash = self.calculate_vc_hash(vc_content)
            logger.info(f"[{request_id}] VC Hash: {vc_hash}")

            # 步骤5: 写入区块链
            logger.info(f"[{request_id}] 步骤5: 写入区块链")
            metadata_with_uuid = metadata.copy()
            metadata_with_uuid['vcName'] = f"{metadata.get('vcName', '')} (UUID: {vc_uuid})"

            tx_hash = self.write_to_blockchain(vc_type, vc_hash, metadata_with_uuid)
            logger.info(f"[{request_id}] 区块链写入成功: {tx_hash}")

            # 步骤6: 记录UUID
            self.log_uuid_to_file(vc_uuid, vc_type, original_contract_name, vc_hash, tx_hash, request_id)

            return {
                "status": "success",
                "request_id": request_id,
                "vc_hash": vc_hash,
                "vc_uuid": vc_uuid,
                "tx_hash": tx_hash,
                "cred_ex_id": cred_ex_id,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"[{request_id}] VC 发行失败:\n{error_details}")
            return {
                "status": "failed",
                "request_id": request_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "timestamp": datetime.now().isoformat()
            }


# 全局实例
oracle_core = None


def get_oracle() -> VCIssuanceCore:
    """获取Oracle实例"""
    global oracle_core
    if oracle_core is None:
        oracle_core = VCIssuanceCore()
    return oracle_core


# ==================== Flask路由 ====================

@app.route('/issue-vc', methods=['POST'])
def handle_issue_vc():
    """处理VC发行请求"""
    try:
        data = request.get_json()
        vc_type = data.get('vc_type')
        metadata = data.get('metadata', {})
        attributes = data.get('attributes', {})

        # 添加日志检查接收到的属性
        logger.info(f"收到VC发行请求: vc_type={vc_type}, attributes={list(attributes.keys())}")

        if not vc_type:
            return jsonify({"status": "failed", "error": "缺少vc_type参数"}), 400

        oracle = get_oracle()
        result = oracle.issue_vc(vc_type, metadata, attributes)
        return jsonify(result)

    except Exception as e:
        logger.error(f"处理请求失败: {e}")
        return jsonify({"status": "failed", "error": str(e)}), 500


@app.route('/health', methods=['GET'])
def handle_health():
    """健康检查（增强版：验证缓存连接有效性）"""
    oracle = get_oracle()

    # 检查ACA-Py服务
    issuer_connected = False
    holder_connected = False

    try:
        resp = requests.get(f"{oracle.issuer_admin_url}/status", timeout=5)
        issuer_connected = resp.status_code == 200
    except:
        pass

    try:
        resp = requests.get(f"{oracle.holder_admin_url}/status", timeout=5)
        holder_connected = resp.status_code == 200
    except:
        pass

    # 新增：验证缓存连接的有效性
    active_connection = oracle.issuer_connection_id
    conn_valid = False
    if active_connection:
        conn_valid = oracle._is_connection_valid(active_connection)
        if not conn_valid:
            logger.warning(f"健康检查：缓存的连接 {active_connection} 已失效")

    health_status = {
        "status": "ok" if (issuer_connected and holder_connected) else "degraded",
        "service": "vc_issuance_oracle",
        "version": "2.0.0-sync",
        "timestamp": datetime.now().isoformat(),
        "connections": {
            "web3": "connected" if oracle.web3_fixed and oracle.web3_fixed.is_connected() else "disconnected",
            "acapy_issuer": "connected" if issuer_connected else "disconnected",
            "acapy_holder": "connected" if holder_connected else "disconnected",
            "active_connection": active_connection if conn_valid else None,
            "connection_valid": conn_valid
        },
        "vc_types": list(oracle.vc_type_configs.keys())
    }
    return jsonify(health_status)


@app.route('/vc-status/<vc_hash>', methods=['GET'])
def handle_vc_status(vc_hash):
    """查询VC状态"""
    # 简化实现
    return jsonify({"vc_hash": vc_hash, "status": "processed"})


@app.route('/credentials', methods=['GET'])
def handle_get_credentials():
    """获取 Holder 凭证列表（支持分页和排序）"""
    try:
        oracle = get_oracle()

        # 获取分页参数
        start = request.args.get('start', 0, type=int)
        count = request.args.get('count', 1000, type=int)

        # 获取排序参数
        sort_by_date = request.args.get('sort_by_date', None)
        descending = request.args.get('descending', 'true', type=str).lower() == 'true'

        # 获取日期范围参数
        start_date = request.args.get('start_date', None)
        end_date = request.args.get('end_date', None)

        # 获取分组统计参数
        group_by_date = request.args.get('group_by_date', 'false', type=str).lower() == 'true'

        if group_by_date:
            # 按日期分组统计
            result = oracle.get_credentials_grouped_by_date()
            return jsonify({
                "status": "success",
                "data": result,
                "total_groups": len(result)
            })

        if start_date and end_date:
            # 按日期范围查询
            result = oracle.get_holder_credentials_by_date_range(start_date, end_date)
            return jsonify({
                "status": "success",
                "data": result,
                "total": len(result),
                "date_range": {"start": start_date, "end": end_date}
            })

        if sort_by_date == 'Date':
            # 按 Date 字段排序
            result = oracle.get_holder_credentials_sorted_by_date(descending=descending)
            return jsonify({
                "status": "success",
                "data": result,
                "total": len(result),
                "sort": {"by": "Date", "order": "desc" if descending else "asc"}
            })

        # 默认分页查询
        result = oracle.get_holder_credentials(start=start, count=count)
        total = oracle.get_holder_credentials_count()

        return jsonify({
            "status": "success",
            "data": result,
            "pagination": {"start": start, "count": count, "total": total},
            "note": "ACA-Py 使用 start/count 参数，不是 limit/offset"
        })

    except Exception as e:
        logger.error(f"获取凭证失败：{e}")
        return jsonify({"status": "failed", "error": str(e)}), 500


@app.route('/credentials/count', methods=['GET'])
def handle_credentials_count():
    """获取 Holder 凭证总数"""
    try:
        oracle = get_oracle()
        count = oracle.get_holder_credentials_count()
        return jsonify({
            "status": "success",
            "count": count
        })
    except Exception as e:
        logger.error(f"统计凭证数量失败：{e}")
        return jsonify({"status": "failed", "error": str(e)}), 500



def main():
    """主函数"""
    # 切换到脚本所在目录
    script_dir = Path(__file__).parent
    import os
    os.chdir(script_dir)

    oracle = get_oracle()
    port = oracle.service_config.get('port', 6000)
    host = oracle.service_config.get('host', '0.0.0.0')

    logger.info("=" * 80)
    logger.info("VC发行Oracle服务启动 (同步版)")
    logger.info("=" * 80)
    logger.info(f"HTTP服务器: http://{host}:{port}")
    logger.info(f"  POST /issue-vc - VC发行")
    logger.info(f"  GET /health - 健康检查")
    logger.info("=" * 80)

    # 启动Flask应用
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
