#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VP谓词验证测试脚本
测试谓词验证Oracle服务的功能

使用方法:
    python3 test_predicate_verification.py

注意:
    1. 需要先启动ACA-Py服务（Verifier: 8082, Holder: 8081）
    2. 需要启动谓词验证Oracle服务（端口7003）
    3. 需要Holder有对应类型的凭证
"""

import json
import logging
import sys
import time
from typing import Dict, Optional

import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 服务配置
ORACLE_URL = "http://localhost:7003"
DEFAULT_TIMEOUT = 180


class PredicateVerificationTester:
    """谓词验证测试器"""

    def __init__(self, oracle_url: str = ORACLE_URL):
        self.oracle_url = oracle_url
        self.test_results = []

    def check_health(self) -> bool:
        """检查服务健康状态"""
        try:
            response = requests.get(f"{self.oracle_url}/api/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"服务状态: {data.get('status')}")
                logger.info(f"区块链连接: {data.get('blockchain_connected')}")
                logger.info(f"VC类型数量: {data.get('vc_types_count')}")
                logger.info(f"谓词策略数量: {data.get('predicate_policies_count')}")
                return True
            return False
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return False

    def get_vc_types(self) -> list:
        """获取支持的VC类型"""
        try:
            response = requests.get(f"{self.oracle_url}/api/vc-types", timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"获取VC类型失败: {e}")
        return []

    def get_predicate_policy(self, vc_type: str) -> Optional[Dict]:
        """获取谓词策略"""
        try:
            response = requests.get(
                f"{self.oracle_url}/api/vc-types/{vc_type}/predicate-policy",
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"获取谓词策略失败: {e}")
        return None

    def verify_with_predicates(
        self,
        vc_type: str,
        vc_hash: str,
        attributes_to_reveal: Optional[list] = None,
        custom_predicates: Optional[Dict] = None,
        holder_did: Optional[str] = None
    ) -> Dict:
        """执行谓词验证"""
        payload = {
            "vc_type": vc_type,
            "vc_hash": vc_hash
        }

        if attributes_to_reveal:
            payload["attributes_to_reveal"] = attributes_to_reveal
        if custom_predicates:
            payload["predicates"] = custom_predicates
        if holder_did:
            payload["holder_did"] = holder_did

        try:
            response = requests.post(
                f"{self.oracle_url}/api/verify",
                json=payload,
                timeout=DEFAULT_TIMEOUT
            )
            return response.json()
        except Exception as e:
            logger.error(f"验证请求失败: {e}")
            return {"error": str(e)}

    def verify_with_default(self, vc_type: str, vc_hash: str) -> Dict:
        """使用默认策略验证"""
        payload = {
            "vc_type": vc_type,
            "vc_hash": vc_hash
        }

        try:
            response = requests.post(
                f"{self.oracle_url}/api/verify-default",
                json=payload,
                timeout=DEFAULT_TIMEOUT
            )
            return response.json()
        except Exception as e:
            logger.error(f"验证请求失败: {e}")
            return {"error": str(e)}

    def run_all_tests(self, vc_hashes: Dict[str, str]):
        """运行所有测试"""
        logger.info("=" * 70)
        logger.info("开始VP谓词验证测试")
        logger.info("=" * 70)

        # 测试1: 健康检查
        logger.info("\n[测试1] 健康检查")
        if not self.check_health():
            logger.error("健康检查失败，请确保服务已启动")
            return
        self.test_results.append(("健康检查", True))

        # 测试2: 获取VC类型
        logger.info("\n[测试2] 获取支持的VC类型")
        vc_types = self.get_vc_types()
        if vc_types:
            logger.info(f"支持的VC类型: {vc_types}")
            self.test_results.append(("获取VC类型", True))
        else:
            logger.error("获取VC类型失败")
            self.test_results.append(("获取VC类型", False))
            return

        # 测试3: 获取谓词策略
        logger.info("\n[测试3] 获取谓词策略")
        for vc_type in vc_types:
            policy = self.get_predicate_policy(vc_type)
            if policy:
                logger.info(f"\n{vc_type} 谓词策略:")
                logger.info(f"  揭示属性: {policy.get('attributes_to_reveal', [])}")
                predicates = policy.get('predicates', {})
                if predicates:
                    logger.info(f"  谓词数量: {len(predicates)}")
                    for pred_key, pred_def in predicates.items():
                        logger.info(f"    - {pred_key}: {pred_def.get('attribute')} "
                                   f"{pred_def.get('operator')} {pred_def.get('value')}")
                else:
                    logger.info("  谓词数量: 0 (仅披露)")
        self.test_results.append(("获取谓词策略", True))

        # 测试4: 执行验证（如果有vc_hash）
        if vc_hashes:
            logger.info("\n[测试4] 执行谓词验证")
            for vc_type, vc_hash in vc_hashes.items():
                if vc_type not in vc_types:
                    logger.warning(f"跳过不支持的VC类型: {vc_type}")
                    continue

                logger.info(f"\n验证 {vc_type}:")
                logger.info(f"  VC哈希: {vc_hash}")

                start_time = time.time()
                result = self.verify_with_default(vc_type, vc_hash)
                duration = time.time() - start_time

                if "error" in result:
                    logger.error(f"  验证失败: {result.get('error')}")
                    self.test_results.append((f"验证{vc_type}", False))
                else:
                    logger.info(f"  验证结果: {result.get('status')}")
                    logger.info(f"  验证通过: {result.get('verified')}")
                    logger.info(f"  耗时: {duration:.2f}秒")

                    # 显示揭示的属性
                    revealed = result.get('revealed_attributes', {})
                    if revealed:
                        logger.info(f"  揭示的属性:")
                        for attr, value in revealed.items():
                            logger.info(f"    - {attr}: {value}")

                    # 显示谓词结果
                    predicates = result.get('predicate_results', {})
                    if predicates:
                        logger.info(f"  谓词验证结果:")
                        for pred_key, pred_result in predicates.items():
                            satisfied = pred_result.get('satisfied', False)
                            status = "✓" if satisfied else "✗"
                            logger.info(f"    - {status} {pred_key}: {pred_result.get('attribute')} "
                                       f"{pred_result.get('operator')} {pred_result.get('expected_value')}")

                    self.test_results.append((f"验证{vc_type}", result.get('verified', False)))
        else:
            logger.info("\n[测试4] 跳过验证测试（未提供vc_hash）")

        # 测试5: 自定义谓词验证（可选）
        if vc_hashes and "InspectionReport" in vc_hashes:
            logger.info("\n[测试5] 自定义谓词验证")
            vc_hash = vc_hashes["InspectionReport"]

            # 使用自定义谓词
            custom_predicates = {
                "qty_check": {
                    "attribute": "productQuantity",
                    "operator": ">=",
                    "value": 1
                }
            }

            logger.info(f"自定义谓词: productQuantity >= 1")
            result = self.verify_with_predicates(
                vc_type="InspectionReport",
                vc_hash=vc_hash,
                custom_predicates=custom_predicates,
                attributes_to_reveal=["exporter", "contractName"]
            )

            if "error" not in result:
                logger.info(f"  验证结果: {result.get('status')}")
                predicates = result.get('predicate_results', {})
                if predicates:
                    for pred_key, pred_result in predicates.items():
                        logger.info(f"    - {pred_key}: satisfied={pred_result.get('satisfied')}")
                self.test_results.append(("自定义谓词验证", True))
            else:
                logger.error(f"  验证失败: {result.get('error')}")
                self.test_results.append(("自定义谓词验证", False))

        # 打印测试总结
        self._print_summary()

    def _print_summary(self):
        """打印测试总结"""
        logger.info("\n" + "=" * 70)
        logger.info("测试总结")
        logger.info("=" * 70)

        passed = 0
        failed = 0

        for test_name, success in self.test_results:
            status = "✓ 通过" if success else "✗ 失败"
            logger.info(f"  {status}: {test_name}")
            if success:
                passed += 1
            else:
                failed += 1

        logger.info(f"\n总计: {passed} 通过, {failed} 失败")
        logger.info("=" * 70)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="VP谓词验证测试")
    parser.add_argument(
        '--url',
        default=ORACLE_URL,
        help=f'Oracle服务URL (默认: {ORACLE_URL})'
    )
    parser.add_argument(
        '--vc-hash',
        action='append',
        nargs=2,
        metavar=('VC_TYPE', 'VC_HASH'),
        help='指定要验证的VC（可多次使用）'
    )
    parser.add_argument(
        '--vc-hash-file',
        help='从JSON文件加载VC哈希'
    )

    args = parser.parse_args()

    # 收集VC哈希
    vc_hashes = {}

    if args.vc_hash:
        for vc_type, vc_hash in args.vc_hash:
            vc_hashes[vc_type] = vc_hash

    if args.vc_hash_file:
        try:
            with open(args.vc_hash_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    vc_hashes.update(data)
        except Exception as e:
            logger.error(f"加载VC哈希文件失败: {e}")

    # 运行测试
    tester = PredicateVerificationTester(args.url)
    tester.run_all_tests(vc_hashes)


if __name__ == '__main__':
    main()
