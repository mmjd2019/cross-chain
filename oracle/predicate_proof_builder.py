#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
谓词证明请求构造器
构建包含谓词验证的proof_request，支持零知识证明验证

与现有 proof_request_builder.py 的区别:
- 现有: 只支持属性披露（revealed_attributes）
- 新增: 支持谓词验证（predicates），Verifier只获得"属性是否满足条件"的结果
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class PredicateProofBuilderError(Exception):
    """谓词证明请求构造错误"""
    pass


# 支持的谓词操作符
VALID_OPERATORS = ['==', '!=', '>', '>=', '<', '<=']


class PredicateProofBuilder:
    """
    谓词证明请求构造器

    功能:
    - 构建包含谓词的证明请求
    - 支持操作符: ==, !=, >, >=, <, <=
    - 支持布尔值、整数、字符串类型的谓词
    - 从配置文件加载谓词策略
    - 支持混合模式（部分属性披露 + 部分谓词验证）
    """

    def __init__(self, vc_config: Dict, predicate_policies: Dict):
        """
        初始化谓词证明请求构造器

        参数:
            vc_config: VC类型配置字典
                {
                    "InspectionReport": {
                        "schema_id": "...",
                        "cred_def_id": "...",
                        "attributes": [...]
                    },
                    ...
                }
            predicate_policies: 谓词策略配置
                {
                    "InspectionReport": {
                        "attributes_to_reveal": ["exporter", "contractName"],
                        "predicates": {
                            "inspection_passed": {
                                "attribute": "inspectionPassed",
                                "operator": "==",
                                "value": 1,
                                "description": "检验必须通过"
                            }
                        }
                    },
                    ...
                }
        """
        self.vc_config = vc_config
        self.predicate_policies = predicate_policies
        logger.info("谓词证明请求构造器初始化完成")
        logger.info(f"已加载 {len(self.predicate_policies)} 种VC类型的谓词策略")

    def build_predicate_proof_request(
        self,
        vc_type: str,
        attributes_to_reveal: List[str],
        predicates: Dict[str, Dict],
        attribute_filters: Optional[Dict[str, str]] = None,
        attribute_restrictions: Optional[Dict[str, Dict]] = None,
        name: Optional[str] = None,
        version: str = "1.0"
    ) -> Dict:
        """
        构建包含谓词的证明请求

        参数:
            vc_type: VC类型（如 "InspectionReport"）
            attributes_to_reveal: 需要披露的属性列表
                如 ["exporter", "contractName", "productName"]
            predicates: 谓词定义字典
                {
                    "pred_key": {
                        "attribute": "inspectionPassed",
                        "operator": "==",
                        "value": 1
                    },
                    ...
                }
            attribute_filters: 可选的属性值过滤器
                如 {"contractName": "uuid-value"}，用于UUID匹配
            attribute_restrictions: 可选的属性限制条件（零知识过滤）
                {
                    "restriction_key": {
                        "attribute": "inspectionPassed",
                        "value": "true",
                        "description": "检验必须通过"
                    },
                    ...
                }
            name: 请求名称（默认使用VC类型名称）
            version: 请求版本

        返回:
            proof_request字典，包含:
            - name: 请求名称
            - version: 版本
            - requested_attributes: 需要披露的属性
            - requested_predicates: 谓词验证条件

        异常:
            PredicateProofBuilderError: 构造失败
        """
        if vc_type not in self.vc_config:
            raise PredicateProofBuilderError(f"不支持的VC类型: {vc_type}")

        vc_cfg = self.vc_config[vc_type]
        valid_attrs = vc_cfg.get("attributes", [])

        # 验证属性
        invalid_attrs = [attr for attr in attributes_to_reveal if attr not in valid_attrs]
        if invalid_attrs:
            raise PredicateProofBuilderError(
                f"属性 {invalid_attrs} 不在VC类型 {vc_type} 中. "
                f"有效属性: {valid_attrs}"
            )

        # 验证谓词属性
        for pred_key, pred_def in predicates.items():
            attr_name = pred_def.get("attribute")
            if attr_name not in valid_attrs:
                raise PredicateProofBuilderError(
                    f"谓词 {pred_key} 的属性 {attr_name} 不在VC类型 {vc_type} 中"
                )

        # 获取默认restrictions
        restrictions = self._get_default_restrictions(vc_type)

        # 构造 requested_attributes
        requested_attrs_obj = {}

        for i, attr_name in enumerate(attributes_to_reveal):
            attr_key = f"attr_{i}_{attr_name}"

            # 为每个属性创建restrictions副本
            attr_restrictions = [r.copy() for r in restrictions]

            # 1. 添加UUID过滤（来自attribute_filters）- 按原有逻辑，只添加到匹配的属性
            if attribute_filters and attr_name in attribute_filters:
                for attr_restriction in attr_restrictions:
                    filter_key = f"attr::{attr_name}::value"
                    attr_restriction[filter_key] = attribute_filters[attr_name]
                    logger.debug(f"添加属性值过滤: {filter_key} = {attribute_filters[attr_name]}")

            # 2. 添加额外属性限制（来自attribute_restrictions）
            # 这些限制条件作为全局凭证过滤，添加到每个披露属性上
            # 这样可以确保 Holder 选择的凭证满足所有条件，即使某些属性不在披露列表中
            if attribute_restrictions:
                for restr_key, restr_def in attribute_restrictions.items():
                    restr_attr = restr_def.get("attribute")
                    restr_value = restr_def.get("value")
                    if restr_attr and restr_value is not None:
                        restriction_entry = f"attr::{restr_attr}::value"
                        for attr_restriction in attr_restrictions:
                            attr_restriction[restriction_entry] = restr_value
                        logger.debug(f"添加限制条件: {restr_key} -> {restr_attr}={restr_value}")

            requested_attrs_obj[attr_key] = {
                "name": attr_name,
                "restrictions": attr_restrictions
            }

        # 记录限制条件应用情况
        restr_count = len(attribute_restrictions) if attribute_restrictions else 0
        filter_count = len(attribute_filters) if attribute_filters else 0
        logger.info(f"限制条件: {restr_count}个attribute_restrictions, {filter_count}个attribute_filters")

        # 构造 requested_predicates
        requested_preds_obj = {}
        for i, (pred_key, pred_def) in enumerate(predicates.items()):
            attr_name = pred_def.get("attribute")
            operator = pred_def.get("operator", "==")
            value = pred_def.get("value")

            if operator not in VALID_OPERATORS:
                raise PredicateProofBuilderError(
                    f"不支持的操作符: {operator}. 支持的操作符: {VALID_OPERATORS}"
                )

            if value is None:
                raise PredicateProofBuilderError(f"谓词 {pred_key} 缺少 value 字段")

            # 转换值类型
            p_value = self._convert_predicate_value(value, attr_name, vc_type)

            # 为谓词创建独立的restrictions副本
            pred_restrictions = [r.copy() for r in restrictions]

            # 1. 添加UUID过滤（如果谓词属性匹配attribute_filters的键）
            if attribute_filters and attr_name in attribute_filters:
                for pred_restriction in pred_restrictions:
                    filter_key = f"attr::{attr_name}::value"
                    pred_restriction[filter_key] = attribute_filters[attr_name]

            # 2. 添加额外属性限制（来自attribute_restrictions）
            if attribute_restrictions:
                for restr_key, restr_def in attribute_restrictions.items():
                    restr_attr = restr_def.get("attribute")
                    restr_value = restr_def.get("value")
                    if restr_attr and restr_value is not None:
                        restriction_entry = f"attr::{restr_attr}::value"
                        for pred_restriction in pred_restrictions:
                            pred_restriction[restriction_entry] = restr_value

            pred_internal_key = f"pred_{i}_{pred_key}"
            requested_preds_obj[pred_internal_key] = {
                "name": attr_name,
                "p_type": operator,
                "p_value": p_value,
                "restrictions": pred_restrictions
            }

            logger.debug(f"添加谓词: {pred_key} -> {attr_name} {operator} {p_value}")

        # 构造proof_request
        proof_request = {
            "name": name or f"{vc_type}谓词验证",
            "version": version,
            "requested_attributes": requested_attrs_obj,
            "requested_predicates": requested_preds_obj
        }

        restr_count = len(attribute_restrictions) if attribute_restrictions else 0
        logger.info(
            f"构造{vc_type}谓词证明请求: "
            f"{len(attributes_to_reveal)}个披露属性, "
            f"{len(predicates)}个谓词, "
            f"{restr_count}个限制条件"
        )

        return proof_request

    def build_predicate_proof_request_from_policy(
        self,
        vc_type: str,
        attribute_filters: Optional[Dict[str, str]] = None,
        custom_predicates: Optional[Dict[str, Dict]] = None,
        custom_attributes_to_reveal: Optional[List[str]] = None,
        custom_attribute_restrictions: Optional[Dict[str, Dict]] = None
    ) -> Dict:
        """
        从配置的策略构建谓词证明请求

        参数:
            vc_type: VC类型
            attribute_filters: 可选的属性值过滤器（如UUID）
            custom_predicates: 自定义谓词（覆盖默认策略）
            custom_attributes_to_reveal: 自定义披露属性列表（覆盖默认策略）
            custom_attribute_restrictions: 自定义属性限制条件（覆盖默认策略）

        返回:
            proof_request字典

        异常:
            PredicateProofBuilderError: 构造失败
        """
        # 获取默认策略
        policy = self.get_predicate_policy(vc_type)

        # 使用自定义值或默认值
        attributes_to_reveal = custom_attributes_to_reveal or policy.get("attributes_to_reveal", [])
        predicates = custom_predicates or policy.get("predicates", {})
        # 修复：使用 is not None 判断，允许传入空字典 {} 来跳过 attribute_restrictions
        if custom_attribute_restrictions is not None:
            attribute_restrictions = custom_attribute_restrictions
        else:
            attribute_restrictions = policy.get("attribute_restrictions", {})

        # 如果没有指定任何属性或谓词，使用所有属性披露
        if not attributes_to_reveal and not predicates:
            vc_cfg = self.vc_config.get(vc_type, {})
            attributes_to_reveal = vc_cfg.get("attributes", [])
            logger.info(f"使用所有属性披露: {len(attributes_to_reveal)}个")

        return self.build_predicate_proof_request(
            vc_type=vc_type,
            attributes_to_reveal=attributes_to_reveal,
            predicates=predicates,
            attribute_filters=attribute_filters,
            attribute_restrictions=attribute_restrictions if attribute_restrictions else None
        )

    def get_predicate_policy(self, vc_type: str) -> Dict:
        """
        获取VC类型的默认谓词策略

        参数:
            vc_type: VC类型

        返回:
            谓词策略字典，包含:
            - attributes_to_reveal: 需要披露的属性列表
            - predicates: 谓词定义字典

        异常:
            PredicateProofBuilderError: VC类型不支持
        """
        if vc_type not in self.vc_config:
            raise PredicateProofBuilderError(f"不支持的VC类型: {vc_type}")

        # 返回配置的策略，如果没有则返回空策略
        policy = self.predicate_policies.get(vc_type, {})

        if not policy:
            logger.warning(f"VC类型 {vc_type} 没有配置谓词策略，将使用空策略")
            return {"attributes_to_reveal": [], "predicates": {}}

        return policy

    def get_supported_vc_types(self) -> List[str]:
        """获取支持的VC类型列表"""
        return list(self.vc_config.keys())

    def get_vc_attributes(self, vc_type: str) -> List[str]:
        """获取VC类型的可用属性"""
        if vc_type not in self.vc_config:
            raise PredicateProofBuilderError(f"不支持的VC类型: {vc_type}")
        return self.vc_config[vc_type].get("attributes", [])

    def validate_predicate(self, predicate: Dict, vc_type: str) -> bool:
        """
        验证谓词定义是否有效

        参数:
            predicate: 谓词定义
            vc_type: VC类型

        返回:
            是否有效

        异常:
            PredicateProofBuilderError: 验证失败时抛出异常
        """
        required_fields = ["attribute", "operator", "value"]
        for field in required_fields:
            if field not in predicate:
                raise PredicateProofBuilderError(f"谓词缺少必需字段: {field}")

        if predicate["operator"] not in VALID_OPERATORS:
            raise PredicateProofBuilderError(
                f"不支持的操作符: {predicate['operator']}. 支持的操作符: {VALID_OPERATORS}"
            )

        # 验证属性存在
        valid_attrs = self.get_vc_attributes(vc_type)
        if predicate["attribute"] not in valid_attrs:
            raise PredicateProofBuilderError(
                f"属性 {predicate['attribute']} 不在VC类型 {vc_type} 中"
            )

        return True

    def _get_default_restrictions(self, vc_type: str) -> List[Dict]:
        """
        获取VC类型的默认restrictions

        参数:
            vc_type: VC类型

        返回:
            restrictions列表
        """
        if vc_type not in self.vc_config:
            raise PredicateProofBuilderError(f"不支持的VC类型: {vc_type}")

        vc_cfg = self.vc_config[vc_type]
        restriction = {}

        # 添加schema_id
        if "schema_id" in vc_cfg:
            restriction["schema_id"] = vc_cfg["schema_id"]

        # 添加cred_def_id
        if "cred_def_id" in vc_cfg:
            restriction["cred_def_id"] = vc_cfg["cred_def_id"]

        # 添加issuer_did（从schema_id中提取）
        if "schema_id" in vc_cfg:
            schema_id = vc_cfg["schema_id"]
            issuer_did = schema_id.split(":")[0] if ":" in schema_id else None
            if issuer_did:
                restriction["issuer_did"] = issuer_did

        return [restriction]

    def _convert_predicate_value(self, value: Any, attr_name: str, vc_type: str) -> int:
        """
        转换谓词值为整数（ACA-Py要求）

        在Hyperledger Indy中，所有谓词值都必须是整数:
        - 布尔值: true=1, false=0
        - 整数: 保持不变
        - 字符串: 不支持谓词（抛出异常）

        参数:
            value: 原始值
            attr_name: 属性名
            vc_type: VC类型

        返回:
            整数值

        异常:
            PredicateProofBuilderError: 不支持的类型
        """
        if isinstance(value, bool):
            return 1 if value else 0
        elif isinstance(value, int):
            return value
        elif isinstance(value, str):
            # 尝试解析字符串
            if value.lower() == "true":
                return 1
            elif value.lower() == "false":
                return 0
            else:
                try:
                    return int(value)
                except ValueError:
                    raise PredicateProofBuilderError(
                        f"属性 {attr_name} 的谓词值 '{value}' 无法转换为整数. "
                        f"Indy只支持整数类型的谓词验证"
                    )
        else:
            raise PredicateProofBuilderError(
                f"属性 {attr_name} 的谓词值类型 {type(value)} 不支持"
            )

    def describe_predicate_policy(self, vc_type: str) -> str:
        """
        生成谓词策略的人类可读描述

        参数:
            vc_type: VC类型

        返回:
            描述字符串
        """
        policy = self.get_predicate_policy(vc_type)

        lines = [f"VC类型: {vc_type}"]

        attrs = policy.get("attributes_to_reveal", [])
        if attrs:
            lines.append(f"披露属性: {', '.join(attrs)}")
        else:
            lines.append("披露属性: 无")

        predicates = policy.get("predicates", {})
        if predicates:
            lines.append("谓词验证:")
            for pred_key, pred_def in predicates.items():
                attr = pred_def.get("attribute")
                op = pred_def.get("operator")
                val = pred_def.get("value")
                desc = pred_def.get("description", "")
                lines.append(f"  - {pred_key}: {attr} {op} {val}" + (f" ({desc})" if desc else ""))
        else:
            lines.append("谓词验证: 无")

        attribute_restrictions = policy.get("attribute_restrictions", {})
        if attribute_restrictions:
            lines.append("限制条件过滤（零知识）:")
            for restr_key, restr_def in attribute_restrictions.items():
                attr = restr_def.get("attribute")
                val = restr_def.get("value")
                desc = restr_def.get("description", "")
                lines.append(f"  - {restr_key}: {attr} = {val}" + (f" ({desc})" if desc else ""))
        else:
            lines.append("限制条件过滤: 无")

        return "\n".join(lines)

    def list_all_predicates(self) -> Dict[str, List[str]]:
        """
        列出所有VC类型配置的谓词

        返回:
            {vc_type: [predicate_keys]}
        """
        result = {}
        for vc_type in self.predicate_policies:
            policy = self.predicate_policies[vc_type]
            predicates = policy.get("predicates", {})
            result[vc_type] = list(predicates.keys())
        return result
