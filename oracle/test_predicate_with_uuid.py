#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三步验证测试脚本
1. 建立测试实例 - 从区块链获取VC元数据，确认Holder凭证
2. UUID匹配验证 - 仅使用UUID限制条件过滤
3. 全部属性值验证 - UUID + attribute_restrictions

测试目标：验证修改后的predicate_proof_builder能正确将所有限制条件
添加到每个披露属性，使Holder自动响应能选择正确凭证
"""

import sys
import json
import argparse
import logging
import requests
from pathlib import Path
from typing import Dict, Optional, Tuple, List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_CONFIG_PATH = "vp_predicate_config.json"
DEFAULT_ORACLE_URL = "http://localhost:7003"
DEFAULT_UUID_PATH = "logs/uuid.json"


def load_config(config_path: str) -> Dict:
    """加载配置文件"""
    with open(config_path, 'r') as f:
        return json.load(f)


def load_uuid_data(uuid_path: str) -> Dict:
    """加载UUID数据文件"""
    try:
        with open(uuid_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"UUID数据文件不存在: {uuid_path}")
        return {}


def find_matching_vc_hash(uuid_data: Dict, vc_type: str, credential_uuid: str) -> Optional[str]:
    """
    从uuid.json中查找与凭证UUID匹配的vc_hash

    参数:
        uuid_data: uuid.json中的数据
        vc_type: VC类型
        credential_uuid: 凭证中的contractName值

    返回:
        匹配的vc_hash，如果没找到返回None
    """
    # 遍历uuid_data，查找匹配的记录
    for record_uuid, record in uuid_data.items():
        if record.get('vc_type') == vc_type:
            # 检查记录的UUID是否与凭证UUID匹配
            if record_uuid == credential_uuid:
                return record.get('vc_hash')

    # 如果没有直接匹配，尝试使用最新的一条记录
    matching_records = []
    for record_uuid, record in uuid_data.items():
        if record.get('vc_type') == vc_type:
            matching_records.append((record.get('timestamp', ''), record.get('vc_hash'), record_uuid))

    if matching_records:
        # 按时间戳排序，取最新的
        matching_records.sort(reverse=True)
        _, vc_hash, record_uuid = matching_records[0]
        logger.warning(f"未找到精确匹配，使用最新的记录: {record_uuid}")
        return vc_hash

    return None


def setup_test_instance(vc_type: str, oracle_url: str, config: Dict, uuid_data: Dict) -> Tuple[str, str, Dict]:
    """
    步骤1：建立测试实例

    返回:
        (uuid, vc_hash, credential_attributes)
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"步骤1：建立测试实例 - {vc_type}")
    logger.info(f"{'='*60}")

    # 1.1 获取Holder的所有凭证
    holder_url = config['acapy']['holder']['admin_url']
    logger.info(f"从Holder获取凭证列表: {holder_url}")

    response = requests.get(f"{holder_url}/credentials")
    if response.status_code != 200:
        raise Exception(f"获取Holder凭证失败: {response.text}")

    credentials = response.json()['results']
    logger.info(f"Holder共有 {len(credentials)} 个凭证")

    # 1.2 找到匹配指定VC类型的凭证
    vc_config = config['vc_types'].get(vc_type)
    if not vc_config:
        raise Exception(f"未找到VC类型配置: {vc_type}")

    schema_id = vc_config['schema_id']
    cred_def_id = vc_config['cred_def_id']

    matching_creds = []
    for cred in credentials:
        if cred.get('schema_id') == schema_id and cred.get('cred_def_id') == cred_def_id:
            matching_creds.append(cred)

    if not matching_creds:
        raise Exception(f"Holder没有 {vc_type} 类型的凭证")

    logger.info(f"找到 {len(matching_creds)} 个 {vc_type} 凭证")

    # 1.3 尝试从uuid.json中找到匹配的vc_hash
    vc_hash = None
    matched_cred = None

    for cred in matching_creds:
        credential_uuid = cred.get('attrs', {}).get('contractName', '')
        if credential_uuid:
            found_hash = find_matching_vc_hash(uuid_data, vc_type, credential_uuid)
            if found_hash:
                vc_hash = found_hash
                matched_cred = cred
                logger.info(f"找到匹配的vc_hash: {vc_hash}")
                break

    # 如果没有找到匹配的，使用第一个凭证并尝试从uuid.json获取最新的vc_hash
    if not vc_hash:
        matched_cred = matching_creds[0]
        credential_uuid = matched_cred.get('attrs', {}).get('contractName', '')

        # 尝试从uuid.json获取该类型的最新vc_hash
        if uuid_data:
            matching_records = []
            for record_uuid, record in uuid_data.items():
                if record.get('vc_type') == vc_type:
                    matching_records.append((record.get('timestamp', ''), record.get('vc_hash')))

            if matching_records:
                matching_records.sort(reverse=True)
                _, vc_hash = matching_records[0]
                logger.warning(f"使用最新的vc_hash: {vc_hash}")

    if not vc_hash:
        raise Exception(f"无法获取有效的vc_hash，请检查uuid.json文件")

    # 提取凭证信息
    credential_attributes = matched_cred.get('attrs', {})
    cred_referent = matched_cred.get('referent')
    uuid = credential_attributes.get('contractName', '')

    logger.info(f"选择测试凭证:")
    logger.info(f"  - Referent: {cred_referent}")
    logger.info(f"  - UUID (contractName): {uuid}")
    logger.info(f"  - vc_hash: {vc_hash}")
    logger.info(f"  - 属性数量: {len(credential_attributes)}")

    # 显示凭证属性
    for attr_name, attr_value in credential_attributes.items():
        logger.info(f"    {attr_name}: {attr_value}")

    return uuid, vc_hash, credential_attributes


def verify_with_uuid_only(vc_type: str, vc_hash: str, uuid: str, oracle_url: str) -> Dict:
    """
    步骤2：UUID匹配验证

    仅使用UUID限制条件，验证Holder能选择正确凭证
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"步骤2：UUID匹配验证 - 仅UUID限制条件")
    logger.info(f"{'='*60}")

    # 构造验证请求（仅UUID过滤，传入空字典跳过attribute_restrictions）
    verify_request = {
        "vc_type": vc_type,
        "vc_hash": vc_hash,
        "attribute_restrictions": {}  # 空字典表示跳过attribute_restrictions
    }

    logger.info(f"发送验证请求到Oracle: {oracle_url}/api/verify")

    response = requests.post(
        f"{oracle_url}/api/verify",
        json=verify_request,
        timeout=120
    )

    if response.status_code != 200:
        logger.error(f"验证请求失败: {response.text}")
        raise Exception(f"验证请求失败: {response.status_code}")

    result = response.json()
    logger.info(f"验证结果: verified={result.get('verified')}")

    if result.get('verified'):
        logger.info("UUID匹配验证成功!")
        revealed = result.get('revealed_attributes', {})
        for attr_name, attr_value in revealed.items():
            logger.info(f"  披露属性: {attr_name} = {attr_value}")
    else:
        logger.error("UUID匹配验证失败!")
        logger.error(f"错误: {result.get('error', '未知错误')}")

    return result


def verify_with_all_restrictions(vc_type: str, vc_hash: str, uuid: str, oracle_url: str) -> Dict:
    """
    步骤3：全部属性值验证

    使用UUID + attribute_restrictions，验证完整限制条件过滤
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"步骤3：全部属性值验证 - UUID + attribute_restrictions")
    logger.info(f"{'='*60}")

    # 构造验证请求（使用默认attribute_restrictions）
    verify_request = {
        "vc_type": vc_type,
        "vc_hash": vc_hash
        # 不传attribute_restrictions，使用默认策略
    }

    logger.info(f"发送验证请求到Oracle: {oracle_url}/api/verify")

    response = requests.post(
        f"{oracle_url}/api/verify",
        json=verify_request,
        timeout=120
    )

    if response.status_code != 200:
        logger.error(f"验证请求失败: {response.text}")
        raise Exception(f"验证请求失败: {response.status_code}")

    result = response.json()
    logger.info(f"验证结果: verified={result.get('verified')}")

    if result.get('verified'):
        logger.info("全部属性值验证成功!")

        # 显示披露属性
        revealed = result.get('revealed_attributes', {})
        logger.info("披露属性:")
        for attr_name, attr_value in revealed.items():
            logger.info(f"  {attr_name}: {attr_value}")

        # 显示谓词验证结果
        predicate_results = result.get('predicate_results', {})
        if predicate_results:
            logger.info("谓词验证结果:")
            for pred_key, pred_result in predicate_results.items():
                logger.info(f"  {pred_key}: satisfied={pred_result.get('satisfied')}")

        # 显示限制条件验证结果
        restriction_results = result.get('restriction_results', {})
        if restriction_results:
            logger.info("限制条件验证结果:")
            for restr_key, restr_result in restriction_results.items():
                logger.info(f"  {restr_key}: satisfied={restr_result.get('satisfied')}")
    else:
        logger.error("全部属性值验证失败!")
        logger.error(f"错误: {result.get('error', '未知错误')}")

    return result


def verify_restriction_applied_to_all_attributes(
    vc_type: str,
    vc_hash: str,
    uuid: str,
    oracle_url: str,
    config: Dict
) -> bool:
    """
    验证限制条件确实被应用到所有披露属性

    通过检查proof_request结构来验证
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"额外验证：检查限制条件是否应用到所有披露属性")
    logger.info(f"{'='*60}")

    # 获取VC类型的披露属性列表
    policy = config['predicate_policies'].get(vc_type, {})
    attributes_to_reveal = policy.get('attributes_to_reveal', [])
    attribute_restrictions = policy.get('attribute_restrictions', {})

    if not attributes_to_reveal:
        logger.warning("没有配置披露属性，跳过检查")
        return True

    if not attribute_restrictions:
        logger.warning("没有配置attribute_restrictions，跳过检查")
        return True

    logger.info(f"披露属性: {attributes_to_reveal}")
    logger.info(f"限制条件: {list(attribute_restrictions.keys())}")

    # 构造proof_request来检查结构
    from predicate_proof_builder import PredicateProofBuilder

    builder = PredicateProofBuilder(config['vc_types'], config['predicate_policies'])

    # 使用UUID过滤和attribute_restrictions
    proof_request = builder.build_predicate_proof_request(
        vc_type=vc_type,
        attributes_to_reveal=attributes_to_reveal,
        predicates=policy.get('predicates', {}),
        attribute_filters={"contractName": uuid},
        attribute_restrictions=attribute_restrictions
    )

    # 检查每个披露属性的restrictions
    requested_attrs = proof_request.get('requested_attributes', {})

    all_have_restrictions = True
    for attr_key, attr_def in requested_attrs.items():
        attr_name = attr_def.get('name')
        restrictions = attr_def.get('restrictions', [])

        logger.info(f"\n检查属性 {attr_name} ({attr_key}):")
        logger.info(f"  Restrictions数量: {len(restrictions)}")

        # 检查是否有UUID过滤
        has_uuid_filter = False
        has_attr_restriction = False

        for restr in restrictions:
            if 'attr::contractName::value' in restr:
                has_uuid_filter = True
                logger.info(f"  包含UUID过滤: contractName={restr['attr::contractName::value']}")

            for restr_key in attribute_restrictions.keys():
                restr_attr = attribute_restrictions[restr_key]['attribute']
                filter_key = f"attr::{restr_attr}::value"
                if filter_key in restr:
                    has_attr_restriction = True
                    logger.info(f"  包含属性限制: {restr_attr}={restr[filter_key]}")

        if not has_uuid_filter:
            logger.warning(f"  缺少UUID过滤!")
            all_have_restrictions = False

        if not has_attr_restriction:
            logger.warning(f"  缺少attribute_restrictions!")
            all_have_restrictions = False

    if all_have_restrictions:
        logger.info("\n验证通过：所有限制条件都已应用到每个披露属性!")
    else:
        logger.error("\n验证失败：部分属性缺少限制条件!")

    return all_have_restrictions


def execute_verification(
    vc_type: str,
    vc_hash: str,
    uuid: str,
    oracle_url: str,
    config: Dict,
    custom_predicates: Optional[Dict] = None,
    custom_attribute_filters: Optional[Dict] = None,
    skip_uuid_only: bool = False,
    skip_full_verification: bool = False
) -> Dict:
    """
    执行完整验证流程（供前端调用）

    参数:
        vc_type: VC 类型
        vc_hash: VC 哈希
        uuid: 凭证 UUID (contractName)
        oracle_url: Oracle 服务地址
        config: 配置字典
        custom_predicates: 自定义谓词条件（可选）
        custom_attribute_filters: 自定义属性过滤器（可选）
        skip_uuid_only: 是否跳过步骤 2
        skip_full_verification: 是否跳过步骤 3

    返回:
        {
            'success': True/False,
            'step2_result': {...} 或 None,
            'step3_result': {...} 或 None,
            'error': None 或错误信息
        }
    """
    result = {
        'success': False,
        'step2_result': None,
        'step3_result': None,
        'error': None
    }

    try:
        # 步骤 2：UUID 匹配验证
        if not skip_uuid_only:
            logger.info(f"执行步骤 2：UUID 匹配验证")
            verify_request = {
                "vc_type": vc_type,
                "vc_hash": vc_hash,
                "attribute_restrictions": {}  # 空字典表示跳过 attribute_restrictions
            }

            response = requests.post(
                f"{oracle_url}/api/verify",
                json=verify_request,
                timeout=120
            )

            if response.status_code != 200:
                result['error'] = f"步骤 2 验证请求失败：{response.text}"
                return result

            result['step2_result'] = response.json()

            if not result['step2_result'].get('verified'):
                result['error'] = f"步骤 2 验证失败：{result['step2_result'].get('error', '未知错误')}"
                return result

        # 步骤 3：全部属性值验证（支持自定义谓词和属性过滤器）
        if not skip_full_verification:
            logger.info(f"执行步骤 3：全部属性值验证")
            verify_request = {
                "vc_type": vc_type,
                "vc_hash": vc_hash
            }

            # 添加自定义谓词（如果提供）
            if custom_predicates:
                verify_request['predicates'] = custom_predicates

            # 添加自定义属性过滤器（如果提供）
            if custom_attribute_filters:
                verify_request['attribute_filters'] = custom_attribute_filters

            response = requests.post(
                f"{oracle_url}/api/verify",
                json=verify_request,
                timeout=120
            )

            if response.status_code != 200:
                result['error'] = f"步骤 3 验证请求失败：{response.text}"
                return result

            result['step3_result'] = response.json()

            if not result['step3_result'].get('verified'):
                result['error'] = f"步骤 3 验证失败：{result['step3_result'].get('error', '未知错误')}"
                return result

        result['success'] = True
        return result

    except Exception as e:
        logger.error(f"验证执行失败：{e}", exc_info=True)
        result['error'] = str(e)
        return result


def get_latest_uuids(uuid_data: Dict, vc_type: Optional[str] = None) -> Dict:
    """
    从 uuid.json 数据中获取各 VC 类型的最新记录

    参数:
        uuid_data: uuid.json 中的数据
        vc_type: 可选的 VC 类型过滤，如果为 None 则返回所有类型

    返回:
        {
            "InspectionReport": [
                {"uuid": "...", "vc_hash": "...", "timestamp": "...", "original_contract_name": "..."}
            ],
            ...
        }
    """
    result = {}

    # 按 vc_type 分组
    grouped = {}
    for record_uuid, record in uuid_data.items():
        vc_type_record = record.get('vc_type')
        if vc_type_record not in grouped:
            grouped[vc_type_record] = []
        grouped[vc_type_record].append({
            'uuid': record_uuid,
            'vc_hash': record.get('vc_hash'),
            'timestamp': record.get('timestamp'),
            'original_contract_name': record.get('original_contract_name'),
            'tx_hash': record.get('tx_hash')
        })

    # 对每组按时间戳排序，取最新的
    for vc_type_group, records in grouped.items():
        if vc_type and vc_type != vc_type_group:
            continue

        records_sorted = sorted(records, key=lambda x: x.get('timestamp', ''), reverse=True)
        result[vc_type_group] = records_sorted

    return result


def get_holder_credentials_for_vc_type(vc_type: str, config: Dict) -> List[Dict]:
    """
    从 Holder 获取指定 VC 类型的凭证列表

    参数:
        vc_type: VC 类型
        config: 配置字典

    返回:
        凭证列表，每个凭证包含 referent, attrs 等信息
    """
    holder_url = config['acapy']['holder']['admin_url']
    vc_config = config['vc_types'].get(vc_type)

    if not vc_config:
        return []

    schema_id = vc_config['schema_id']
    cred_def_id = vc_config['cred_def_id']

    try:
        response = requests.get(f"{holder_url}/credentials", timeout=10)
        if response.status_code != 200:
            logger.error(f"获取 Holder 凭证失败：{response.text}")
            return []

        credentials = response.json().get('results', [])
        matching_creds = [
            cred for cred in credentials
            if cred.get('schema_id') == schema_id and cred.get('cred_def_id') == cred_def_id
        ]

        return matching_creds
    except Exception as e:
        logger.error(f"获取 Holder 凭证异常：{e}")
        return []


def main():
    parser = argparse.ArgumentParser(description='三步验证测试脚本')
    parser.add_argument('--vc-type', required=True, help='VC类型 (如 InspectionReport)')
    parser.add_argument('--config', default=DEFAULT_CONFIG_PATH, help='配置文件路径')
    parser.add_argument('--uuid-path', default=DEFAULT_UUID_PATH, help='UUID数据文件路径')
    parser.add_argument('--oracle-url', default=DEFAULT_ORACLE_URL, help='Oracle服务URL')
    parser.add_argument('--skip-step2', action='store_true', help='跳过步骤2（UUID验证）')
    parser.add_argument('--skip-step3', action='store_true', help='跳过步骤3（完整验证）')
    parser.add_argument('--check-structure', action='store_true', help='检查proof_request结构')

    args = parser.parse_args()

    try:
        # 加载配置
        config = load_config(args.config)

        # 加载UUID数据
        uuid_data = load_uuid_data(args.uuid_path)

        # 步骤1：建立测试实例
        uuid, vc_hash, credential_attributes = setup_test_instance(
            args.vc_type, args.oracle_url, config, uuid_data
        )

        # 额外验证：检查proof_request结构
        if args.check_structure:
            structure_ok = verify_restriction_applied_to_all_attributes(
                args.vc_type, vc_hash, uuid, args.oracle_url, config
            )
            if not structure_ok:
                logger.error("proof_request结构验证失败!")
                return 1

        # 步骤2：UUID匹配验证
        if not args.skip_step2:
            result2 = verify_with_uuid_only(
                args.vc_type, vc_hash, uuid, args.oracle_url
            )
            if not result2.get('verified'):
                logger.error("步骤2验证失败，终止测试")
                return 1

        # 步骤3：全部属性值验证
        if not args.skip_step3:
            result3 = verify_with_all_restrictions(
                args.vc_type, vc_hash, uuid, args.oracle_url
            )
            if not result3.get('verified'):
                logger.error("步骤3验证失败")
                return 1

        logger.info(f"\n{'='*60}")
        logger.info("所有测试通过!")
        logger.info(f"{'='*60}")
        return 0

    except Exception as e:
        logger.error(f"测试执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
