#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VP谓词验证Oracle服务 - Flask REST API
端口: 7003
提供REST API接口进行谓词验证

与现有 flask_app.py（端口7002）的区别:
- 支持谓词验证API
- 返回谓词验证结果
- 提供谓词策略查询接口
"""

import asyncio
import concurrent.futures
import logging
import sys
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS

from vp_predicate_oracle_service import VPPredicateOracleService


# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 全局服务实例
oracle_service = None

# 全局事件循环（用于异步操作）
_event_loop = None
_loop_thread = None
_loop_started = threading.Event()


def _run_event_loop():
    """在后台线程中运行事件循环"""
    global _event_loop
    _event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_event_loop)
    _loop_started.set()
    _event_loop.run_forever()


def get_event_loop():
    """获取全局事件循环（在后台线程中运行）"""
    global _loop_thread
    if _loop_thread is None or not _loop_thread.is_alive():
        _loop_started.clear()
        _loop_thread = threading.Thread(target=_run_event_loop, daemon=True)
        _loop_thread.start()
        _loop_started.wait()
    return _event_loop


def run_async(coro):
    """在后台事件循环中运行协程，等待结果"""
    loop = get_event_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=180)  # 3分钟超时


def init_service(config_path: str = "vp_predicate_config.json"):
    """初始化Oracle服务"""
    global oracle_service
    try:
        oracle_service = VPPredicateOracleService(config_path)
        logger.info("VP谓词验证Oracle服务初始化成功")
    except Exception as e:
        logger.error(f"VP谓词验证Oracle服务初始化失败: {e}", exc_info=True)
        sys.exit(1)


@app.route('/api/health', methods=['GET'])
def health():
    """
    GET /api/health - 健康检查

    返回:
    {
        "status": "healthy",
        "service": "vp_predicate_oracle",
        "port": 7003,
        "timestamp": "...",
        "blockchain_connected": true | false,
        "vc_types_count": 4,
        "predicate_policies_count": 4
    }
    """
    return jsonify({
        "status": "healthy",
        "service": "vp_predicate_oracle",
        "version": "1.0.0",
        "port": 7003,
        "timestamp": datetime.now().isoformat(),
        "blockchain_connected": oracle_service.blockchain_client.is_connected() if oracle_service else False,
        "vc_types_count": len(oracle_service.get_supported_vc_types()) if oracle_service else 0,
        "predicate_policies_count": len(oracle_service.get_all_predicate_policies()) if oracle_service else 0
    })


@app.route('/api/vc-types', methods=['GET'])
def get_vc_types():
    """
    GET /api/vc-types - 获取支持的VC类型

    返回:
    ["InspectionReport", "InsuranceContract", ...]
    """
    if not oracle_service:
        return jsonify({"error": "服务未初始化"}), 500

    vc_types = oracle_service.get_supported_vc_types()
    return jsonify(vc_types)


@app.route('/api/vc-types/<vc_type>/attributes', methods=['GET'])
def get_vc_attributes(vc_type: str):
    """
    GET /api/vc-types/<vc_type>/attributes - 获取VC类型的可用属性

    返回:
    ["exporter", "contractName", "inspectionPassed", ...]
    """
    if not oracle_service:
        return jsonify({"error": "服务未初始化"}), 500

    attributes = oracle_service.get_vc_attributes(vc_type)
    if attributes is None:
        return jsonify({
            "error": f"不支持的VC类型: {vc_type}",
            "supported_vc_types": oracle_service.get_supported_vc_types()
        }), 400

    return jsonify(attributes)


@app.route('/api/vc-types/<vc_type>/info', methods=['GET'])
def get_vc_info(vc_type: str):
    """
    GET /api/vc-types/<vc_type>/info - 获取VC类型的完整配置信息

    返回:
    {
        "schema_id": "...",
        "cred_def_id": "...",
        "contract_address": "...",
        "attributes": [...]
    }
    """
    if not oracle_service:
        return jsonify({"error": "服务未初始化"}), 500

    info = oracle_service.get_vc_config(vc_type)
    if info is None:
        return jsonify({
            "error": f"不支持的VC类型: {vc_type}",
            "supported_vc_types": oracle_service.get_supported_vc_types()
        }), 400

    # 返回非敏感配置
    return jsonify({
        "schema_id": info.get("schema_id"),
        "cred_def_id": info.get("cred_def_id"),
        "contract_address": info.get("contract_address"),
        "attributes": info.get("attributes", [])
    })


@app.route('/api/vc-types/<vc_type>/predicate-policy', methods=['GET'])
def get_predicate_policy(vc_type: str):
    """
    GET /api/vc-types/<vc_type>/predicate-policy - 获取VC类型的谓词策略

    返回:
    {
        "description": "检验报告 - 验证货物已通过检验",
        "attributes_to_reveal": ["exporter", "contractName", "productName"],
        "predicates": {
            "inspection_passed": {
                "attribute": "inspectionPassed",
                "operator": "==",
                "value": 1,
                "description": "检验必须通过"
            }
        }
    }
    """
    if not oracle_service:
        return jsonify({"error": "服务未初始化"}), 500

    policy = oracle_service.get_predicate_policy(vc_type)
    if policy is None:
        return jsonify({
            "error": f"VC类型 {vc_type} 没有配置谓词策略",
            "supported_vc_types": oracle_service.get_supported_vc_types()
        }), 404

    return jsonify(policy)


@app.route('/api/vc-types/<vc_type>/predicate-policy/describe', methods=['GET'])
def describe_predicate_policy(vc_type: str):
    """
    GET /api/vc-types/<vc_type>/predicate-policy/describe - 获取谓词策略的人类可读描述

    返回:
    {
        "vc_type": "InspectionReport",
        "description": "VC类型: InspectionReport\n披露属性: exporter, contractName, productName\n谓词验证:\n  - inspection_passed: inspectionPassed == 1 (检验必须通过)\n  - min_quantity: productQuantity > 0 (产品数量必须大于0)"
    }
    """
    if not oracle_service:
        return jsonify({"error": "服务未初始化"}), 500

    try:
        description = oracle_service.describe_predicate_policy(vc_type)
        return jsonify({
            "vc_type": vc_type,
            "description": description
        })
    except Exception as e:
        return jsonify({
            "error": f"获取谓词策略描述失败: {str(e)}"
        }), 400


@app.route('/api/predicate-policies', methods=['GET'])
def get_all_predicate_policies():
    """
    GET /api/predicate-policies - 获取所有VC类型的谓词策略

    返回:
    {
        "InspectionReport": {...},
        "InsuranceContract": {...},
        ...
    }
    """
    if not oracle_service:
        return jsonify({"error": "服务未初始化"}), 500

    policies = oracle_service.get_all_predicate_policies()
    return jsonify(policies)


@app.route('/api/verify', methods=['POST'])
def verify_with_predicates():
    """
    POST /api/verify - 使用谓词验证VC

    请求体:
    {
        "vc_type": "InspectionReport",
        "vc_hash": "0x1234...",
        "attributes_to_reveal": ["exporter", "contractName"],  // 可选，默认使用策略配置
        "predicates": {  // 可选，默认使用策略配置
            "custom_predicate": {
                "attribute": "productQuantity",
                "operator": ">=",
                "value": 100
            }
        },
        "attribute_restrictions": {  // 可选，默认使用策略配置，传{}跳过
            "inspection_must_pass": {
                "attribute": "inspectionPassed",
                "value": "true"
            }
        },
        "holder_did": "optional-holder-did"  // 可选
    }

    返回:
    {
        "verification_id": "...",
        "status": "verified" | "failed",
        "verified": true | false,
        "vc_type": "...",
        "vc_hash": "...",
        "uuid": "...",
        "revealed_attributes": {...},
        "predicate_results": {
            "inspection_passed": {
                "attribute": "inspectionPassed",
                "operator": "==",
                "expected_value": 1,
                "satisfied": true
            }
        },
        "verification_details": {
            "uuid_matched": true,
            "all_predicates_satisfied": true
        },
        "duration_seconds": 1.23,
        "timestamp": "..."
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "error": "缺少请求体"
            }), 400

        vc_type = data.get('vc_type')
        vc_hash = data.get('vc_hash')
        attributes_to_reveal = data.get('attributes_to_reveal')
        custom_predicates = data.get('predicates')
        custom_attribute_restrictions = data.get('attribute_restrictions')
        holder_did = data.get('holder_did')

        # 验证必需参数
        if not vc_type:
            return jsonify({
                "error": "缺少必需参数: vc_type"
            }), 400

        if not vc_hash:
            return jsonify({
                "error": "缺少必需参数: vc_hash"
            }), 400

        # 验证vc_hash格式
        if not (isinstance(vc_hash, str) and len(vc_hash) == 66 and vc_hash.startswith('0x')):
            return jsonify({
                "error": "vc_hash格式无效，应为66位十六进制字符串（含0x前缀）"
            }), 400

        # 验证vc_type是否支持
        supported_types = oracle_service.get_supported_vc_types()
        if vc_type not in supported_types:
            return jsonify({
                "error": f"不支持的VC类型: {vc_type}",
                "supported_vc_types": supported_types
            }), 400

        # 验证自定义属性（如果提供）
        if attributes_to_reveal:
            valid_attrs = oracle_service.get_vc_attributes(vc_type)
            if valid_attrs:
                invalid_attrs = [attr for attr in attributes_to_reveal if attr not in valid_attrs]
                if invalid_attrs:
                    return jsonify({
                        "error": f"属性 {invalid_attrs} 不在VC类型 {vc_type} 中",
                        "valid_attributes": valid_attrs
                    }), 400

        # 验证自定义谓词（如果提供）
        if custom_predicates:
            valid_attrs = oracle_service.get_vc_attributes(vc_type)
            if valid_attrs:
                for pred_key, pred_def in custom_predicates.items():
                    attr = pred_def.get('attribute')
                    if attr and attr not in valid_attrs:
                        return jsonify({
                            "error": f"谓词 {pred_key} 的属性 {attr} 不在VC类型 {vc_type} 中",
                            "valid_attributes": valid_attrs
                        }), 400

        # 验证自定义属性限制条件（如果提供）
        if custom_attribute_restrictions:
            valid_attrs = oracle_service.get_vc_attributes(vc_type)
            if valid_attrs:
                for restr_key, restr_def in custom_attribute_restrictions.items():
                    attr = restr_def.get('attribute')
                    if attr and attr not in valid_attrs:
                        return jsonify({
                            "error": f"限制条件 {restr_key} 的属性 {attr} 不在VC类型 {vc_type} 中",
                            "valid_attributes": valid_attrs
                        }), 400

        logger.info(f"收到谓词验证请求: vc_type={vc_type}, vc_hash={vc_hash[:16]}...")
        logger.info(f"  attributes_to_reveal={attributes_to_reveal or '使用默认策略'}")
        logger.info(f"  custom_predicates={list(custom_predicates.keys()) if custom_predicates else '使用默认策略'}")
        logger.info(f"  custom_attribute_restrictions={list(custom_attribute_restrictions.keys()) if custom_attribute_restrictions else '使用默认策略'}")

        # 使用后台事件循环执行异步验证
        try:
            result = run_async(
                oracle_service.verify_with_predicates(
                    vc_type=vc_type,
                    vc_hash=vc_hash,
                    attributes_to_reveal=attributes_to_reveal,
                    custom_predicates=custom_predicates,
                    custom_attribute_restrictions=custom_attribute_restrictions,
                    holder_did=holder_did
                )
            )
            return jsonify(result)
        except concurrent.futures.TimeoutError:
            logger.error(f"验证执行超时")
            return jsonify({
                "error": "验证执行超时"
            }), 504
        except Exception as e:
            logger.error(f"验证执行失败: {e}", exc_info=True)
            return jsonify({
                "error": f"验证执行失败: {str(e)}"
            }), 500

    except Exception as e:
        logger.error(f"验证请求处理失败: {e}", exc_info=True)
        return jsonify({
            "error": f"验证请求处理失败: {str(e)}"
        }), 500


@app.route('/api/verify-default', methods=['POST'])
def verify_with_default_predicates():
    """
    POST /api/verify-default - 使用默认谓词策略验证VC

    简化API，只需提供vc_type和vc_hash，使用配置文件中的默认谓词策略

    请求体:
    {
        "vc_type": "InspectionReport",
        "vc_hash": "0x1234...",
        "holder_did": "optional-holder-did"  // 可选
    }

    返回:
    同 /api/verify
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "error": "缺少请求体"
            }), 400

        vc_type = data.get('vc_type')
        vc_hash = data.get('vc_hash')
        holder_did = data.get('holder_did')

        # 验证必需参数
        if not vc_type:
            return jsonify({
                "error": "缺少必需参数: vc_type"
            }), 400

        if not vc_hash:
            return jsonify({
                "error": "缺少必需参数: vc_hash"
            }), 400

        # 验证vc_hash格式
        if not (isinstance(vc_hash, str) and len(vc_hash) == 66 and vc_hash.startswith('0x')):
            return jsonify({
                "error": "vc_hash格式无效，应为66位十六进制字符串（含0x前缀）"
            }), 400

        # 验证vc_type是否支持
        supported_types = oracle_service.get_supported_vc_types()
        if vc_type not in supported_types:
            return jsonify({
                "error": f"不支持的VC类型: {vc_type}",
                "supported_vc_types": supported_types
            }), 400

        logger.info(f"收到默认谓词验证请求: vc_type={vc_type}, vc_hash={vc_hash[:16]}...")

        # 使用后台事件循环执行异步验证（使用默认策略）
        try:
            result = run_async(
                oracle_service.verify_with_predicates(
                    vc_type=vc_type,
                    vc_hash=vc_hash,
                    attributes_to_reveal=None,  # 使用默认
                    custom_predicates=None,     # 使用默认
                    holder_did=holder_did
                )
            )
            return jsonify(result)
        except concurrent.futures.TimeoutError:
            logger.error(f"验证执行超时")
            return jsonify({
                "error": "验证执行超时"
            }), 504
        except Exception as e:
            logger.error(f"验证执行失败: {e}", exc_info=True)
            return jsonify({
                "error": f"验证执行失败: {str(e)}"
            }), 500

    except Exception as e:
        logger.error(f"验证请求处理失败: {e}", exc_info=True)
        return jsonify({
            "error": f"验证请求处理失败: {str(e)}"
        }), 500


@app.errorhandler(404)
def not_found(error):
    """处理404错误"""
    return jsonify({
        "error": "API端点不存在",
        "service": "vp_predicate_oracle",
        "port": 7003,
        "available_endpoints": [
            "GET  /api/health",
            "GET  /api/vc-types",
            "GET  /api/vc-types/<vc_type>/attributes",
            "GET  /api/vc-types/<vc_type>/info",
            "GET  /api/vc-types/<vc_type>/predicate-policy",
            "GET  /api/vc-types/<vc_type>/predicate-policy/describe",
            "GET  /api/predicate-policies",
            "POST /api/verify",
            "POST /api/verify-default"
        ]
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """处理500错误"""
    logger.error(f"内部错误: {error}")
    return jsonify({
        "error": "服务器内部错误"
    }), 500


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="VP谓词验证Oracle服务（端口7003）")
    parser.add_argument(
        '--config',
        default='vp_predicate_config.json',
        help='配置文件路径 (默认: vp_predicate_config.json)'
    )
    parser.add_argument(
        '--host',
        default=None,
        help='服务器地址 (覆盖配置文件)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=None,
        help='服务器端口 (覆盖配置文件)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='启用调试模式'
    )

    args = parser.parse_args()

    # 初始化服务
    init_service(args.config)

    # 获取服务器配置
    host = args.host or oracle_service.service_config.get('host', '0.0.0.0')
    port = args.port or oracle_service.service_config.get('port', 7003)
    debug = args.debug

    logger.info(f"启动Flask服务器: http://{host}:{port}")
    logger.info(f"API端点:")
    logger.info(f"  GET  /api/health")
    logger.info(f"  GET  /api/vc-types")
    logger.info(f"  GET  /api/vc-types/<vc_type>/attributes")
    logger.info(f"  GET  /api/vc-types/<vc_type>/info")
    logger.info(f"  GET  /api/vc-types/<vc_type>/predicate-policy")
    logger.info(f"  GET  /api/vc-types/<vc_type>/predicate-policy/describe")
    logger.info(f"  GET  /api/predicate-policies")
    logger.info(f"  POST /api/verify")
    logger.info(f"  POST /api/verify-default")

    # 启动Flask服务器
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    main()
