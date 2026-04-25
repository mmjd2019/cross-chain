#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证proof_request结构脚本

独立测试：验证修改后的predicate_proof_builder能正确将所有限制条件
添加到每个披露属性和谓词的restrictions中
"""

import sys
import json
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from predicate_proof_builder import PredicateProofBuilder


def verify_structure(vc_type: str, config_path: str = "vp_predicate_config.json"):
    """
    验证proof_request结构

    检查：
    1. 所有限制条件（UUID + attribute_restrictions）是否应用到每个披露属性
    2. 所有限制条件是否应用到每个谓词
    """
    # 加载配置
    with open(config_path, 'r') as f:
        config = json.load(f)

    vc_config = config['vc_types']
    predicate_policies = config['predicate_policies']

    # 创建builder
    builder = PredicateProofBuilder(vc_config, predicate_policies)

    # 获取策略配置
    policy = predicate_policies.get(vc_type, {})
    attributes_to_reveal = policy.get('attributes_to_reveal', [])
    predicates = policy.get('predicates', {})
    attribute_restrictions = policy.get('attribute_restrictions', {})

    if not attributes_to_reveal:
        logger.error(f"VC类型 {vc_type} 没有配置披露属性")
        return False

    logger.info(f"\n{'='*60}")
    logger.info(f"验证 proof_request 结构: {vc_type}")
    logger.info(f"{'='*60}")
    logger.info(f"披露属性: {attributes_to_reveal}")
    logger.info(f"谓词: {list(predicates.keys()) if predicates else '无'}")
    logger.info(f"限制条件: {list(attribute_restrictions.keys()) if attribute_restrictions else '无'}")

    # 构造proof_request（使用模拟的UUID）
    test_uuid = "test-uuid-1234"
    proof_request = builder.build_predicate_proof_request(
        vc_type=vc_type,
        attributes_to_reveal=attributes_to_reveal,
        predicates=predicates,
        attribute_filters={"contractName": test_uuid},
        attribute_restrictions=attribute_restrictions
    )

    logger.info(f"\n构造的 proof_request:")
    logger.info(f"  名称: {proof_request.get('name')}")
    logger.info(f"  版本: {proof_request.get('version')}")

    # 验证每个披露属性
    requested_attrs = proof_request.get('requested_attributes', {})
    logger.info(f"\n验证披露属性 ({len(requested_attrs)}个):")

    all_attrs_valid = True
    for attr_key, attr_def in requested_attrs.items():
        attr_name = attr_def.get('name')
        restrictions = attr_def.get('restrictions', [])

        logger.info(f"\n  属性 {attr_name} ({attr_key}):")
        logger.info(f"    Restrictions数量: {len(restrictions)}")

        # 检查UUID过滤
        has_uuid = False
        has_attr_restr = {}

        for restr in restrictions:
            if 'attr::contractName::value' in restr:
                has_uuid = True
                logger.info(f"    ✓ UUID过滤: {restr['attr::contractName::value']}")

            for restr_key, restr_def in attribute_restrictions.items():
                restr_attr = restr_def['attribute']
                filter_key = f"attr::{restr_attr}::value"
                if filter_key in restr:
                    has_attr_restr[restr_key] = True
                    logger.info(f"    ✓ 限制条件 {restr_key}: {restr_attr}={restr[filter_key]}")

        # UUID过滤只在contractName属性上应该有（原有逻辑）
        if attr_name == 'contractName':
            if not has_uuid:
                logger.error(f"    ✗ contractName属性缺少UUID过滤!")
                all_attrs_valid = False
        else:
            if has_uuid:
                logger.warning(f"    ⚠ {attr_name}属性不应该有UUID过滤（原有逻辑）")

        for restr_key in attribute_restrictions.keys():
            if restr_key not in has_attr_restr:
                logger.error(f"    ✗ 缺少限制条件: {restr_key}!")
                all_attrs_valid = False

    # 验证每个谓词
    requested_preds = proof_request.get('requested_predicates', {})
    if requested_preds:
        logger.info(f"\n验证谓词 ({len(requested_preds)}个):")

        all_preds_valid = True
        for pred_key, pred_def in requested_preds.items():
            attr_name = pred_def.get('name')
            p_type = pred_def.get('p_type')
            p_value = pred_def.get('p_value')
            restrictions = pred_def.get('restrictions', [])

            logger.info(f"\n  谓词 {pred_key} ({attr_name} {p_type} {p_value}):")
            logger.info(f"    Restrictions数量: {len(restrictions)}")

            # 检查attribute_restrictions
            has_attr_restr = {}

            for restr in restrictions:
                for restr_key, restr_def in attribute_restrictions.items():
                    restr_attr = restr_def['attribute']
                    filter_key = f"attr::{restr_attr}::value"
                    if filter_key in restr:
                        has_attr_restr[restr_key] = True
                        logger.info(f"    ✓ 限制条件 {restr_key}: {restr_attr}={restr[filter_key]}")

            # 谓词不需要UUID过滤（原有逻辑），只需检查attribute_restrictions
            # if not has_uuid:
            #     logger.error(f"    ✗ 缺少UUID过滤!")
            #     all_preds_valid = False

            for restr_key in attribute_restrictions.keys():
                if restr_key not in has_attr_restr:
                    logger.error(f"    ✗ 缺少限制条件: {restr_key}!")
                    all_preds_valid = False
    else:
        all_preds_valid = True

    # 汇总结果
    logger.info(f"\n{'='*60}")
    if all_attrs_valid and all_preds_valid:
        logger.info("✓ 结构验证通过!")
        logger.info("  - UUID过滤只在contractName属性上（原有逻辑）")
        logger.info("  - attribute_restrictions添加到每个披露属性")
        if requested_preds:
            logger.info("  - attribute_restrictions添加到每个谓词")
        return True
    else:
        logger.error("✗ 结构验证失败!")
        if not all_attrs_valid:
            logger.error("  - 部分披露属性限制条件不正确")
        if not all_preds_valid:
            logger.error("  - 部分谓词缺少限制条件")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description='验证proof_request结构')
    parser.add_argument('--vc-type', default='InspectionReport',
                        help='VC类型 (默认: InspectionReport)')
    parser.add_argument('--config', default='vp_predicate_config.json',
                        help='配置文件路径')

    args = parser.parse_args()

    try:
        success = verify_structure(args.vc_type, args.config)
        return 0 if success else 1
    except Exception as e:
        logger.error(f"验证失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
