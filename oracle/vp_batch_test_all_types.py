#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VP验证批量性能测试工具 - 4种VC类型组合验证
模拟多进程并发验证请求，每次验证包含4种VC类型，收集性能指标
"""

import argparse
import json
import multiprocessing
import os
import queue
import signal
import statistics
import sys
import time
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
        """移除颜色代码（用于文件输出）"""
        for code in [Colors.HEADER, Colors.BLUE, Colors.CYAN, Colors.GREEN,
                     Colors.YELLOW, Colors.RED, Colors.END, Colors.BOLD]:
            msg = msg.replace(code, '')
        return msg


# ============================================================================
# 4种VC类型配置
# ============================================================================
VC_TYPES_CONFIG = {
    "InspectionReport": {
        "attributes": ["exporter", "inspectionPassed", "contractName", "productName"]
    },
    "InsuranceContract": {
        "attributes": ["exporter", "importer", "contractName", "isInsured"]
    },
    "CertificateOfOrigin": {
        "attributes": ["exporter", "importer", "certifier", "placeOfOrigin"]
    },
    "BillOfLadingCertificate": {
        "attributes": ["exporter", "shippingCompany", "portOfDeparture", "portOfArrival"]
    }
}


# ============================================================================
# 数据加载函数
# ============================================================================
def load_uuid_data(uuid_path: Path) -> Dict:
    """加载uuid.json数据"""
    try:
        if uuid_path.exists():
            with open(uuid_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"{Colors.RED}警告: 无法加载uuid.json: {e}{Colors.END}")
        return {}


def get_vc_hashes_by_type(uuid_data: Dict, vc_type: str) -> List[str]:
    """获取指定类型的所有VC哈希"""
    hashes = []
    for uuid_val, data in uuid_data.items():
        if data.get('vc_type') == vc_type:
            hashes.append(data.get('vc_hash'))
    return hashes


def get_all_vc_hashes(uuid_data: Dict) -> Dict[str, List[str]]:
    """获取所有VC类型的哈希列表（每个类型取最新的一个）"""
    result = {}

    for vc_type in VC_TYPES_CONFIG.keys():
        # 找到该类型的所有VC，按时间戳排序取最新的
        matching_vcs = []
        for uuid_val, data in uuid_data.items():
            if data.get('vc_type') == vc_type:
                matching_vcs.append((uuid_val, data))

        if matching_vcs:
            # 按时间戳排序，取最新的
            matching_vcs.sort(key=lambda x: x[1].get('timestamp', ''), reverse=True)
            latest = matching_vcs[0][1]
            result[vc_type] = [latest.get('vc_hash')]
        else:
            result[vc_type] = []

    return result


# ============================================================================
# 验证函数
# ============================================================================
def verify_vc_type(
    oracle_url: str,
    vc_hash: str,
    vc_type: str,
    attributes: List[str],
    timeout: int,
    holder_did: str = None
) -> Dict:
    """执行单次VP验证"""
    start_time = time.time()
    result = {
        "vc_type": vc_type,
        "success": False,
        "verified": False,
        "duration": 0,
        "error": None
    }

    try:
        verify_request = {
            "vc_type": vc_type,
            "vc_hash": vc_hash,
            "requested_attributes": attributes,
            "holder_did": holder_did
        }

        response = requests.post(
            f"{oracle_url}/api/verify",
            json=verify_request,
            timeout=timeout
        )

        elapsed = time.time() - start_time
        result["duration"] = elapsed

        if response.status_code == 200:
            data = response.json()
            result["success"] = True
            result["verified"] = data.get("verified", False)
            result["uuid"] = data.get("uuid")
        else:
            result["error"] = f"HTTP {response.status_code}"

    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        result["duration"] = elapsed
        result["error"] = "Timeout"

    except requests.exceptions.RequestException as e:
        elapsed = time.time() - start_time
        result["duration"] = elapsed
        result["error"] = str(e)

    return result


def verify_all_types_once(
    oracle_url: str,
    vc_hashes: Dict[str, List[str]],
    timeout: int,
    holder_did: str = None
) -> Dict:
    """
    执行一次包含4种VC类型的验证

    Args:
        oracle_url: Oracle服务URL
        vc_hashes: 每种VC类型的哈希列表
        timeout: 请求超时时间

    Returns:
        包含所有4种类型验证结果的字典
    """
    batch_start = time.time()
    result = {
        "batch_id": str(int(time.time() * 1000000)),
        "success": True,
        "all_verified": True,
        "durations": {},
        "results": {},
        "errors": []
    }

    all_success = True

    for vc_type, config in VC_TYPES_CONFIG.items():
        hashes = vc_hashes.get(vc_type, [])
        if not hashes:
            result["success"] = False
            result["all_verified"] = False
            result["errors"].append(f"{vc_type}: 没有可用的VC")
            continue

        # 使用第一个哈希（可以扩展为轮询）
        vc_hash = hashes[0]

        vc_result = verify_vc_type(
            oracle_url=oracle_url,
            vc_hash=vc_hash,
            vc_type=vc_type,
            attributes=config["attributes"],
            timeout=timeout,
            holder_did=holder_did
        )

        result["results"][vc_type] = vc_result
        result["durations"][vc_type] = vc_result["duration"]

        if not vc_result["success"]:
            all_success = False
            result["success"] = False

        if not vc_result.get("verified", False):
            result["all_verified"] = False

        if vc_result.get("error"):
            result["errors"].append(f"{vc_type}: {vc_result['error']}")

    result["total_duration"] = time.time() - batch_start
    result["all_success"] = all_success

    return result


# ============================================================================
# 进程工作函数
# ============================================================================
def worker_process(
    process_id: int,
    iterations: int,
    interval: float,
    vc_hashes: Dict[str, List[str]],
    oracle_url: str,
    timeout: int,
    result_queue: multiprocessing.Queue,
    holder_did: str = None
) -> List[Dict]:
    """单个进程的工作循环"""
    results = []

    for i in range(iterations):
        batch_result = verify_all_types_once(
            oracle_url=oracle_url,
            vc_hashes=vc_hashes,
            timeout=timeout,
            holder_did=holder_did
        )

        batch_result["process_id"] = process_id
        batch_result["iteration"] = i
        batch_result["timestamp"] = datetime.now().isoformat()

        results.append(batch_result)
        result_queue.put(batch_result)

        # 间隔时间（最后一次不需要等待）
        if interval > 0 and i < iterations - 1:
            time.sleep(interval)

    return results


# ============================================================================
# 统计收集器
# ============================================================================
class StatsCollector:
    """收集和计算统计数据"""

    def __init__(self):
        self.results = []
        self.start_time = None
        self.end_time = None

    def add_result(self, result: Dict):
        """添加单个结果"""
        if self.start_time is None:
            self.start_time = datetime.fromisoformat(result["timestamp"])
        self.results.append(result)
        self.end_time = datetime.fromisoformat(result["timestamp"])

    def get_statistics(self) -> Dict:
        """计算并返回统计信息"""
        if not self.results:
            return {}

        total_batches = len(self.results)
        successful_batches = sum(1 for r in self.results if r.get("success"))
        verified_batches = sum(1 for r in self.results if r.get("all_verified"))

        # 每批次的4种VC类型统计
        vc_type_stats = {}
        for vc_type in VC_TYPES_CONFIG.keys():
            successful = sum(1 for r in self.results
                            if r.get("results", {}).get(vc_type, {}).get("success", False))
            verified = sum(1 for r in self.results
                          if r.get("results", {}).get(vc_type, {}).get("verified", False))
            durations = [r.get("durations", {}).get(vc_type, 0) for r in self.results
                         if vc_type in r.get("durations", {})]

            vc_type_stats[vc_type] = {
                "total": total_batches,
                "successful": successful,
                "verified": verified,
                "success_rate": successful / total_batches * 100 if total_batches > 0 else 0,
                "verification_rate": verified / total_batches * 100 if total_batches > 0 else 0,
            }

            if durations:
                vc_type_stats[vc_type]["avg_duration"] = statistics.mean(durations)
                vc_type_stats[vc_type]["min_duration"] = min(durations)
                vc_type_stats[vc_type]["max_duration"] = max(durations)

        # 总批次统计
        total_durations = [r["total_duration"] for r in self.results]

        total_time = 0
        if self.start_time and self.end_time:
            total_time = (self.end_time - self.start_time).total_seconds()

        stats = {
            "total_batches": total_batches,
            "successful_batches": successful_batches,
            "verified_batches": verified_batches,
            "batch_success_rate": successful_batches / total_batches * 100 if total_batches > 0 else 0,
            "batch_verification_rate": verified_batches / total_batches * 100 if total_batches > 0 else 0,
            "vc_type_stats": vc_type_stats,
            "duration": {
                "min": min(total_durations) if total_durations else 0,
                "max": max(total_durations) if total_durations else 0,
                "avg": statistics.mean(total_durations) if total_durations else 0,
                "median": statistics.median(total_durations) if total_durations else 0,
            },
            "total_time": total_time,
            "throughput": total_batches / total_time if total_time > 0 else 0,
        }

        # 添加百分位数
        if len(total_durations) >= 2:
            percentiles = statistics.quantiles(total_durations, n=100)
            stats["duration"]["p50"] = percentiles[49]
            stats["duration"]["p75"] = percentiles[74]
            stats["duration"]["p90"] = percentiles[89]
            stats["duration"]["p95"] = percentiles[94]
            stats["duration"]["p99"] = percentiles[98]
        elif len(total_durations) == 1:
            v = total_durations[0]
            stats["duration"]["p50"] = stats["duration"]["p75"] = v
            stats["duration"]["p90"] = stats["duration"]["p95"] = v
            stats["duration"]["p99"] = v

        return stats


# ============================================================================
# 终端输出类
# ============================================================================
class TerminalOutput:
    """终端输出管理"""

    def __init__(self, quiet: bool = False):
        self.quiet = quiet
        self.last_progress_len = 0
        self.completed_count = 0
        self.total_batches = 0

    def _clear_progress(self):
        """清除上一行进度"""
        if self.last_progress_len > 0:
            sys.stdout.write('\r' + ' ' * self.last_progress_len + '\r')
            self.last_progress_len = 0

    def print_header(self, title: str):
        """打印标题"""
        self._clear_progress()
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}  {title}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")

    def print_config(self, config: Dict):
        """打印配置"""
        self._clear_progress()
        print(f"\n{Colors.BOLD}配置:{Colors.END}")
        for key, value in config.items():
            print(f"  {Colors.CYAN}{key}:{Colors.END} {Colors.GREEN}{value}{Colors.END}")

    def set_total_batches(self, total: int):
        """设置总批次数"""
        self.total_batches = total
        self.completed_count = 0

    def print_progress(self, batch_result: Dict):
        """打印进度"""
        if self.quiet:
            return

        self.completed_count += 1
        percent = int(self.completed_count / self.total_batches * 100) if self.total_batches > 0 else 0

        bar_width = 20
        filled = int(bar_width * self.completed_count / self.total_batches) if self.total_batches > 0 else 0
        bar = '█' * filled + '░' * (bar_width - filled)

        # 统计本批次中各VC类型的验证状态
        vc_results = []
        for vc_type in VC_TYPES_CONFIG.keys():
            vc_result = batch_result.get("results", {}).get(vc_type, {})
            if vc_result.get("verified"):
                vc_results.append(f"{Colors.GREEN}✓{Colors.END}")
            elif vc_result.get("success"):
                vc_results.append(f"{Colors.YELLOW}○{Colors.END}")
            else:
                vc_results.append(f"{Colors.RED}✗{Colors.END}")

        vc_status = ' '.join(vc_results)
        duration = batch_result.get("total_duration", 0)

        line = f"\r[{self.completed_count}/{self.total_batches}] [{vc_status}] {duration:.1f}s   [{Colors.CYAN}{bar}{Colors.END}] {percent}%"
        self.last_progress_len = len(Colors.strip(line)) + 5
        sys.stdout.write(line)
        sys.stdout.flush()

    def print_statistics(self, stats: Dict):
        """打印统计信息"""
        self._clear_progress()

        # 总体批次统计
        print(f"\n{Colors.BOLD}{Colors.CYAN}批次统计:{Colors.END}")
        print(f"  总批次数:      {Colors.BOLD}{stats.get('total_batches', 0)}{Colors.END}")
        print(f"  成功批次:      {Colors.GREEN}{stats.get('successful_batches', 0)}{Colors.END} "
              f"({stats.get('batch_success_rate', 0):.1f}%)")
        print(f"  完全验证:      {Colors.GREEN}{stats.get('verified_batches', 0)}{Colors.END} "
              f"({stats.get('batch_verification_rate', 0):.1f}%)")

        # 响应时间统计
        dur = stats.get("duration", {})
        print(f"\n{Colors.BOLD}{Colors.CYAN}批次响应时间统计:{Colors.END}")
        print(f"  最小值:        {Colors.GREEN}{dur.get('min', 0):.2f}s{Colors.END}")
        print(f"  最大值:        {Colors.YELLOW}{dur.get('max', 0):.2f}s{Colors.END}")
        print(f"  平均值:        {Colors.GREEN}{dur.get('avg', 0):.2f}s{Colors.END}")
        print(f"  中位数:        {Colors.GREEN}{dur.get('median', 0):.2f}s{Colors.END}")
        print(f"  P95:          {Colors.YELLOW}{dur.get('p95', 0):.2f}s{Colors.END}")

        # 性能指标
        print(f"\n{Colors.BOLD}{Colors.CYAN}性能指标:{Colors.END}")
        print(f"  总耗时:        {stats.get('total_time', 0):.2f}s")
        print(f"  吞吐量:        {Colors.GREEN}{stats.get('throughput', 0):.2f} batch/s{Colors.END}")

        # 各VC类型统计
        print(f"\n{Colors.BOLD}{Colors.CYAN}各VC类型统计:{Colors.END}")
        for vc_type, type_stats in stats.get("vc_type_stats", {}).items():
            print(f"\n  {Colors.CYAN}{vc_type}:{Colors.END}")
            print(f"    成功: {type_stats['successful']}/{type_stats['total']} "
                  f"({type_stats['success_rate']:.1f}%)")
            print(f"    验证: {type_stats['verified']}/{type_stats['total']} "
                  f"({type_stats['verification_rate']:.1f}%)")
            if 'avg_duration' in type_stats:
                print(f"    平均耗时: {type_stats['avg_duration']:.2f}s")

    def print_error(self, msg: str):
        """打印错误"""
        self._clear_progress()
        print(f"{Colors.RED}✗ {msg}{Colors.END}")

    def print(self, msg: str):
        """打印普通消息"""
        self._clear_progress()
        print(msg)

    def print_success(self, msg: str):
        """打印成功消息"""
        self._clear_progress()
        print(f"{Colors.GREEN}✓ {msg}{Colors.END}")


# ============================================================================
# 全局中断标志
# ============================================================================
class InterruptFlag:
    """中断标志（用于跨进程通信）"""
    def __init__(self):
        self.value = multiprocessing.Value('i', 0)

    def set(self):
        self.value.value = 1

    def is_set(self) -> bool:
        return self.value.value == 1


# ============================================================================
# 进度监控线程
# ============================================================================
def progress_monitor(
    result_queue: multiprocessing.Queue,
    total_expected: int,
    output: TerminalOutput,
    interrupt_flag: InterruptFlag,
    collector: 'StatsCollector' = None
):
    """监控队列并显示进度"""
    received = 0

    while received < total_expected and not interrupt_flag.is_set():
        try:
            result = result_queue.get(timeout=0.1)
            received += 1
            # 更新统计收集器
            if collector is not None:
                collector.add_result(result)
            output.print_progress(result)
        except queue.Empty:
            continue

    # 确保最后一条进度显示完整
    if received > 0:
        output.print_progress({
            "results": {vc_type: {"verified": True} for vc_type in VC_TYPES_CONFIG},
            "total_duration": 0
        })


# ============================================================================
# 主函数
# ============================================================================
def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="VP验证批量性能测试工具 - 4种VC类型组合验证",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基础测试: 2个进程，每进程5次验证（每验证包含4种VC类型）
  python3 vp_batch_test_all_types.py

  # 高并发测试: 5个进程，每进程10次验证
  python3 vp_batch_test_all_types.py -p 5 -i 10

  # 压力测试: 10个进程，每进程20次验证，间隔1秒
  python3 vp_batch_test_all_types.py -p 10 -i 20 -t 1

  # 导出结果
  python3 vp_batch_test_all_types.py --output results.json
        """
    )

    parser.add_argument(
        '--processes', '-p',
        type=int,
        default=2,
        help='进程数量 (默认: 2)'
    )

    parser.add_argument(
        '--iterations', '-i',
        type=int,
        default=5,
        help='每进程循环次数 (默认: 5)'
    )

    parser.add_argument(
        '--interval', '-t',
        type=float,
        default=0,
        help='验证间隔秒数 (默认: 0)'
    )

    parser.add_argument(
        '--timeout', '-T',
        type=int,
        default=180,
        help='API请求超时秒数 (默认: 180，因为每批验证需要4次请求)'
    )

    parser.add_argument(
        '--oracle-url',
        default='http://localhost:7002',
        help='Oracle服务URL (默认: http://localhost:7002)'
    )

    parser.add_argument(
        '--uuid-path',
        type=str,
        default=None,
        help='uuid.json文件路径 (默认: oracle/logs/uuid.json)'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='结果输出文件 (JSON格式)'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='安静模式，减少输出'
    )

    parser.add_argument(
        '--no-progress',
        action='store_true',
        help='不显示进度条'
    )

    parser.add_argument(
        '--holder-did-pattern',
        type=str,
        default='batch-test-{process_id}',
        help='Holder DID模式，{process_id}会被替换为进程ID (默认: batch-test-{process_id})'
    )

    args = parser.parse_args()

    # 确定uuid路径
    if args.uuid_path is None:
        args.uuid_path = str(Path(__file__).parent / "logs" / "uuid.json")

    # 初始化输出
    output = TerminalOutput(quiet=args.quiet)

    # 打印标题
    output.print_header("VP验证批量性能测试 - 4种VC类型组合验证")

    # 加载VC哈希数据
    uuid_data = load_uuid_data(Path(args.uuid_path))
    if not uuid_data:
        output.print_error(f"无法加载uuid.json: {args.uuid_path}")
        return 1

    vc_hashes = get_all_vc_hashes(uuid_data)

    # 检查每种VC类型是否有可用的哈希
    missing_types = []
    for vc_type in VC_TYPES_CONFIG.keys():
        if not vc_hashes.get(vc_type):
            missing_types.append(vc_type)

    if missing_types:
        output.print_error(f"以下VC类型没有可用的VC: {', '.join(missing_types)}")
        return 1

    total_batches = args.processes * args.iterations

    # 打印配置
    config = {
        "进程数量": args.processes,
        "每进程迭代": args.iterations,
        "验证间隔": f"{args.interval}秒",
        "API超时": f"{args.timeout}秒",
        "总批次数": total_batches,
        "Holder DID模式": args.holder_did_pattern,
    }

    # 添加VC哈希数量信息
    for vc_type, hashes in vc_hashes.items():
        config[f"{vc_type}可用VC"] = len(hashes)

    output.print_config(config)

    # 确认继续（对于大量请求）
    if total_batches > 20 and not args.quiet:
        response = input(f"\n{Colors.YELLOW}即将发送 {total_batches} 个批次，每批次验证4种VC类型（共{total_batches*4}次验证），按 Enter 继续...{Colors.END}")
        if response.lower() in ['q', 'quit', 'exit', 'n', 'no']:
            print("测试已取消")
            return 0

    # 初始化
    interrupt_flag = InterruptFlag()
    collector = StatsCollector()
    result_queue = multiprocessing.Queue()

    # 设置信号处理
    original_handler = signal.getsignal(signal.SIGINT)

    def signal_handler(sig, frame):
        output.print_error("\n接收到中断信号，正在停止...")
        interrupt_flag.set()
        time.sleep(0.5)
        sys.exit(130)

    signal.signal(signal.SIGINT, signal_handler)

    # 启动时间
    test_start_time = time.time()

    # 创建并启动进程池
    processes = []
    output.print(f"\n{Colors.BOLD}启动测试...{Colors.END}")

    try:
        # 启动进度监控线程
        monitor_thread = None
        if not args.no_progress and not args.quiet:
            import threading
            monitor_thread = threading.Thread(
                target=progress_monitor,
                args=(result_queue, total_batches, output, interrupt_flag, collector),
                daemon=True
            )
            monitor_thread.start()

        # 启动工作进程
        for process_id in range(args.processes):
            # 为每个进程生成唯一的holder_did
            holder_did = args.holder_did_pattern.format(process_id=process_id)

            p = multiprocessing.Process(
                target=worker_process,
                args=(
                    process_id,
                    args.iterations,
                    args.interval,
                    vc_hashes,
                    args.oracle_url,
                    args.timeout,
                    result_queue,
                    holder_did
                )
            )
            p.start()
            processes.append(p)

        # 等待所有进程完成
        for p in processes:
            p.join()

        # 等待监控线程结束
        if monitor_thread:
            monitor_thread.join(timeout=1)

        # 从队列收集剩余结果
        while not result_queue.empty():
            collector.add_result(result_queue.get())

    except KeyboardInterrupt:
        interrupt_flag.set()
        output.print_error("测试被中断")

        # 终止所有进程
        for p in processes:
            if p.is_alive():
                p.terminate()
                p.join(timeout=1)

    finally:
        signal.signal(signal.SIGINT, original_handler)

    test_end_time = time.time()

    # 打印统计
    stats = collector.get_statistics()
    stats["test_wall_time"] = test_end_time - test_start_time

    output.print_statistics(stats)

    # 导出结果
    if args.output:
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "oracle_url": args.oracle_url,
            "config": {
                "processes": args.processes,
                "iterations": args.iterations,
                "interval": args.interval,
                "timeout": args.timeout,
                "total_batches": total_batches,
            },
            "vc_hashes": {k: len(v) for k, v in vc_hashes.items()},
            "statistics": stats,
            "raw_results": collector.results
        }
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        output.print_success(f"\n结果已导出到: {args.output}")

    # 完成
    output.print_header("测试完成")

    return 0


if __name__ == "__main__":
    sys.exit(main())
