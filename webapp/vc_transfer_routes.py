#!/usr/bin/env python3
"""
VC 跨链传输 API 路由模块

提供 VC 跨链传输相关的 REST API 端点
"""

import logging
from flask import Blueprint, jsonify, request
from vc_transfer_api import vc_crosschain_service

logger = logging.getLogger(__name__)

# 创建 Blueprint
vc_transfer_bp = Blueprint('vc_transfer', __name__, url_prefix='/api/vc-transfer')


@vc_transfer_bp.route('/config', methods=['GET'])
def get_config():
    """
    获取配置信息（VC Managers、链信息）

    Returns:
        JSON 配置信息
    """
    try:
        config = vc_crosschain_service.config
        vc_issuance_config = vc_crosschain_service.vc_issuance_config

        # 提取 VC Managers 配置
        vc_managers = config.get('vc_managers', {}).get('chain_a', {})
        vc_managers_info = []
        for key, info in vc_managers.items():
            vc_managers_info.append({
                'key': key,
                'name': info.get('description', key),
                'address': info.get('address'),
                'did': info.get('did')
            })

        # 提取链配置
        chains = config.get('chains', {})
        chains_info = {}
        for chain_key, chain_info in chains.items():
            chains_info[chain_key] = {
                'name': chain_info.get('name'),
                'rpc_url': chain_info.get('rpc_url'),
                'chain_id': chain_info.get('chain_id'),
                'bridge_address': chain_info.get('bridge_address')
            }

        # 提取 VC 类型配置
        vc_types = vc_issuance_config.get('vc_types', {})
        vc_types_info = {}
        for vc_type, type_info in vc_types.items():
            vc_types_info[vc_type] = {
                'schema_name': type_info.get('schema_name'),
                'cred_def_id': type_info.get('cred_def_id'),
                'contract_address': type_info.get('contract_address'),
                'contract_name': type_info.get('contract_name'),
                'attributes': type_info.get('attributes', [])
            }

        return jsonify({
            'success': True,
            'vc_managers': vc_managers_info,
            'chains': chains_info,
            'vc_types': vc_types_info
        })

    except Exception as e:
        logger.error(f"获取配置失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vc_transfer_bp.route('/issued-vcs', methods=['GET'])
def get_issued_vcs():
    """
    从 uuid.json 读取已发行的 VC 列表

    Returns:
        JSON VC 列表
    """
    try:
        result = vc_crosschain_service.get_issued_vcs_from_log()
        return jsonify(result)

    except Exception as e:
        logger.error(f"读取已发行 VC 失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vc_transfer_bp.route('/vc-metadata/<vc_type>/<vc_hash>', methods=['GET'])
def get_vc_metadata(vc_type: str, vc_hash: str):
    """
    从链上获取 VC 元数据

    Args:
        vc_type: VC 类型
        vc_hash: VC Hash

    Returns:
        JSON VC 元数据
    """
    try:
        # 根据 vc_type 获取对应的 contract_name
        vc_issuance_config = vc_crosschain_service.vc_issuance_config
        vc_types = vc_issuance_config.get('vc_types', {})

        if vc_type not in vc_types:
            return jsonify({
                'success': False,
                'error': f'不支持的 VC 类型：{vc_type}'
            }), 400

        contract_name = vc_types[vc_type].get('contract_name', vc_type)

        result = vc_crosschain_service.get_vc_metadata_from_chain_a(contract_name, vc_hash)
        return jsonify(result)

    except Exception as e:
        logger.error(f"获取 VC 元数据失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vc_transfer_bp.route('/initiate', methods=['POST'])
def initiate_transfer():
    """
    发起跨链传输

    Request Body:
        {
            "vc_hash": "0x...",
            "vc_type": "InspectionReport",
            "target_chain": "chain_b"
        }

    Returns:
        JSON 传输结果
    """
    try:
        data = request.get_json()

        vc_hash = data.get('vc_hash')
        vc_type = data.get('vc_type')
        target_chain = data.get('target_chain', 'chain_b')

        if not vc_hash or not vc_type:
            return jsonify({
                'success': False,
                'error': '缺少必要参数：vc_hash, vc_type'
            }), 400

        # 发起跨链传输
        result = vc_crosschain_service.initiate_cross_chain_transfer(
            vc_hash=vc_hash,
            vc_type=vc_type,
            target_chain=target_chain
        )

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f"发起跨链传输失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vc_transfer_bp.route('/wait-for-completion/<vc_hash>', methods=['GET'])
def wait_for_completion(vc_hash: str):
    """
    等待跨链传输完成

    Query Parameters:
        timeout: 超时时间（秒），默认 120

    Args:
        vc_hash: VC Hash

    Returns:
        JSON 验证结果
    """
    try:
        timeout = request.args.get('timeout', 120, type=int)

        result = vc_crosschain_service.wait_for_cross_chain_transfer(
            vc_hash=vc_hash,
            timeout=timeout
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"等待跨链传输失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vc_transfer_bp.route('/bridge-record/<vc_hash>', methods=['GET'])
def get_bridge_record(vc_hash: str):
    """
    从 Chain B 读取接收记录

    Args:
        vc_hash: VC Hash

    Returns:
        JSON 接收记录
    """
    try:
        result = vc_crosschain_service.get_bridge_record_from_chain_b(vc_hash)
        return jsonify(result)

    except Exception as e:
        logger.error(f"读取桥接记录失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vc_transfer_bp.route('/all-vc-hashes/<vc_manager_type>', methods=['GET'])
def get_all_vc_hashes(vc_manager_type: str):
    """
    从 Chain A VC Manager 获取所有 VC 哈希列表

    Args:
        vc_manager_type: VC Manager 类型（如 InspectionReportVCManager）

    Returns:
        JSON VC 列表
    """
    try:
        result = vc_crosschain_service.get_all_vc_hashes(vc_manager_type)
        return jsonify(result)

    except Exception as e:
        logger.error(f"获取 VC 哈希列表失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
