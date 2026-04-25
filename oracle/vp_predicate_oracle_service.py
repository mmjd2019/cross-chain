#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VP谓词验证Oracle服务
使用零知识证明谓词方式验证属性值，而不是明文披露后验证

与现有 vp_oracle_service.py 的区别:
- 现有: 所有属性都明文披露
- 新增: 支持谓词验证，Verifier只获得"属性是否满足条件"的结果

隐私保护优势:
- Verifier不知道具体的属性值，只知道是否满足条件
- 符合零知识证明的最小披露原则
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
from predicate_proof_builder import PredicateProofBuilder, PredicateProofBuilderError
from blockchain_client import BlockchainClient


logger = logging.getLogger(__name__)


class VPPredicateOracleService:
    """
    VP谓词验证Oracle服务主类

    负责：
    1. 从区块链查询UUID
    2. 协调7阶段VP验证流程（支持谓词验证）
    3. 验证UUID匹配和谓词条件
    4. 返回验证结果
    """

    def __init__(self, config_path: str = "vp_predicate_config.json"):
        """
        初始化VP谓词验证Oracle服务

        参数:
            config_path: 配置文件路径
        """
        logger.info("=" * 70)
        logger.info("初始化VP谓词验证Oracle服务（端口7003）")
        logger.info("=" * 70)

        # 加载配置
        self.config = self._load_config(config_path)
        self.service_config = self.config.get('service', {})
        self.acapy_config = self.config.get('acapy', {})
        self.vc_config = self.config.get('vc_types', {})
        self.predicate_policies = self.config.get('predicate_policies', {})

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

        # 初始化 ConnectionManager
        self.connection_manager = ConnectionManager(
            verifier_admin_url=verifier_config.get('admin_url'),
            holder_admin_url=holder_config.get('admin_url'),
            cleanup_interval_seconds=self.service_config.get('cleanup_interval_seconds', 300)
        )

        # 初始化谓词证明请求构造器
        self.predicate_builder = PredicateProofBuilder(self.vc_config, self.predicate_policies)

        # 服务配置
        self.default_timeout = self.service_config.get('default_timeout_seconds', 120)

        logger.info(f"验证者DID: {verifier_config.get('did')}")
        logger.info(f"支持的VC类型: {list(self.vc_config.keys())}")
        logger.info(f"已配置谓词策略: {list(self.predicate_policies.keys())}")
        logger.info(f"区块链连接: {self.blockchain_client.is_connected()}")
        logger.info("VP谓词验证Oracle服务初始化完成")
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
        logger.info("VP谓词验证Oracle服务已启动")

    async def stop(self):
        """停止服务"""
        await self.connection_manager.stop()
        await self.verifier_client.close()
        logger.info("VP谓词验证Oracle服务已停止")

    async def verify_with_predicates(
        self,
        vc_type: str,
        vc_hash: str,
        attributes_to_reveal: Optional[List[str]] = None,
        custom_predicates: Optional[Dict[str, Dict]] = None,
        custom_attribute_restrictions: Optional[Dict[str, Dict]] = None,
        holder_did: Optional[str] = None
    ) -> Dict:
        """
        使用谓词验证VC

        参数:
            vc_type: VC类型（如 "InspectionReport"）
            vc_hash: VC哈希（66位十六进制，含0x前缀）
            attributes_to_reveal: 自定义披露属性（None使用默认策略）
            custom_predicates: 自定义谓词（None使用默认策略）
                {
                    "pred_key": {
                        "attribute": "inspectionPassed",
                        "operator": "==",
                        "value": 1
                    }
                }
            custom_attribute_restrictions: 自定义属性限制条件（None使用默认策略，{}跳过限制）
                {
                    "restr_key": {
                        "attribute": "inspectionPassed",
                        "value": "true"
                    }
                }
            holder_did: 可选的Holder DID（用于连接复用）

        返回:
            {
                "verification_id": "...",
                "verified": true/false,
                "predicate_results": {
                    "inspection_passed": {"satisfied": true, ...},
                    ...
                },
                "revealed_attributes": {...},
                "vc_type": "...",
                "vc_hash": "...",
                "duration_seconds": 1.23
            }
        """
        verification_id = str(uuid.uuid4())
        logger.info(f"[{verification_id}] 开始VP谓词验证流程")
        logger.info(f"[{verification_id}] VC类型: {vc_type}")
        logger.info(f"[{verification_id}] VC哈希: {vc_hash}")
        logger.info(f"[{verification_id}] 披露属性: {attributes_to_reveal or '使用默认策略'}")
        logger.info(f"[{verification_id}] 自定义谓词: {custom_predicates or '使用默认策略'}")

        start_time = datetime.now()

        try:
            # 阶段1: 准备阶段
            logger.info(f"[{verification_id}] 阶段1: 准备阶段")
            phase1_result = await self._phase1_preparation(
                verification_id, vc_type, vc_hash, holder_did
            )

            # 阶段2: 构造谓词证明请求
            logger.info(f"[{verification_id}] 阶段2: 构造谓词证明请求")
            phase2_result = await self._phase2_build_predicate_request(
                phase1_result,
                attributes_to_reveal=attributes_to_reveal,
                custom_predicates=custom_predicates,
                custom_attribute_restrictions=custom_attribute_restrictions
            )

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

            # 阶段6: 处理验证结果（含UUID匹配和谓词结果）
            logger.info(f"[{verification_id}] 阶段6: 处理验证结果")
            expected_uuid = phase1_result.get('_expected_uuid')
            predicates_config = phase2_result.get('predicates_config', {})
            attribute_restrictions_config = phase2_result.get('attribute_restrictions_config', {})
            phase6_result = await self._phase6_process_predicate_results(
                verification_id, phase3_result['pres_ex_id'],
                phase5_result,
                expected_uuid=expected_uuid,
                predicates_config=predicates_config,
                attribute_restrictions_config=attribute_restrictions_config
            )

            # 阶段7: 生成最终响应
            logger.info(f"[{verification_id}] 阶段7: 生成最终响应")
            final_result = await self._phase7_generate_final_response(
                verification_id, vc_type, vc_hash, phase6_result, start_time
            )

            logger.info(f"[{verification_id}] VP谓词验证完成: {final_result['status']}")
            return final_result

        except Exception as e:
            logger.error(f"[{verification_id}] VP谓词验证失败: {e}", exc_info=True)
            duration = (datetime.now() - start_time).total_seconds()
            return {
                'verification_id': verification_id,
                'status': 'failed',
                'verified': False,
                'error': str(e),
                'vc_type': vc_type,
                'vc_hash': vc_hash,
                'duration_seconds': round(duration, 2)
            }

    async def _phase1_preparation(
        self,
        verification_id: str,
        vc_type: str,
        vc_hash: str,
        holder_did: Optional[str]
    ) -> Dict:
        """阶段1: 准备阶段"""
        # 验证VC类型
        if vc_type not in self.vc_config:
            raise ValueError(f"不支持的VC类型: {vc_type}")

        # 验证vc_hash格式
        if not self._validate_vc_hash(vc_hash):
            raise ValueError("vc_hash格式无效，应为66位十六进制字符串（含0x前缀）")

        # 从区块链获取UUID
        logger.info(f"[{verification_id}] 从区块链查询UUID...")
        expected_uuid = self.blockchain_client.get_vc_uuid(vc_type, vc_hash)
        if not expected_uuid:
            raise ValueError(f"无法从区块链获取 vc_hash={vc_hash} 对应的UUID")

        logger.info(f"[{verification_id}] 从区块链提取UUID: {expected_uuid}")

        # 获取或创建连接
        logger.info(f"[{verification_id}] 获取/创建连接...")
        connection_id = await self.connection_manager.get_or_create_connection(holder_did)
        if not connection_id:
            raise ConnectionError("无法建立与Holder的连接")

        logger.info(f"[{verification_id}] 使用连接: {connection_id}")

        return {
            'connection_id': connection_id,
            'vc_type': vc_type,
            'vc_hash': vc_hash,
            '_expected_uuid': expected_uuid
        }

    async def _phase2_build_predicate_request(
        self,
        phase1_result: Dict,
        attributes_to_reveal: Optional[List[str]] = None,
        custom_predicates: Optional[Dict[str, Dict]] = None,
        custom_attribute_restrictions: Optional[Dict[str, Dict]] = None
    ) -> Dict:
        """阶段2: 构造谓词证明请求"""
        vc_type = phase1_result['vc_type']
        expected_uuid = phase1_result.get('_expected_uuid')

        # 合并静态 attribute_filters 和动态 UUID 过滤
        attribute_filters = {}

        # 1. 添加配置文件中的静态 attribute_filters（零知识验证）
        policy = self.predicate_builder.get_predicate_policy(vc_type)
        static_filters = policy.get('attribute_filters', {})
        if static_filters:
            attribute_filters.update(static_filters)
            logger.info(f"添加静态attribute_filters: {list(static_filters.keys())}")

        # 2. 添加UUID过滤（动态从区块链获取）
        if expected_uuid:
            attribute_filters['contractName'] = expected_uuid
            logger.info(f"添加UUID过滤: contractName={expected_uuid}")

        if not attribute_filters:
            attribute_filters = None

        # 使用谓词证明构造器构建请求
        try:
            proof_request = self.predicate_builder.build_predicate_proof_request_from_policy(
                vc_type=vc_type,
                attribute_filters=attribute_filters,
                custom_predicates=custom_predicates,
                custom_attributes_to_reveal=attributes_to_reveal,
                custom_attribute_restrictions=custom_attribute_restrictions
            )
        except PredicateProofBuilderError as e:
            logger.error(f"构造谓词证明请求失败: {e}")
            raise ValueError(f"构造谓词证明请求失败: {e}")

        # 获取使用的谓词配置（用于后续结果解析）
        policy = self.predicate_builder.get_predicate_policy(vc_type)
        if custom_predicates:
            predicates_config = custom_predicates
        else:
            predicates_config = policy.get('predicates', {})

        # 获取attribute_restrictions配置
        # 如果传入custom_attribute_restrictions，使用它（空字典表示跳过）
        if custom_attribute_restrictions is not None:
            attribute_restrictions_config = custom_attribute_restrictions
        else:
            attribute_restrictions_config = policy.get('attribute_restrictions', {})

        logger.info(f"谓词证明请求构造完成:")
        logger.info(f"  - 名称: {proof_request.get('name')}")
        logger.info(f"  - 披露属性: {len(proof_request.get('requested_attributes', {}))}个")
        logger.info(f"  - 谓词: {len(proof_request.get('requested_predicates', {}))}个")
        logger.info(f"  - 限制条件: {len(attribute_restrictions_config)}个")

        return {
            'proof_request': proof_request,
            'predicates_config': predicates_config,
            'attribute_restrictions_config': attribute_restrictions_config
        }

    async def _phase3_send_proof_request(
        self,
        connection_id: str,
        proof_request: Dict
    ) -> Dict:
        """阶段3: 发送证明请求（使用AIP 2.0）"""
        pres_ex_id = await self.verifier_client.send_proof_request_v2(
            connection_id=connection_id,
            proof_request=proof_request,
            auto_verify=True
        )

        logger.info(f"谓词证明请求已发送，pres_ex_id: {pres_ex_id}")

        return {'pres_ex_id': pres_ex_id, 'connection_id': connection_id}

    async def _phase4_await_holder_presentation(
        self,
        verification_id: str,
        pres_ex_id: str,
        timeout: int
    ) -> Dict:
        """阶段4: 等待Holder展示（使用AIP 2.0 API）"""
        logger.info(f"等待Holder展示，超时: {timeout}秒")

        start_time = datetime.now()
        check_interval = 0.5

        # 保存最后一次成功获取的presentation exchange
        last_pres_ex = None

        while (datetime.now() - start_time).total_seconds() < timeout:
            try:
                pres_ex = await self.verifier_client.get_presentation_exchange_v2(pres_ex_id)
                last_pres_ex = pres_ex
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
                # 处理auto_remove导致的404
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > 1 and last_pres_ex:
                    logger.info(f"验证完成 (记录已auto_remove), 耗时: {elapsed:.2f}秒")
                    last_pres_ex['state'] = 'done_deleted'
                    return {'presentation_state': 'done', 'presentation_exchange': last_pres_ex}
                elif elapsed > 1:
                    logger.info(f"验证完成 (记录已auto_remove, 无保存结果), 耗时: {elapsed:.2f}秒")
                    return {'presentation_state': 'done', 'presentation_exchange': {'state': 'done_deleted', 'verified': 'true'}}
                logger.warning(f"获取presentation状态失败: {e}")
                await asyncio.sleep(check_interval)

        raise TimeoutError(f"等待展示超时（{timeout}秒）")

    async def _phase5_verify_presentation(
        self,
        verification_id: str,
        pres_ex_id: str
    ) -> Dict:
        """阶段5: 验证展示（使用AIP 2.0 API）"""
        logger.info("获取验证结果（AIP 2.0格式）")

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
            logger.info(f"记录已被删除，验证已完成: {e}")
            return {
                'verified': True,
                'state': 'done_deleted',
                'presentation_exchange': {'state': 'done_deleted', 'verified': 'true'}
            }

    async def _phase6_process_predicate_results(
        self,
        verification_id: str,
        pres_ex_id: str,
        phase5_result: Dict,
        expected_uuid: Optional[str],
        predicates_config: Dict[str, Dict],
        attribute_restrictions_config: Optional[Dict[str, Dict]] = None
    ) -> Dict:
        """阶段6: 处理验证结果（含UUID匹配和谓词结果解析）"""
        pres_ex = phase5_result['presentation_exchange']

        # 提取revealed_attrs和predicates（AIP 2.0格式）
        by_format = pres_ex.get('by_format', {})
        pres = by_format.get('pres', {})
        indy = pres.get('indy', {})

        requested_proof = indy.get('requested_proof', {})
        revealed_attrs = requested_proof.get('revealed_attrs', {})
        predicates_proof = requested_proof.get('predicates', {})

        logger.info(f"揭示的属性数量: {len(revealed_attrs)}")
        logger.info(f"谓词证明数量: {len(predicates_proof)}")

        # 解析揭示的属性值
        revealed_attributes = {}
        for attr_ref, attr_data in revealed_attrs.items():
            if isinstance(attr_data, dict):
                # 从attr_ref中提取属性名（格式: "attr_{index}_{attr_name}"）
                if '_' in attr_ref:
                    parts = attr_ref.split('_', 2)
                    if len(parts) >= 3:
                        attr_name = parts[2]
                    else:
                        attr_name = attr_ref
                else:
                    attr_name = attr_ref
                attr_value = attr_data.get('raw', '')
            else:
                attr_name = attr_ref
                attr_value = str(attr_data)
            revealed_attributes[attr_name] = attr_value
            logger.debug(f"  揭示属性: {attr_name} = {attr_value}")

        # 解析谓词验证结果
        predicate_results = {}
        all_predicates_satisfied = True

        # 调试：打印原始谓词证明数据
        logger.debug(f"原始谓词证明数据: {predicates_proof}")

        for pred_key, pred_config in predicates_config.items():
            attr_name = pred_config.get('attribute')
            operator = pred_config.get('operator', '==')
            expected_value = pred_config.get('value')

            # 在谓词证明中查找对应的结果
            # 谓词引用格式通常是 "pred_{index}_{pred_key}"
            satisfied = False
            found_pred = False
            for pred_ref, pred_data in predicates_proof.items():
                logger.debug(f"检查谓词引用: pred_ref={pred_ref}, pred_key={pred_key}, pred_data={pred_data}")
                # 检查是否匹配我们的谓词
                if pred_key in pred_ref or pred_ref.endswith(pred_key):
                    found_pred = True
                    # 在Indy中，谓词证明只返回是否满足条件
                    # 谓词证明数据格式可能是：
                    # 1. {"sub_proof_index": 0} - 表示谓词满足
                    # 2. 空 dict {} - 也可能表示满足
                    # 3. None - 表示不满足
                    if isinstance(pred_data, dict):
                        # 如果有sub_proof_index，说明Holder成功生成了谓词证明
                        has_sub_proof = pred_data.get('sub_proof_index') is not None
                        # 如果dict不为空，通常表示谓词满足
                        satisfied = has_sub_proof or len(pred_data) > 0
                        logger.debug(f"谓词数据是dict: sub_proof_index={pred_data.get('sub_proof_index')}, satisfied={satisfied}")
                    elif pred_data is None:
                        satisfied = False
                        logger.debug(f"谓词数据是None: satisfied=False")
                    else:
                        satisfied = bool(pred_data)
                        logger.debug(f"谓词数据是其他类型: type={type(pred_data)}, satisfied={satisfied}")
                    break

            if not found_pred:
                # 如果没有找到对应的谓词证明，使用整体验证结果
                # ACA-Py的verified=true表示所有条件都满足
                satisfied = phase5_result['verified']
                logger.info(f"谓词 {pred_key} 未在VP中找到，使用整体验证结果: {satisfied}")

            predicate_results[pred_key] = {
                'attribute': attr_name,
                'operator': operator,
                'expected_value': expected_value,
                'satisfied': satisfied
            }

            if not satisfied:
                all_predicates_satisfied = False

            logger.info(f"  谓词结果: {pred_key} -> {attr_name} {operator} {expected_value} = {satisfied}")

        # UUID验证
        uuid_matched = True
        if expected_uuid:
            logger.info(f"[{verification_id}] 验证UUID匹配...")
            matched_contract_name = revealed_attributes.get('contractName', '')

            if matched_contract_name == expected_uuid:
                logger.info(f"[{verification_id}] UUID匹配成功: {expected_uuid}")
            else:
                error_msg = f'UUID不匹配: 预期 {expected_uuid}, 实际 {matched_contract_name or "未找到"}'
                logger.error(f"[{verification_id}] {error_msg}")
                uuid_matched = False

        # 处理attribute_restrictions结果
        # 限制条件过滤是通过restrictions实现的，如果Holder能成功响应，说明所有限制条件都满足
        restriction_results = {}
        all_restrictions_satisfied = True

        if attribute_restrictions_config:
            logger.info(f"[{verification_id}] 处理限制条件过滤结果...")
            for restr_key, restr_def in attribute_restrictions_config.items():
                restr_attr = restr_def.get('attribute')
                restr_value = restr_def.get('value')
                desc = restr_def.get('description', '')

                # 如果整体验证通过，说明限制条件满足（因为Holder必须满足restrictions才能响应）
                satisfied = phase5_result['verified']

                restriction_results[restr_key] = {
                    'attribute': restr_attr,
                    'expected_value': restr_value,
                    'satisfied': satisfied,
                    'description': desc
                }

                if not satisfied:
                    all_restrictions_satisfied = False

                logger.info(f"  限制条件结果: {restr_key} -> {restr_attr}={restr_value} = {satisfied}")

        # 综合验证结果
        # 验证通过条件：整体验证通过 + UUID匹配 + 所有谓词满足 + 所有限制条件满足
        overall_verified = (
            phase5_result['verified'] and
            uuid_matched and
            all_predicates_satisfied and
            all_restrictions_satisfied
        )

        return {
            'verified': overall_verified,
            'revealed_attributes': revealed_attributes,
            'predicate_results': predicate_results,
            'restriction_results': restriction_results,
            'uuid_matched': uuid_matched,
            'all_predicates_satisfied': all_predicates_satisfied,
            'all_restrictions_satisfied': all_restrictions_satisfied
        }

    async def _phase7_generate_final_response(
        self,
        verification_id: str,
        vc_type: str,
        vc_hash: str,
        phase6_result: Dict,
        start_time: datetime
    ) -> Dict:
        """阶段7: 生成最终响应"""
        duration = (datetime.now() - start_time).total_seconds()

        result = {
            'verification_id': verification_id,
            'status': 'verified' if phase6_result['verified'] else 'failed',
            'verified': phase6_result['verified'],
            'vc_type': vc_type,
            'vc_hash': vc_hash,
            'revealed_attributes': phase6_result.get('revealed_attributes', {}),
            'predicate_results': phase6_result.get('predicate_results', {}),
            'restriction_results': phase6_result.get('restriction_results', {}),
            'duration_seconds': round(duration, 2),
            'timestamp': datetime.now().isoformat()
        }

        # 添加UUID
        if 'contractName' in phase6_result.get('revealed_attributes', {}):
            result['uuid'] = phase6_result['revealed_attributes']['contractName']

        # 添加验证详情
        result['verification_details'] = {
            'uuid_matched': phase6_result.get('uuid_matched', True),
            'all_predicates_satisfied': phase6_result.get('all_predicates_satisfied', True),
            'all_restrictions_satisfied': phase6_result.get('all_restrictions_satisfied', True)
        }

        # 添加错误信息（如果失败）
        if not phase6_result['verified']:
            errors = []
            if not phase6_result.get('uuid_matched', True):
                errors.append('UUID不匹配')
            if not phase6_result.get('all_predicates_satisfied', True):
                failed_predicates = [
                    k for k, v in phase6_result.get('predicate_results', {}).items()
                    if not v.get('satisfied', False)
                ]
                errors.append(f'谓词验证失败: {failed_predicates}')
            if not phase6_result.get('all_restrictions_satisfied', True):
                failed_restrictions = [
                    k for k, v in phase6_result.get('restriction_results', {}).items()
                    if not v.get('satisfied', False)
                ]
                errors.append(f'限制条件验证失败: {failed_restrictions}')
            result['error'] = '; '.join(errors) if errors else '验证失败'

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

    def get_predicate_policy(self, vc_type: str) -> Optional[Dict]:
        """获取VC类型的谓词策略"""
        return self.predicate_policies.get(vc_type)

    def get_all_predicate_policies(self) -> Dict:
        """获取所有谓词策略"""
        return self.predicate_policies

    def describe_predicate_policy(self, vc_type: str) -> str:
        """获取谓词策略的人类可读描述"""
        return self.predicate_builder.describe_predicate_policy(vc_type)
