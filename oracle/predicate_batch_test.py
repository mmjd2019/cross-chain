#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VP谓词验证批量测试脚本
批量测试谓词验证Oracle服务的性能和稳定性

使用方法:
    # 测试1个进程，每个进程2次迭代
    python3 predicate_batch_test.py -p 1 -i 2

    # 测试4个进程，每个进程5次迭代
    python3 predicate_batch_test.py -p 4 -i 5

    # 使用指定的VC哈希文件
    python3 predicate_batch_test.py --vc-hash-file vc_hashes.json
"""

import argparse
import json
import logging
import multiprocessing
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(processName)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 服务配置
ORACLE_URL = "http://localhost:7003"
DEFAULT_TIMEOUT = 180


@dataclass
class TestResult:
    """测试结果"""
    test_id: int
    vc_type: str
    vc_hash: str
    success: bool
    verified: bool
    duration_seconds: float
    error: Optional[str] = None
    predicate_results: Optional[Dict] = None
    revealed_attributes: Optional[Dict] = None


class PredicateBatchTester:
    """谓词验证批量测试器"""

    def __init__(self, oracle_url: str = ORACLE_URL):
        self.oracle_url = oracle_url
        self.results: List[TestResult] = []

    def check_health(self) -> bool:
        """检查服务健康状态"""
        try:
            response = requests.get(f"{self.oracle_url}/api/health", timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def get_vc_types(self) -> List[str]:
        """获取支持的VC类型"""
        try:
            response = requests.get(f"{self.oracle_url}/api/vc-types", timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"获取VC类型失败: {e}")
        return []

    def verify_vc(self, vc_type: str, vc_hash: str, test_id: int) -> TestResult:
        """执行单个验证"""
        start_time = time.time()

        try:
            response = requests.post(
                f"{self.oracle_url}/api/verify-default",
                json={
                    "vc_type": vc_type,
                    "vc_hash": vc_hash
                },
                timeout=DEFAULT_TIMEOUT
            )

            duration = time.time() - start_time
            data = response.json()

            if "error" in data:
                return TestResult(
                    test_id=test_id,
                    vc_type=vc_type,
                    vc_hash=vc_hash,
                    success=False,
                    verified=False,
                    duration_seconds=duration,
                    error=data.get("error")
                )

            return TestResult(
                test_id=test_id,
                vc_type=vc_type,
                vc_hash=vc_hash,
                success=True,
                verified=data.get("verified", False),
                duration_seconds=duration,
                predicate_results=data.get("predicate_results"),
                revealed_attributes=data.get("revealed_attributes")
            )

        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_id=test_id,
                vc_type=vc_type,
                vc_hash=vc_hash,
                success=False,
                verified=False,
                duration_seconds=duration,
                error=str(e)
            )

    def run_batch_test(
        self,
        vc_hashes: Dict[str, str],
        num_processes: int = 1,
        iterations: int = 1
    ) -> List[TestResult]:
        """
        运行批量测试

        参数:
            vc_hashes: VC类型到哈希的映射
            num_processes: 并发进程数
            iterations: 每个VC的迭代次数

        返回:
            测试结果列表
        """
        logger.info("=" * 70)
        logger.info("开始批量谓词验证测试")
        logger.info("=" * 70)
        logger.info(f"并发进程: {num_processes}")
        logger.info(f"每VC迭代: {iterations}")
        logger.info(f"VC类型数: {len(vc_hashes)}")

        # 健康检查
        if not self.check_health():
            logger.error("服务健康检查失败，请确保服务已启动")
            return []

        # 构建测试任务列表
        tasks: List[Tuple[str, str, int]] = []
        test_id = 0

        for vc_type, vc_hash in vc_hashes.items():
            for _ in range(iterations):
                test_id += 1
                tasks.append((vc_type, vc_hash, test_id))

        logger.info(f"总测试任务: {len(tasks)}")

        # 执行测试
        start_time = time.time()
        results: List[TestResult] = []

        with ThreadPoolExecutor(max_workers=num_processes) as executor:
            futures = {
                executor.submit(self.verify_vc, vc_type, vc_hash, tid): (vc_type, tid)
                for vc_type, vc_hash, tid in tasks
            }

            for future in as_completed(futures):
                vc_type, tid = futures[future]
                try:
                    result = future.result()
                    results.append(result)

                    status = "✓" if result.verified else "✗"
                    logger.info(
                        f"[{tid}] {vc_type}: {status} "
                        f"({result.duration_seconds:.2f}s)"
                    )

                    if not result.success:
                        logger.warning(f"[{tid}] 错误: {result.error}")

                except Exception as e:
                    logger.error(f"[{tid}] 测试异常: {e}")
                    results.append(TestResult(
                        test_id=tid,
                        vc_type=vc_type,
                        vc_hash="",
                        success=False,
                        verified=False,
                        duration_seconds=0,
                        error=str(e)
                    ))

        total_duration = time.time() - start_time
        self.results = results

        # 打印统计
        self._print_statistics(results, total_duration)

        return results

    def _print_statistics(self, results: List[TestResult], total_duration: float):
        """打印测试统计"""
        logger.info("\n" + "=" * 70)
        logger.info("测试统计")
        logger.info("=" * 70)

        total = len(results)
        successful = sum(1 for r in results if r.success)
        verified = sum(1 for r in results if r.verified)
        failed = total - successful

        logger.info(f"总测试数: {total}")
        logger.info(f"成功执行: {successful} ({successful/total*100:.1f}%)")
        logger.info(f"验证通过: {verified} ({verified/total*100:.1f}%)")
        logger.info(f"执行失败: {failed}")

        # 时间统计
        durations = [r.duration_seconds for r in results if r.success]
        if durations:
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)

            logger.info(f"\n时间统计:")
            logger.info(f"  总耗时: {total_duration:.2f}s")
            logger.info(f"  平均耗时: {avg_duration:.2f}s")
            logger.info(f"  最小耗时: {min_duration:.2f}s")
            logger.info(f"  最大耗时: {max_duration:.2f}s")
            logger.info(f"  吞吐量: {len(durations)/total_duration:.2f} req/s")

        # 按VC类型统计
        logger.info(f"\n按VC类型统计:")
        vc_type_stats: Dict[str, Dict] = {}

        for r in results:
            if r.vc_type not in vc_type_stats:
                vc_type_stats[r.vc_type] = {
                    "total": 0, "verified": 0, "failed": 0, "durations": []
                }
            vc_type_stats[r.vc_type]["total"] += 1
            if r.verified:
                vc_type_stats[r.vc_type]["verified"] += 1
            if not r.success:
                vc_type_stats[r.vc_type]["failed"] += 1
            if r.success:
                vc_type_stats[r.vc_type]["durations"].append(r.duration_seconds)

        for vc_type, stats in vc_type_stats.items():
            avg = sum(stats["durations"]) / len(stats["durations"]) if stats["durations"] else 0
            logger.info(
                f"  {vc_type}: {stats['verified']}/{stats['total']} 通过, "
                f"平均 {avg:.2f}s"
            )

        # 谓词验证统计
        logger.info(f"\n谓词验证统计:")
        predicate_stats: Dict[str, Dict] = {}

        for r in results:
            if r.predicate_results:
                for pred_key, pred_result in r.predicate_results.items():
                    if pred_key not in predicate_stats:
                        predicate_stats[pred_key] = {"satisfied": 0, "total": 0}
                    predicate_stats[pred_key]["total"] += 1
                    if pred_result.get("satisfied"):
                        predicate_stats[pred_key]["satisfied"] += 1

        for pred_key, stats in predicate_stats.items():
            rate = stats["satisfied"] / stats["total"] * 100 if stats["total"] else 0
            logger.info(f"  {pred_key}: {stats['satisfied']}/{stats['total']} ({rate:.1f}%)")

        logger.info("=" * 70)

    def save_results(self, output_file: str):
        """保存测试结果到JSON文件"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "results": [
                {
                    "test_id": r.test_id,
                    "vc_type": r.vc_type,
                    "vc_hash": r.vc_hash,
                    "success": r.success,
                    "verified": r.verified,
                    "duration_seconds": r.duration_seconds,
                    "error": r.error,
                    "predicate_results": r.predicate_results,
                    "revealed_attributes": r.revealed_attributes
                }
                for r in self.results
            ]
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"结果已保存到: {output_file}")


def load_vc_hashes_from_file(file_path: str) -> Dict[str, str]:
    """从文件加载VC哈希"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            elif isinstance(data, list):
                # 如果是列表，尝试从每个元素中提取
                result = {}
                for item in data:
                    if isinstance(item, dict) and "vc_type" in item and "vc_hash" in item:
                        result[item["vc_type"]] = item["vc_hash"]
                return result
    except Exception as e:
        logger.error(f"加载VC哈希文件失败: {e}")
    return {}


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="VP谓词验证批量测试")
    parser.add_argument(
        '--url',
        default=ORACLE_URL,
        help=f'Oracle服务URL (默认: {ORACLE_URL})'
    )
    parser.add_argument(
        '-p', '--processes',
        type=int,
        default=1,
        help='并发进程数 (默认: 1)'
    )
    parser.add_argument(
        '-i', '--iterations',
        type=int,
        default=1,
        help='每个VC的迭代次数 (默认: 1)'
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
    parser.add_argument(
        '-o', '--output',
        help='保存测试结果的JSON文件'
    )

    args = parser.parse_args()

    # 收集VC哈希
    vc_hashes = {}

    if args.vc_hash:
        for vc_type, vc_hash in args.vc_hash:
            vc_hashes[vc_type] = vc_hash

    if args.vc_hash_file:
        file_hashes = load_vc_hashes_from_file(args.vc_hash_file)
        vc_hashes.update(file_hashes)

    if not vc_hashes:
        logger.error("未提供任何VC哈希，请使用 --vc-hash 或 --vc-hash-file 指定")
        sys.exit(1)

    # 运行测试
    tester = PredicateBatchTester(args.url)
    tester.run_batch_test(
        vc_hashes=vc_hashes,
        num_processes=args.processes,
        iterations=args.iterations
    )

    # 保存结果
    if args.output:
        tester.save_results(args.output)


if __name__ == '__main__':
    main()
