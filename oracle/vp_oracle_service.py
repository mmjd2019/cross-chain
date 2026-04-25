#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VP验证Oracle服务主类
协调VC验证流程，从区块链查询UUID并通过Holder完成验证
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Any

from acapy_client import ACAPyClient, ACAPyClientError
from connection_manager import ConnectionManager, ConnectionManagerError
from proof_request_builder import ProofRequestBuilder
from blockchain_client import BlockchainClient


logger = logging.getLogger(__name__)


class VPOracleService:
    """
    VP验证Oracle服务主类

    负责：
    1. 从区块链查询UUID
    2. 协调7阶段VP验证流程
    3. 验证UUID匹配
    4. 返回验证结果
    """

    def __init__(self, config_path: str = "vp_oracle_config.json"):
        """
        初始化VP验证Oracle服务

        参数:
            config_path: 配置文件路径
        """
        logger.info("=" * 70)
        logger.info("初始化VP验证Oracle服务")
        logger.info("=" * 70)

        # 加载配置
        self.config = self._load_config(config_path)
        self.service_config = self.config.get('service', {})
        self.acapy_config = self.config.get('acapy', {})
        self.vc_config = self.config.get('vc_types', {})

        # 初始化 BlockchainClient
        self.blockchain_client = BlockchainClient(
            blockchain_config=self.config.get('blockchain', {}),
            vc_config=self.vc_config
        )

        # 初始化 ACA-Py 客户端
        verifier_config = self.acapy_config.get('verifier', {})
        holder_config = self.acapy_config.get('holder', {})

        self.verifier_client = ACAPyClient(
            admin_url=verifier_config.get('admin_url', 'http://localhost:8082'),
            wallet_name='verifierWallet'
        )

        # 初始化 ConnectionManager（保持原有逻辑，不简化）
        self.connection_manager = ConnectionManager(
            verifier_admin_url=verifier_config.get('admin_url'),
            holder_admin_url=holder_config.get('admin_url'),
            cleanup_interval_seconds=self.service_config.get('cleanup_interval_seconds', 300)
        )

        # 初始化证明请求构造器
        self.proof_request_builder = ProofRequestBuilder(self.vc_config)

        # 服务配置
        self.default_timeout = self.service_config.get('default_timeout_seconds', 120)

        logger.info(f"验证者DID: {verifier_config.get('did')}")
        logger.info(f"支持的VC类型: {list(self.vc_config.keys())}")
        logger.info(f"区块链连接: {self.blockchain_client.is_connected()}")
        logger.info("VP验证Oracle服务初始化完成")
        logger.info("=" * 70)

    def _load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        try:
            config_path = Path(__file__).parent / config_file
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"配置文件 {config_file} 加载成功")
            return config
        except Exception as e:
            logger.error(f"配置文件 {config_file} 加载失败: {e}")
            return {}

    async def start(self):
        """启动服务"""
        await self.connection_manager.start()
        logger.info("VP验证Oracle服务已启动")

    async def stop(self):
        """停止服务"""
        await self.connection_manager.stop()
        await self.verifier_client.close()
        logger.info("VP验证Oracle服务已停止")

    async def verify_vc(self, vc_type: str, vc_hash: str, requested_attributes: List[str],
                       holder_did: Optional[str] = None) -> Dict:
        """
        执行VC验证（7个阶段）

        参数:
            vc_type: VC类型（如 "InspectionReport"）
            vc_hash: VC哈希（66位十六进制，含0x前缀）
            requested_attributes: 请求的属性列表
            holder_did: 可选的Holder DID（用于连接复用）

        返回:
            验证结果字典，包含:
            - verification_id: 验证ID
            - status: verified/failed
            - verified: 布尔值
            - vc_type: VC类型
            - vc_hash: VC哈希
            - uuid: UUID（验证成功时）
            - revealed_attributes: 揭示的属性
            - error: 错误信息（失败时）
        """
        verification_id = str(uuid.uuid4())
        logger.info(f"[{verification_id}] 开始VP验证流程")
        logger.info(f"[{verification_id}] VC类型: {vc_type}")
        logger.info(f"[{verification_id}] VC哈希: {vc_hash}")
        logger.info(f"[{verification_id}] 请求属性: {requested_attributes}")

        start_time = datetime.now()

        try:
            # 阶段1: 准备阶段 - 验证输入，从区块链获取UUID，获取/创建连接
            logger.info(f"[{verification_id}] 阶段1: 准备阶段")
            phase1_result = await self._phase1_preparation(
                verification_id, vc_type, vc_hash, requested_attributes, holder_did
            )

            # 阶段2: 构造证明请求
            logger.info(f"[{verification_id}] 阶段2: 构造证明请求")
            phase2_result = await self._phase2_construct_proof_request(phase1_result)

            # 阶段3: 发送证明请求
            logger.info(f"[{verification_id}] 阶段3: 发送证明请求")
            phase3_result = await self._phase3_send_proof_request(
                phase1_result['connection_id'],
                phase2_result['proof_request']
            )

            # 阶段4: 等待Holder展示
            logger.info(f"[{verification_id}] 阶段4: 等待Holder展示")
            phase4_result = await self._phase4_await_holder_presentation(
                verification_id, phase3_result['pres_ex_id'], self.default_timeout
            )

            # 阶段5: 验证展示
            logger.info(f"[{verification_id}] 阶段5: 验证展示")
            phase5_result = await self._phase5_verify_presentation(
                verification_id, phase3_result['pres_ex_id']
            )

            # 阶段6: 处理验证结果（含UUID匹配验证）
            logger.info(f"[{verification_id}] 阶段6: 处理验证结果")
            expected_uuid = phase1_result.get('_expected_uuid')
            phase6_result = await self._phase6_process_verification_result(
                verification_id, phase3_result['pres_ex_id'],
                phase5_result, expected_uuid=expected_uuid
            )

            # 阶段7: 生成最终响应
            logger.info(f"[{verification_id}] 阶段7: 生成最终响应")
            final_result = await self._phase7_generate_final_response(
                verification_id, vc_type, vc_hash, phase6_result, start_time
            )

            logger.info(f"[{verification_id}] VP验证完成: {final_result['status']}")
            return final_result

        except Exception as e:
            logger.error(f"[{verification_id}] VP验证失败: {e}", exc_info=True)
            duration = (datetime.now() - start_time).total_seconds()
            return {
                'verification_id': verification_id,
                'status': 'failed',
                'verified': False,
                'error': str(e),
                'duration_seconds': duration
            }

    async def _phase1_preparation(self, verification_id: str, vc_type: str,
                                  vc_hash: str, requested_attributes: List[str],
                                  holder_did: Optional[str]) -> Dict:
        """阶段1: 准备阶段"""
        # 验证VC类型
        if vc_type not in self.vc_config:
            raise ValueError(f"不支持的VC类型: {vc_type}")

        # 验证vc_hash格式
        if not self._validate_vc_hash(vc_hash):
            raise ValueError("vc_hash格式无效，应为66位十六进制字符串（含0x前缀）")

        # 验证属性
        vc_attrs = self.vc_config[vc_type].get('attributes', [])
        for attr in requested_attributes:
            if attr not in vc_attrs:
                raise ValueError(f"属性 {attr} 不在VC类型 {vc_type} 中")

        # 从区块链获取UUID
        logger.info(f"[{verification_id}] 从区块链查询UUID...")
        expected_uuid = self.blockchain_client.get_vc_uuid(vc_type, vc_hash)
        if not expected_uuid:
            raise ValueError(f"无法从区块链获取 vc_hash={vc_hash} 对应的UUID")

        logger.info(f"[{verification_id}] 从区块链提取UUID: {expected_uuid}")

        # 获取或创建连接（使用 ConnectionManager 原有逻辑）
        logger.info(f"[{verification_id}] 获取/创建连接...")
        connection_id = await self.connection_manager.get_or_create_connection(holder_did)
        if not connection_id:
            raise ConnectionError("无法建立与Holder的连接")

        logger.info(f"[{verification_id}] 使用连接: {connection_id}")

        return {
            'connection_id': connection_id,
            'vc_type': vc_type,
            'requested_attributes': requested_attributes,
            '_expected_uuid': expected_uuid
        }

    async def _phase2_construct_proof_request(self, phase1_result: Dict) -> Dict:
        """阶段2: 构造证明请求"""
        vc_type = phase1_result['vc_type']
        requested_attributes = phase1_result['requested_attributes'].copy()
        expected_uuid = phase1_result.get('_expected_uuid')

        # 构造属性值过滤器（如果有expected_uuid）
        attribute_filters = None
        if expected_uuid:
            # 确保contractName在请求属性中
            if 'contractName' not in requested_attributes:
                requested_attributes.append('contractName')
                logger.info("自动添加 contractName 到请求属性（用于UUID匹配）")

            # 添加UUID值过滤，确保Holder选择正确的VC
            attribute_filters = {'contractName': expected_uuid}
            logger.info(f"添加contractName值过滤: {expected_uuid}")

        # 构造证明请求
        if vc_type == 'InspectionReport':
            proof_request = self.proof_request_builder.build_inspection_report_request(
                requested_attributes=requested_attributes,
                name=f"验证{vc_type}",
                version="1.0",
                attribute_filters=attribute_filters
            )
        else:
            proof_request = self.proof_request_builder.build_custom_proof_request(
                vc_type=vc_type,
                requested_attributes=requested_attributes,
                name=f"验证{vc_type}",
                attribute_filters=attribute_filters
            )

        logger.debug(f"证明请求: {proof_request['name']}")

        return {'proof_request': proof_request}

    async def _phase3_send_proof_request(self, connection_id: str,
                                        proof_request: Dict) -> Dict:
        """阶段3: 发送证明请求（使用AIP 2.0，与vp_verification_auto.py一致）"""
        # 使用 AIP 2.0 API（与 vp_verification_auto.py 一致）
        pres_ex_id = await self.verifier_client.send_proof_request_v2(
            connection_id=connection_id,
            proof_request=proof_request,
            auto_verify=True
        )

        logger.info(f"证明请求已发送，pres_ex_id: {pres_ex_id}")

        return {'pres_ex_id': pres_ex_id, 'connection_id': connection_id}

    async def _phase4_await_holder_presentation(self, verification_id: str,
                                               pres_ex_id: str, timeout: int) -> Dict:
        """阶段4: 等待Holder展示（使用AIP 2.0 API，处理auto_remove）"""
        logger.info(f"等待Holder展示，超时: {timeout}秒")

        start_time = datetime.now()
        check_interval = 0.5  # 与vp_verification_auto.py一致

        # 保存最后一次成功获取的presentation exchange
        last_pres_ex = None

        while (datetime.now() - start_time).total_seconds() < timeout:
            try:
                pres_ex = await self.verifier_client.get_presentation_exchange_v2(pres_ex_id)
                last_pres_ex = pres_ex  # 保存最新结果
                state = pres_ex.get('state')

                logger.debug(f"Presentation状态: {state}")

                if state == 'done':
                    logger.info(f"验证完成 (state=done)")
                    return {'presentation_state': state, 'presentation_exchange': pres_ex}
                elif state == 'presentation_received':
                    logger.info(f"收到Presentation，正在验证...")
                elif state in ['abandoned', 'failed']:
                    raise Exception(f"Holder放弃了证明请求 (state={state})")

                await asyncio.sleep(check_interval)

            except ACAPyClientError as e:
                # 处理auto_remove导致的404（与vp_verification_auto.py一致）
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > 1 and last_pres_ex:  # 至少等待1秒且有保存的结果
                    logger.info(f"验证完成 (记录已auto_remove), 耗时: {elapsed:.2f}秒")
                    # 使用最后一次成功获取的结果
                    last_pres_ex['state'] = 'done_deleted'
                    return {'presentation_state': 'done', 'presentation_exchange': last_pres_ex}
                elif elapsed > 1:
                    # 没有保存的结果，但已经过了足够时间，认为验证完成
                    logger.info(f"验证完成 (记录已auto_remove, 无保存结果), 耗时: {elapsed:.2f}秒")
                    return {'presentation_state': 'done', 'presentation_exchange': {'state': 'done_deleted', 'verified': 'true'}}
                logger.warning(f"获取presentation状态失败: {e}")
                await asyncio.sleep(check_interval)

        raise TimeoutError(f"等待展示超时（{timeout}秒）")

    async def _phase5_verify_presentation(self, verification_id: str,
                                        pres_ex_id: str) -> Dict:
        """阶段5: 验证展示（使用AIP 2.0 API）"""
        logger.info("获取验证结果（AIP 2.0格式）")

        # 尝试获取presentation exchange（可能已被auto_remove删除）
        try:
            pres_ex = await self.verifier_client.get_presentation_exchange_v2(pres_ex_id)
            verified = pres_ex.get('verified')
            state = pres_ex.get('state')

            logger.info(f"验证结果: verified={verified}, state={state}")

            return {
                'verified': verified == 'true' or verified is True,
                'state': state,
                'presentation_exchange': pres_ex
            }
        except ACAPyClientError as e:
            # 记录已被删除，说明验证已完成
            logger.info(f"记录已被删除，验证已完成: {e}")
            return {
                'verified': True,
                'state': 'done_deleted',
                'presentation_exchange': {'state': 'done_deleted', 'verified': 'true'}
            }

    async def _phase6_process_verification_result(self, verification_id: str,
                                                  pres_ex_id: str, phase5_result: Dict,
                                                  expected_uuid: Optional[str]) -> Dict:
        """阶段6: 处理验证结果（含UUID匹配验证，AIP 2.0格式）"""
        pres_ex = phase5_result['presentation_exchange']

        # 提取revealed_attrs（AIP 2.0格式，与vp_verification_auto.py一致）
        by_format = pres_ex.get('by_format', {})
        pres = by_format.get('pres', {})
        indy = pres.get('indy', {})

        requested_proof = indy.get('requested_proof', {})
        revealed_attrs = requested_proof.get('revealed_attrs', {})

        logger.info(f"揭示的属性数量: {len(revealed_attrs)}")

        # 解析属性值（AIP 2.0格式）
        requested_attributes = {}
        for attr_ref, attr_data in revealed_attrs.items():
            # AIP 2.0格式: {"sub_proof_index": 0, "raw": "value", "encoded": "..."}
            # 属性名在attr_ref中，格式为 "attr_{index}_{attr_name}"
            if isinstance(attr_data, dict):
                # 尝试从attr_ref中提取属性名
                # attr_ref格式: "attr_0_exporter" 或 "attr_2_contractName"
                if '_' in attr_ref:
                    # 去掉 "attr_{index}_" 前缀，获取真实属性名
                    parts = attr_ref.split('_', 2)  # 最多分割成3部分
                    if len(parts) >= 3:
                        attr_name = parts[2]  # 第三部分是真实属性名
                    else:
                        attr_name = attr_ref
                else:
                    attr_name = attr_ref
                attr_value = attr_data.get('raw', '')
            else:
                attr_name = attr_ref
                attr_value = str(attr_data)
            requested_attributes[attr_name] = attr_value
            logger.debug(f"  {attr_name}: {attr_value}")

        # UUID验证
        if expected_uuid:
            logger.info(f"[{verification_id}] 验证UUID匹配...")
            matched_contract_name = requested_attributes.get('contractName', '')

            if matched_contract_name == expected_uuid:
                logger.info(f"[{verification_id}] UUID匹配成功: {expected_uuid}")
            else:
                error_msg = f'UUID不匹配: 预期 {expected_uuid}, 实际 {matched_contract_name or "未找到"}'
                logger.error(f"[{verification_id}] {error_msg}")
                return {
                    'verified': False,
                    'error': error_msg,
                    'expected_uuid': expected_uuid,
                    'actual_contract_name': matched_contract_name
                }

        return {
            'verified': phase5_result['verified'],
            'revealed_attributes': requested_attributes
        }

    async def _phase7_generate_final_response(self, verification_id: str, vc_type: str,
                                             vc_hash: str, phase6_result: Dict,
                                             start_time: datetime) -> Dict:
        """阶段7: 生成最终响应"""
        duration = (datetime.now() - start_time).total_seconds()

        result = {
            'verification_id': verification_id,
            'status': 'verified' if phase6_result['verified'] else 'failed',
            'verified': phase6_result['verified'],
            'vc_type': vc_type,
            'vc_hash': vc_hash,
            'revealed_attributes': phase6_result.get('revealed_attributes', {}),
            'duration_seconds': round(duration, 2),
            'timestamp': datetime.now().isoformat()
        }

        # 添加UUID（如果存在）
        if 'contractName' in phase6_result.get('revealed_attributes', {}):
            result['uuid'] = phase6_result['revealed_attributes']['contractName']

        # 添加错误信息（如果失败）
        if not phase6_result['verified'] and 'error' in phase6_result:
            result['error'] = phase6_result['error']

        return result

    def _validate_vc_hash(self, vc_hash: str) -> bool:
        """验证vc_hash格式: 66位十六进制（含0x前缀）"""
        return isinstance(vc_hash, str) and len(vc_hash) == 66 and vc_hash.startswith('0x')

    def get_supported_vc_types(self) -> List[str]:
        """获取支持的VC类型列表"""
        return list(self.vc_config.keys())

    def get_vc_attributes(self, vc_type: str) -> Optional[List[str]]:
        """获取VC类型的可用属性"""
        if vc_type in self.vc_config:
            return self.vc_config[vc_type].get('attributes', [])
        return None

    def get_vc_config(self, vc_type: str) -> Optional[Dict]:
        """获取VC类型的完整配置"""
        if vc_type in self.vc_config:
            return self.vc_config[vc_type]
        return None
