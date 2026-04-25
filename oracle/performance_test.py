#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VP验证性能测试程序
测试不同属性个数对VP验证时间的影响，区分谓词验证和字符串属性验证的区别

使用方法:
    python3 performance_test.py
    python3 performance_test.py --config performance_config.json
    python3 performance_test.py --repeat 10 --warmup 3
"""

import argparse
import json
import logging
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

# ============================================================================
# 终端颜色类
# ============================================================================
class Colors:
    """终端颜色"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

    @staticmethod
    def strip(msg: str) -> str:
        """移除颜色代码"""
        for code in [Colors.HEADER, Colors.BLUE, Colors.CYAN, Colors.GREEN,
                     Colors.YELLOW, Colors.RED, Colors.END, Colors.BOLD]:
            msg = msg.replace(code, '')
        return msg


# ============================================================================
# 测试结果数据类
# ============================================================================
@dataclass
class TestResult:
    """单次测试结果"""
    scenario_name: str
    iteration: int
    duration: float
    server_duration: Optional[float] = None
    verified: bool = False
    success: bool = True
    error: Optional[str] = None
    attributes_count: int = 0
    has_predicate: bool = False


@dataclass
class ScenarioStats:
    """场景统计数据"""
    scenario_name: str
    has_predicate: bool
    attributes_count: int
    results: List[TestResult] = field(default_factory=list)

    @property
    def successful_results(self) -> List[TestResult]:
        return [r for r in self.results if r.success and r.verified]

    @property
    def durations(self) -> List[float]:
        return [r.duration for r in self.successful_results]

    @property
    def avg_duration(self) -> float:
        return statistics.mean(self.durations) if self.durations else 0

    @property
    def min_duration(self) -> float:
        return min(self.durations) if self.durations else 0

    @property
    def max_duration(self) -> float:
        return max(self.durations) if self.durations else 0

    @property
    def median_duration(self) -> float:
        return statistics.median(self.durations) if self.durations else 0

    @property
    def stdev_duration(self) -> float:
        return statistics.stdev(self.durations) if len(self.durations) > 1 else 0

    @property
    def success_rate(self) -> float:
        if not self.results:
            return 0
        return len(self.successful_results) / len(self.results) * 100


# ============================================================================
# 性能测试器
# ============================================================================
class PerformanceTester:
    """VP验证性能测试器"""

    def __init__(self, config_path: str):
        self.config = self.load_config(config_path)
        self.oracle_url = self.config['oracle_url']
        self.vc_type = self.config['vc_type']
        self.vc_hash = self.config['vc_hash']
        self.repeat_count = self.config.get('repeat_count', 5)
        self.warmup_count = self.config.get('warmup_count', 2)
        self.timeout = self.config.get('timeout', 180)
        self.all_results: List[TestResult] = []
        self.scenario_stats: Dict[str, ScenarioStats] = {}

    def load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"{Colors.RED}错误: 配置文件不存在: {config_path}{Colors.END}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"{Colors.RED}错误: 配置文件JSON格式错误: {e}{Colors.END}")
            sys.exit(1)

    def check_health(self) -> bool:
        """检查服务健康状态"""
        try:
            response = requests.get(f"{self.oracle_url}/api/health", timeout=10)
            if response.status_code == 200:
                return True
            print(f"{Colors.YELLOW}警告: 服务健康检查失败，状态码: {response.status_code}{Colors.END}")
            return False
        except Exception as e:
            print(f"{Colors.YELLOW}警告: 无法连接到服务: {e}{Colors.END}")
            return False

    def run_single_test(self, scenario: Dict, iteration: int, is_warmup: bool = False) -> TestResult:
        """执行单个测试场景"""
        # 构造请求
        payload = {
            "vc_type": self.vc_type,
            "vc_hash": self.vc_hash,
            "attributes_to_reveal": scenario.get('attributes_to_reveal', []),
            "custom_predicates": scenario.get('custom_predicates', {}),
            "custom_attribute_filters": scenario.get('custom_attribute_filters', {})
        }

        start_time = time.time()
        result = TestResult(
            scenario_name=scenario['name'],
            iteration=iteration,
            duration=0,
            attributes_count=len(scenario.get('custom_attribute_filters', {})),
            has_predicate=bool(scenario.get('custom_predicates'))
        )

        try:
            response = requests.post(
                f"{self.oracle_url}/api/verify",
                json=payload,
                timeout=self.timeout
            )
            result.duration = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                result.verified = data.get('verified', False)
                result.server_duration = data.get('duration_seconds')
            else:
                result.success = False
                try:
                    result.error = response.json().get('error', response.text)
                except:
                    result.error = response.text

        except requests.exceptions.Timeout:
            result.duration = time.time() - start_time
            result.success = False
            result.error = "Timeout"

        except Exception as e:
            result.duration = time.time() - start_time
            result.success = False
            result.error = str(e)

        return result

    def run_all_tests(self):
        """运行所有测试场景"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}VP验证性能测试{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")

        print(f"\n{Colors.BOLD}配置信息:{Colors.END}")
        print(f"  Oracle URL: {Colors.GREEN}{self.oracle_url}{Colors.END}")
        print(f"  VC类型: {Colors.GREEN}{self.vc_type}{Colors.END}")
        print(f"  VC哈希: {Colors.GREEN}{self.vc_hash[:16]}...{Colors.END}")
        print(f"  预热次数: {Colors.GREEN}{self.warmup_count}{Colors.END}")
        print(f"  每场景重复: {Colors.GREEN}{self.repeat_count}{Colors.END}")
        print(f"  测试场景数: {Colors.GREEN}{len(self.config['test_scenarios'])}{Colors.END}")

        total_tests = len(self.config['test_scenarios']) * self.repeat_count
        print(f"  总测试次数: {Colors.GREEN}{total_tests}{Colors.END}")

        # 健康检查
        if not self.check_health():
            print(f"\n{Colors.RED}错误: Oracle服务不可用，请确保服务已启动{Colors.END}")
            return

        print(f"\n{Colors.BOLD}开始测试...{Colors.END}\n")

        test_number = 0
        for scenario in self.config['test_scenarios']:
            scenario_name = scenario['name']
            has_predicate = bool(scenario.get('custom_predicates'))
            attrs_count = len(scenario.get('custom_attribute_filters', {}))

            # 初始化场景统计
            if scenario_name not in self.scenario_stats:
                self.scenario_stats[scenario_name] = ScenarioStats(
                    scenario_name=scenario_name,
                    has_predicate=has_predicate,
                    attributes_count=attrs_count
                )

            # 预热测试
            for i in range(self.warmup_count):
                result = self.run_single_test(scenario, i, is_warmup=True)
                # 不记录预热结果

            # 正式测试
            scenario_results = []
            for i in range(self.repeat_count):
                test_number += 1
                result = self.run_single_test(scenario, i)
                scenario_results.append(result)
                self.all_results.append(result)
                self.scenario_stats[scenario_name].results.append(result)

                # 打印进度
                status = f"{Colors.GREEN}✓{Colors.END}" if result.verified else f"{Colors.RED}✗{Colors.END}"
                print(f"  [{test_number:2d}/{total_tests}] {scenario_name:35s} "
                      f"迭代{i+1} {status} {result.duration:.2f}s")

        print(f"\n{Colors.GREEN}所有测试完成！{Colors.END}")

    def generate_report(self):
        """生成测试报告"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}测试报告{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")

        # 按场景分组统计
        print(f"\n{Colors.BOLD}1. 场景详细统计{Colors.END}")
        print(f"\n{'场景名称':<35} {'谓词':<6} {'属性数':<6} {'平均':<8} {'最小':<8} {'最大':<8} {'中位数':<8} {'成功率':<8}")
        print("-" * 95)

        for scenario_name, stats in self.scenario_stats.items():
            predicate_str = "是" if stats.has_predicate else "否"
            print(f"{scenario_name:<35} {predicate_str:<6} {stats.attributes_count:<6} "
                  f"{stats.avg_duration:>7.2f}s {stats.min_duration:>7.2f}s "
                  f"{stats.max_duration:>7.2f}s {stats.median_duration:>7.2f}s "
                  f"{stats.success_rate:>7.1f}%")

        # 场景1: 谓词影响对比
        print(f"\n{Colors.BOLD}2. 谓词影响分析{Colors.END}")
        scenario1a = self.scenario_stats.get("场景1a-基准线-无谓词-1字符串")
        scenario1b = self.scenario_stats.get("场景1b-有谓词-1字符串")

        if scenario1a and scenario1b:
            diff = scenario1b.avg_duration - scenario1a.avg_duration
            percent = (diff / scenario1a.avg_duration * 100) if scenario1a.avg_duration > 0 else 0
            print(f"  基准场景 (无谓词):     {scenario1a.avg_duration:.2f}s")
            print(f"  谓词场景 (有谓词):     {scenario1b.avg_duration:.2f}s")
            print(f"  谓词影响:             {Colors.YELLOW}{diff:+.2f}s ({percent:+.1f}%){Colors.END}")

        # 场景2: 有谓词时属性数量影响
        print(f"\n{Colors.BOLD}3. 有谓词时属性数量影响{Colors.END}")
        print(f"  {'属性数':<8} {'场景名称':<30} {'平均时间':<10} {'增量':<10}")
        print("-" * 60)

        prev_avg = None
        # 配置文件中的命名是: 场景2a-有谓词-2字符串 (2表示属性数)
        scenario2_names = [
            (1, "场景1b-有谓词-1字符串"),   # 复用场景1b作为1属性基准
            (2, "场景2a-有谓词-2字符串"),
            (3, "场景2b-有谓词-3字符串"),
            (4, "场景2c-有谓词-4字符串"),
            (5, "场景2d-有谓词-5字符串")
        ]
        for attr_count, scenario_name in scenario2_names:
            stats = self.scenario_stats.get(scenario_name)
            if stats:
                diff = stats.avg_duration - prev_avg if prev_avg is not None else 0
                diff_str = f"+{diff:.2f}s" if diff > 0 else "0.00s"
                print(f"  {attr_count:<8} {scenario_name:<30} {stats.avg_duration:>8.2f}s   {diff_str:>10}")
                prev_avg = stats.avg_duration

        # 场景3: 无谓词时属性数量影响
        print(f"\n{Colors.BOLD}4. 无谓词时属性数量影响{Colors.END}")
        print(f"  {'属性数':<8} {'场景名称':<30} {'平均时间':<10} {'增量':<10}")
        print("-" * 60)

        prev_avg = None
        scenario3_names = [
            (1, "场景3a-无谓词-1字符串"),
            (2, "场景3b-无谓词-2字符串"),
            (3, "场景3c-无谓词-3字符串"),
            (4, "场景3d-无谓词-4字符串"),
            (5, "场景3e-无谓词-5字符串")
        ]
        for attr_count, scenario_name in scenario3_names:
            stats = self.scenario_stats.get(scenario_name)
            if stats:
                diff = stats.avg_duration - prev_avg if prev_avg is not None else 0
                diff_str = f"+{diff:.2f}s" if diff > 0 else "0.00s"
                print(f"  {attr_count:<8} {scenario_name:<30} {stats.avg_duration:>8.2f}s   {diff_str:>10}")
                prev_avg = stats.avg_duration

        # 总结
        print(f"\n{Colors.BOLD}5. 总体分析{Colors.END}")
        self._print_summary()

        print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")

    def _print_summary(self):
        """打印总结分析"""
        # 计算谓词影响
        scenario1a = self.scenario_stats.get("场景1a-基准线-无谓词-1字符串")
        scenario1b = self.scenario_stats.get("场景1b-有谓词-1字符串")

        if scenario1a and scenario1b:
            predicate_impact = scenario1b.avg_duration - scenario1a.avg_duration
            predicate_impact_pct = (predicate_impact / scenario1a.avg_duration * 100) if scenario1a.avg_duration > 0 else 0
            print(f"  • 谓词验证增加时间: {predicate_impact:.2f}s ({predicate_impact_pct:.1f}%)")

        # 计算属性数量对有谓词的影响 (使用正确的场景名称)
        with_predicate_names = [
            "场景1b-有谓词-1字符串",  # 1属性基准
            "场景2a-有谓词-2字符串",
            "场景2b-有谓词-3字符串",
            "场景2c-有谓词-4字符串",
            "场景2d-有谓词-5字符串"
        ]
        with_predicate_times = []
        for name in with_predicate_names:
            stats = self.scenario_stats.get(name)
            if stats:
                with_predicate_times.append(stats.avg_duration)

        if len(with_predicate_times) >= 2:
            attr_growth_with_predicate = with_predicate_times[-1] - with_predicate_times[0]
            print(f"  • 有谓词时，4个额外属性增加时间: {attr_growth_with_predicate:.2f}s")

        # 计算属性数量对无谓词的影响
        without_predicate_names = [
            "场景3a-无谓词-1字符串",
            "场景3b-无谓词-2字符串",
            "场景3c-无谓词-3字符串",
            "场景3d-无谓词-4字符串",
            "场景3e-无谓词-5字符串"
        ]
        without_predicate_times = []
        for name in without_predicate_names:
            stats = self.scenario_stats.get(name)
            if stats:
                without_predicate_times.append(stats.avg_duration)

        if len(without_predicate_times) >= 2:
            attr_growth_without_predicate = without_predicate_times[-1] - without_predicate_times[0]
            print(f"  • 无谓词时，4个额外属性增加时间: {attr_growth_without_predicate:.2f}s")

        # 总体统计
        total_tests = len(self.all_results)
        successful_tests = sum(1 for r in self.all_results if r.success and r.verified)
        print(f"\n  总测试数: {total_tests}")
        print(f"  成功率: {successful_tests / total_tests * 100:.1f}%")

        avg_time = statistics.mean([r.duration for r in self.all_results if r.success])
        print(f"  平均响应时间: {avg_time:.2f}s")

    def save_results(self, output_file: str):
        """保存测试结果到JSON文件"""
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "oracle_url": self.oracle_url,
                "vc_type": self.vc_type,
                "vc_hash": self.vc_hash,
                "repeat_count": self.repeat_count,
                "warmup_count": self.warmup_count
            },
            "summary": self._generate_summary_dict(),
            "scenarios": []
        }

        for scenario_name, stats in self.scenario_stats.items():
            scenario_data = {
                "name": scenario_name,
                "has_predicate": stats.has_predicate,
                "attributes_count": stats.attributes_count,
                "statistics": {
                    "avg_duration": stats.avg_duration,
                    "min_duration": stats.min_duration,
                    "max_duration": stats.max_duration,
                    "median_duration": stats.median_duration,
                    "stdev_duration": stats.stdev_duration,
                    "success_rate": stats.success_rate
                },
                "results": [
                    {
                        "iteration": r.iteration,
                        "duration": r.duration,
                        "server_duration": r.server_duration,
                        "verified": r.verified,
                        "success": r.success,
                        "error": r.error
                    }
                    for r in stats.results
                ]
            }
            output_data["scenarios"].append(scenario_data)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\n{Colors.GREEN}结果已保存到: {output_file}{Colors.END}")

    def _generate_summary_dict(self) -> Dict:
        """生成总结字典"""
        summary = {
            "total_tests": len(self.all_results),
            "successful_tests": sum(1 for r in self.all_results if r.success and r.verified),
            "predicate_impact": {},
        }

        # 谓词影响
        scenario1a = self.scenario_stats.get("场景1a-基准线-无谓词-1字符串")
        scenario1b = self.scenario_stats.get("场景1b-有谓词-1字符串")

        if scenario1a and scenario1b:
            predicate_impact = scenario1b.avg_duration - scenario1a.avg_duration
            predicate_impact_pct = (predicate_impact / scenario1a.avg_duration * 100) if scenario1a.avg_duration > 0 else 0
            summary["predicate_impact"] = {
                "absolute_seconds": predicate_impact,
                "percentage": predicate_impact_pct,
                "baseline": scenario1a.avg_duration,
                "with_predicate": scenario1b.avg_duration
            }

        return summary


# ============================================================================
# 主函数
# ============================================================================
def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="VP验证性能测试程序",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 使用默认配置运行测试
  python3 performance_test.py

  # 指定配置文件
  python3 performance_test.py --config custom_config.json

  # 调整重复次数和预热次数
  python3 performance_test.py --repeat 10 --warmup 3

  # 保存结果到文件
  python3 performance_test.py --output results.json
        """
    )

    parser.add_argument(
        '--config',
        default='performance_config.json',
        help='配置文件路径 (默认: performance_config.json)'
    )

    parser.add_argument(
        '--repeat',
        type=int,
        help='每个场景的重复次数（覆盖配置文件）'
    )

    parser.add_argument(
        '--warmup',
        type=int,
        help='预热次数（覆盖配置文件）'
    )

    parser.add_argument(
        '--output', '-o',
        help='保存结果的JSON文件'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        help='请求超时时间（秒）'
    )

    args = parser.parse_args()

    # 检查配置文件
    config_path = Path(args.config)
    if not config_path.is_absolute():
        # 相对于脚本目录
        script_dir = Path(__file__).parent
        config_path = script_dir / args.config

    if not config_path.exists():
        print(f"{Colors.RED}错误: 配置文件不存在: {config_path}{Colors.END}")
        sys.exit(1)

    # 创建测试器
    tester = PerformanceTester(str(config_path))

    # 覆盖配置
    if args.repeat:
        tester.repeat_count = args.repeat
    if args.warmup:
        tester.warmup_count = args.warmup
    if args.timeout:
        tester.timeout = args.timeout

    # 运行测试
    try:
        tester.run_all_tests()
        tester.generate_report()

        # 保存结果
        if args.output:
            tester.save_results(args.output)

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}测试被中断{Colors.END}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}错误: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
