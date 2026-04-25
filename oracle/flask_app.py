#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VP验证Oracle服务 - Flask REST API
提供REST API接口进行VC验证
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

from vp_oracle_service import VPOracleService


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


def init_service(config_path: str = "vp_oracle_config.json"):
    """初始化Oracle服务"""
    global oracle_service
    try:
        oracle_service = VPOracleService(config_path)
        logger.info("VP验证Oracle服务初始化成功")
    except Exception as e:
        logger.error(f"VP验证Oracle服务初始化失败: {e}", exc_info=True)
        sys.exit(1)


@app.route('/api/verify', methods=['POST'])
def verify_vc():
    """
    POST /api/verify - 执行VC验证

    请求体:
    {
        "vc_type": "InspectionReport",
        "vc_hash": "0x1234...",
        "requested_attributes": ["exporter", "inspectionPassed"],
        "holder_did": "可选的Holder DID"
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
        requested_attributes = data.get('requested_attributes', [])
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

        if not requested_attributes:
            return jsonify({
                "error": "缺少必需参数: requested_attributes"
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

        # 验证属性是否有效
        valid_attrs = oracle_service.get_vc_attributes(vc_type)
        if valid_attrs:
            invalid_attrs = [attr for attr in requested_attributes if attr not in valid_attrs]
            if invalid_attrs:
                return jsonify({
                    "error": f"属性 {invalid_attrs} 不在VC类型 {vc_type} 中",
                    "valid_attributes": valid_attrs
                }), 400

        logger.info(f"收到验证请求: vc_type={vc_type}, vc_hash={vc_hash[:16]}..., attributes={requested_attributes}, holder_did={holder_did}")

        # 使用后台事件循环执行异步验证（线程安全）
        try:
            result = run_async(
                oracle_service.verify_vc(vc_type, vc_hash, requested_attributes, holder_did)
            )
            return jsonify(result)
        except concurrent.futures.TimeoutError:
            logger.error(f"验证执行超时")
            return jsonify({
                "error": f"验证执行超时"
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


@app.route('/api/health', methods=['GET'])
def health():
    """
    GET /api/health - 健康检查

    返回:
    {
        "status": "healthy",
        "service": "vp_oracle",
        "timestamp": "...",
        "blockchain_connected": true | false
    }
    """
    return jsonify({
        "status": "healthy",
        "service": "vp_oracle",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "blockchain_connected": oracle_service.blockchain_client.is_connected() if oracle_service else False
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


@app.errorhandler(404)
def not_found(error):
    """处理404错误"""
    return jsonify({
        "error": "API端点不存在",
        "available_endpoints": [
            "POST /api/verify",
            "GET /api/health",
            "GET /api/vc-types",
            "GET /api/vc-types/<vc_type>/attributes",
            "GET /api/vc-types/<vc_type>/info"
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

    parser = argparse.ArgumentParser(description="VP验证Oracle服务")
    parser.add_argument(
        '--config',
        default='vp_oracle_config.json',
        help='配置文件路径 (默认: vp_oracle_config.json)'
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
    port = args.port or oracle_service.service_config.get('port', 7002)
    debug = args.debug

    logger.info(f"启动Flask服务器: http://{host}:{port}")
    logger.info(f"API端点:")
    logger.info(f"  POST /api/verify")
    logger.info(f"  GET  /api/health")
    logger.info(f"  GET  /api/vc-types")
    logger.info(f"  GET  /api/vc-types/<vc_type>/attributes")
    logger.info(f"  GET  /api/vc-types/<vc_type>/info")

    # 启动Flask服务器
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    main()
