#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIDComm 消息客户端
处理 DIDComm 消息的封装和传输

作者: Claude Code
日期: 2026-02-14
"""

import json
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class DIDCommClientError(Exception):
    """DIDComm 客户端错误"""
    pass


class DIDCommClient:
    """
    DIDComm 消息客户端

    负责：
    1. 创建 outbound-send 消息
    2. 解析 DID 文档中的服务端点
    3. 封装 DIDComm 消息
    """

    @staticmethod
    def create_outbound_message(
        payload: str,
        their_service: Dict[str, Any],
        their_did: Optional[str] = None
    ) -> Dict:
        """
        创建用于 outbound-send API 的消息

        Args:
            payload: DIDComm 消息内容（JSON 字符串）
            their_service: 目标服务信息
                {
                    "recipient_keys": ["key1", "key2"],
                    "routing_keys": ["routing_key1"],
                    "service_endpoint": "ws://localhost:8001"
                }
            their_did: 目标 DID（可选）

        Returns:
            符合 outbound-send API 格式的消息字典

        Example:
            >>> service = {
            ...     "recipient_keys": ["H3C2AVvLMv6gmMNam3uVAjZpfkcJCwDwnZn6z3wXmqPV"],
            ...     "routing_keys": [],
            ...     "service_endpoint": "ws://localhost:8001"
            ... }
            >>> msg = DIDCommClient.create_outbound_message('{"@type": "..."}', service)
        """
        if not payload:
            raise DIDCommClientError("payload 不能为空")

        if not their_service or not their_service.get("service_endpoint"):
            raise DIDCommClientError("their_service 必须包含 service_endpoint")

        message = {
            "payload": payload,
            "their_service": {
                "recipient_keys": their_service.get("recipient_keys", []),
                "routing_keys": their_service.get("routing_keys", []),
                "service_endpoint": their_service["service_endpoint"]
            }
        }

        if their_did:
            message["their_did"] = their_did

        logger.debug(f"创建 outbound 消息: endpoint={their_service['service_endpoint']}")
        return message

    @staticmethod
    def parse_service_endpoint(did_document: Dict) -> Optional[Dict]:
        """
        从 DID 文档解析 DIDComm 服务端点

        Args:
            did_document: DID 文档
                {
                    "service": [
                        {
                            "id": "did:example:123#didcomm",
                            "type": "did-communication",
                            "recipientKeys": ["key1"],
                            "routingKeys": ["routing_key1"],
                            "serviceEndpoint": "ws://localhost:8001"
                        }
                    ]
                }

        Returns:
            解析后的服务信息，如果未找到则返回 None

        Example:
            >>> did_doc = {
            ...     "service": [{
            ...         "type": "did-communication",
            ...         "serviceEndpoint": "ws://localhost:8001",
            ...         "recipientKeys": ["key1"]
            ...     }]
            ... }
            >>> service = DIDCommClient.parse_service_endpoint(did_doc)
        """
        if not did_document:
            return None

        services = did_document.get("service", [])
        if not services:
            logger.warning("DID 文档中没有 service 字段")
            return None

        # 查找 DIDComm 服务（支持多种类型名称）
        didcomm_types = ["did-communication", "DIDCommMessaging", "didcomm"]

        for service in services:
            service_type = service.get("type", "")

            if service_type in didcomm_types:
                endpoint = {
                    "id": service.get("id", ""),
                    "recipient_keys": service.get("recipientKeys", service.get("recipient_keys", [])),
                    "routing_keys": service.get("routingKeys", service.get("routing_keys", [])),
                    "service_endpoint": service.get("serviceEndpoint", service.get("service_endpoint", ""))
                }

                logger.debug(f"解析到 DIDComm 服务: {endpoint['service_endpoint']}")
                return endpoint

        logger.warning("DID 文档中未找到 DIDComm 服务")
        return None

    @staticmethod
    def create_didcomm_service(
        recipient_keys: list,
        service_endpoint: str,
        routing_keys: Optional[list] = None
    ) -> Dict:
        """
        创建 DIDComm 服务信息字典

        Args:
            recipient_keys: 接收者公钥列表
            service_endpoint: 服务端点 URL
            routing_keys: 路由密钥列表（可选）

        Returns:
            DIDComm 服务信息字典
        """
        return {
            "recipient_keys": recipient_keys or [],
            "routing_keys": routing_keys or [],
            "service_endpoint": service_endpoint
        }

    @staticmethod
    def validate_service_endpoint(service: Dict) -> bool:
        """
        验证 DIDComm 服务端点是否有效

        Args:
            service: 服务信息字典

        Returns:
            True 如果有效，False 否则
        """
        required_fields = ["recipient_keys", "service_endpoint"]

        for field in required_fields:
            if field not in service:
                logger.error(f"服务端点缺少必需字段: {field}")
                return False

        if not service["recipient_keys"]:
            logger.error("recipient_keys 不能为空")
            return False

        endpoint = service["service_endpoint"]
        if not endpoint or not isinstance(endpoint, str):
            logger.error("service_endpoint 必须是非空字符串")
            return False

        # 检查 URL 协议
        valid_protocols = ["ws://", "wss://", "http://", "https://"]
        if not any(endpoint.startswith(proto) for proto in valid_protocols):
            logger.error(f"service_endpoint 协议无效: {endpoint}")
            return False

        return True

    @staticmethod
    def encode_didcomm_message(message: Dict) -> str:
        """
        将 DIDComm 消息编码为 JSON 字符串

        Args:
            message: DIDComm 消息字典

        Returns:
            JSON 字符串
        """
        try:
            return json.dumps(message, ensure_ascii=False)
        except Exception as e:
            raise DIDCommClientError(f"编码 DIDComm 消息失败: {e}")

    @staticmethod
    def decode_didcomm_message(payload: str) -> Dict:
        """
        解码 DIDComm 消息 JSON 字符串

        Args:
            payload: JSON 字符串

        Returns:
            消息字典
        """
        try:
            return json.loads(payload)
        except json.JSONDecodeError as e:
            raise DIDCommClientError(f"解码 DIDComm 消息失败: {e}")


# ==================== 便捷函数 ====================

def create_holder_service_from_config(config: Dict) -> Dict:
    """
    从配置文件创建 Holder DIDComm 服务信息

    Args:
        config: ACA-Py holder 配置
            {
                "did": "...",
                "verkey": "...",
                "didcomm_url": "ws://..."
            }

    Returns:
        DIDComm 服务信息
    """
    return {
        "recipient_keys": [config.get("verkey", "")],
        "routing_keys": [],
        "service_endpoint": config.get("didcomm_url", "")
    }


def validate_didcomm_message(message: Dict) -> bool:
    """
    验证 DIDComm 消息的基本结构

    Args:
        message: 消息字典

    Returns:
        True 如果有效，False 否则
    """
    if not isinstance(message, dict):
        return False

    # 检查 @type 字段
    if "@type" not in message:
        logger.warning("DIDComm 消息缺少 @type 字段")
        return False

    # 检查 @id 字段
    if "@id" not in message:
        logger.warning("DIDComm 消息缺少 @id 字段")
        return False

    return True
