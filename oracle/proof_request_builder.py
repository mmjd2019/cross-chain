#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
证明请求构造器
构造ACA-Py的proof_request对象，支持多种VC类型
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any


logger = logging.getLogger(__name__)


class ProofRequestBuilderError(Exception):
    """证明请求构造错误"""
    pass


class ProofRequestBuilder:
    """
    证明请求构造器

    负责：
    - 构造符合ACA-Py标准的proof_request
    - 应用restrictions（schema_id、cred_def_id、issuer_did）
    - 设置non_revoked时间范围
    - 支持requested_attributes和requested_predicates
    """

    def __init__(self, vc_config: Dict):
        """
        初始化证明请求构造器

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
        """
        self.vc_config = vc_config
        logger.info("证明请求构造器初始化完成")

    def build_inspection_report_request(
        self,
        requested_attributes: List[str],
        restrictions: Optional[List[Dict]] = None,
        non_revoked: Optional[Dict] = None,
        name: str = "质检报告验证请求",
        version: str = "1.0",
        attribute_filters: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        构造InspectionReport的证明请求

        参数:
            requested_attributes: 请求的属性列表
                如 ["exporter", "contractName", "inspectionPassed"]
            restrictions: 可选的限制条件列表
                如 [{"schema_id": "...", "cred_def_id": "...", "issuer_did": "..."}]
            non_revoked: 可选的撤销验证时间范围
                如 {"from": 0, "to": 1706227200}
            name: 请求名称
            version: 请求版本
            attribute_filters: 可选的属性值过滤器
                如 {"contractName": "9552422d-b95f-4afc-bb83-d2fee4d1935e"}
                用于限制Holder选择特定值的VC

        返回:
            proof_request字典

        异常:
            ProofRequestBuilderError: 构造失败
        """
        vc_type = "InspectionReport"

        if vc_type not in self.vc_config:
            raise ProofRequestBuilderError(f"不支持的VC类型: {vc_type}")

        vc_config = self.vc_config[vc_type]

        # 验证属性
        self._validate_attributes(requested_attributes, vc_type)

        # 使用默认restrictions（如果未提供）
        if restrictions is None:
            restrictions = self._get_default_restrictions(vc_type)

        # 构造requested_attributes
        requested_attrs_obj = {}
        for attr_name in requested_attributes:
            # 为每个属性创建restrictions副本
            attr_restrictions = [r.copy() for r in restrictions] if restrictions else []

            # 如果有属性值过滤器，添加到restrictions中
            if attribute_filters and attr_name in attribute_filters:
                for attr_restriction in attr_restrictions:
                    # ACA-Py属性值过滤格式: attr::ATTRIBUTE_NAME::value
                    filter_key = f"attr::{attr_name}::value"
                    attr_restriction[filter_key] = attribute_filters[attr_name]
                    logger.debug(f"添加属性值过滤: {filter_key} = {attribute_filters[attr_name]}")

            requested_attrs_obj[attr_name] = {
                "name": attr_name,
                "restrictions": attr_restrictions if attr_restrictions else restrictions
            }

        # 构造proof_request
        proof_request = {
            "name": name,
            "version": version,
            "requested_attributes": requested_attrs_obj,
            "requested_predicates": {},  # 暂不支持谓词
        }

        # 添加non_revoked（如果提供）
        if non_revoked:
            proof_request["non_revoked"] = non_revoked

        logger.info(f"构造InspectionReport证明请求: {len(requested_attributes)}个属性")
        logger.debug(f"证明请求: {proof_request}")

        return proof_request

    def build_custom_proof_request(
        self,
        vc_type: str,
        requested_attributes: List[str],
        requested_predicates: Optional[Dict] = None,
        restrictions: Optional[List[Dict]] = None,
        non_revoked: Optional[Dict] = None,
        name: Optional[str] = None,
        version: str = "1.0",
        attribute_filters: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        构造自定义VC类型的证明请求

        参数:
            vc_type: VC类型名称
            requested_attributes: 请求的属性列表
            requested_predicates: 可选的谓词证明
                如 {"age_predicate": {"name": "age", "p_type": ">=", "p_value": 18}}
            restrictions: 可选的限制条件
            non_revoked: 可选的撤销验证时间范围
            name: 请求名称（默认使用VC类型名称）
            version: 请求版本
            attribute_filters: 可选的属性值过滤器
                如 {"contractName": "9552422d-b95f-4afc-bb83-d2fee4d1935e"}
                用于限制Holder选择特定值的VC

        返回:
            proof_request字典
        """
        if vc_type not in self.vc_config:
            raise ProofRequestBuilderError(f"不支持的VC类型: {vc_type}")

        vc_config = self.vc_config[vc_type]

        # 验证属性
        self._validate_attributes(requested_attributes, vc_type)

        # 使用默认restrictions
        if restrictions is None:
            restrictions = self._get_default_restrictions(vc_type)

        # 构造requested_attributes
        requested_attrs_obj = {}
        for i, attr_name in enumerate(requested_attributes):
            attr_key = f"attr_{i}_{attr_name}"

            # 为每个属性创建restrictions副本
            attr_restrictions = [r.copy() for r in restrictions] if restrictions else []

            # 如果有属性值过滤器，添加到restrictions中
            if attribute_filters and attr_name in attribute_filters:
                for attr_restriction in attr_restrictions:
                    # ACA-Py属性值过滤格式: attr::ATTRIBUTE_NAME::value
                    filter_key = f"attr::{attr_name}::value"
                    attr_restriction[filter_key] = attribute_filters[attr_name]
                    logger.debug(f"添加属性值过滤: {filter_key} = {attribute_filters[attr_name]}")

            requested_attrs_obj[attr_key] = {
                "name": attr_name,
                "restrictions": attr_restrictions if attr_restrictions else restrictions
            }

        # 构造requested_predicates（如果提供）
        requested_preds_obj = {}
        if requested_predicates:
            for pred_key, pred_data in requested_predicates.items():
                pred_name = pred_data.get("name")
                p_type = pred_data.get("p_type", ">=")
                p_value = pred_data.get("p_value")

                if not pred_name or p_value is None:
                    logger.warning(f"谓词 {pred_key} 缺少必需字段，跳过")
                    continue

                requested_preds_obj[pred_key] = {
                    "name": pred_name,
                    "p_type": p_type,
                    "p_value": p_value,
                    "restrictions": restrictions
                }

        # 构造proof_request
        proof_request = {
            "name": name or f"{vc_type}验证请求",
            "version": version,
            "requested_attributes": requested_attrs_obj,
            "requested_predicates": requested_preds_obj if requested_preds_obj else {}
        }

        # 添加non_revoked
        if non_revoked:
            proof_request["non_revoked"] = non_revoked

        logger.info(f"构造{vc_type}证明请求: {len(requested_attributes)}个属性, {len(requested_preds_obj)}个谓词")

        return proof_request

    def _get_default_restrictions(self, vc_type: str) -> List[Dict]:
        """
        获取VC类型的默认restrictions

        参数:
            vc_type: VC类型名称

        返回:
            restrictions列表
        """
        if vc_type not in self.vc_config:
            raise ProofRequestBuilderError(f"不支持的VC类型: {vc_type}")

        vc_config = self.vc_config[vc_type]

        restriction = {}

        # 添加schema_id
        if "schema_id" in vc_config:
            restriction["schema_id"] = vc_config["schema_id"]

        # 添加cred_def_id
        if "cred_def_id" in vc_config:
            restriction["cred_def_id"] = vc_config["cred_def_id"]

        # 添加issuer_did（从schema_id中提取）
        if "schema_id" in vc_config:
            schema_id = vc_config["schema_id"]
            issuer_did = schema_id.split(":")[0] if ":" in schema_id else None
            if issuer_did:
                restriction["issuer_did"] = issuer_did

        return [restriction]

    def _validate_attributes(self, attributes: List[str], vc_type: str) -> bool:
        """
        验证属性是否在VC类型中存在

        参数:
            attributes: 属性列表
            vc_type: VC类型名称

        返回:
            是否有效

        异常:
            ProofRequestBuilderError: 属性无效
        """
        if vc_type not in self.vc_config:
            raise ProofRequestBuilderError(f"不支持的VC类型: {vc_type}")

        vc_config = self.vc_config[vc_type]
        valid_attrs = vc_config.get("attributes", [])

        invalid_attrs = [attr for attr in attributes if attr not in valid_attrs]

        if invalid_attrs:
            raise ProofRequestBuilderError(
                f"属性 {invalid_attrs} 不在VC类型 {vc_type} 中. "
                f"有效属性: {valid_attrs}"
            )

        return True

    def build_non_revoked(
        self,
        from_timestamp: Optional[int] = None,
        to_timestamp: Optional[int] = None
    ) -> Dict:
        """
        构造non_revoked时间范围

        参数:
            from_timestamp: 起始时间戳（默认0）
            to_timestamp: 结束时间戳（默认当前时间）

        返回:
            non_revoked字典
        """
        if from_timestamp is None:
            from_timestamp = 0

        if to_timestamp is None:
            to_timestamp = int(datetime.now().timestamp())

        return {
            "from": from_timestamp,
            "to": to_timestamp
        }

    def get_supported_vc_types(self) -> List[str]:
        """
        获取支持的VC类型列表

        返回:
            VC类型名称列表
        """
        return list(self.vc_config.keys())

    def get_vc_attributes(self, vc_type: str) -> List[str]:
        """
        获取VC类型的可用属性

        参数:
            vc_type: VC类型名称

        返回:
            属性列表

        异常:
            ProofRequestBuilderError: VC类型不支持
        """
        if vc_type not in self.vc_config:
            raise ProofRequestBuilderError(f"不支持的VC类型: {vc_type}")

        return self.vc_config[vc_type].get("attributes", [])

    def get_vc_info(self, vc_type: str) -> Dict:
        """
        获取VC类型的完整信息

        参数:
            vc_type: VC类型名称

        返回:
            VC配置信息
        """
        if vc_type not in self.vc_config:
            raise ProofRequestBuilderError(f"不支持的VC类型: {vc_type}")

        return self.vc_config[vc_type]
