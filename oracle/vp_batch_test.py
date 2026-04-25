#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VP验证批量性能测试工具
模拟多进程并发验证请求，收集性能指标
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
from typing import Dict, List, Optional, Tuple

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
    UNDERLINE = '\033[4m'

    @staticmethod
    def strip(msg: str) -> str:
        """移除颜色代码（用于文件输出）"""
        for code in [Colors.HEADER, Colors.BLUE, Colors.CYAN, Colors.GREEN,
                     Colors.YELLOW, Colors.RED, Colors.END, Colors.BOLD,
                     Colors.UNDERLINE]:
            msg = msg.replace(code, '')
        return msg


# ============================================================================
# 单次验证函数
# ============================================================================
def verify_once(
    oracle_url: str,
    vc_hash: str,
    vc_type: str,
    attributes: List[str],
    timeout: int,
    holder_did: str = None
) -> Dict:
    """
    执行单次VP验证

    Args:
        oracle_url: Oracle服务URL
        vc_hash: VC哈希
        vc_type: VC类型
        attributes: 请求的属性列表
        timeout: 请求超时时间

    Returns:
        包含验证结果的字典
    """
    start_time = time.time()
    result = {
        "vc_type": vc_type,
        "vc_hash": vc_hash,
        "success": False,
        "verified": False,
        "duration": 0,
        "api_duration": None,
        "error": None,
        "status_code": None,
        "revealed_attrs": None,
        "uuid": None,
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
        result["status_code"] = response.status_code

        if response.status_code == 200:
            data = response.json()
            result["success"] = True
            result["verified"] = data.get("verified", False)
            result["api_duration"] = data.get("duration_seconds")
            result["revealed_attrs"] = data.get("revealed_attributes")
            result["uuid"] = data.get("uuid")
        else:
            try:
                result["error"] = response.json()
            except:
                result["error"] = response.text

    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        result["duration"] = elapsed
        result["error"] = "Timeout"

    except requests.exceptions.RequestException as e:
        elapsed = time.time() - start_time
        result["duration"] = elapsed
        result["error"] = str(e)

    except Exception as e:
        elapsed = time.time() - start_time
        result["duration"] = elapsed
        result["error"] = f"Unexpected: {str(e)}"

    return result


# ============================================================================
# 进程工作函数
# ============================================================================
def worker_process(
    process_id: int,
    iterations: int,
    interval: float,
    vc_hashes: List[str],
    vc_type: str,
    attributes: List[str],
    oracle_url: str,
    timeout: int,
    result_queue: multiprocessing.Queue,
    holder_did: str = None
) -> List[Dict]:
    """
    单个进程的工作循环

    Args:
        process_id: 进程ID
        iterations: 迭代次数
        interval: 验证间隔时间
        vc_hashes: VC哈希列表（循环使用）
        vc_type: VC类型
        attributes: 请求的属性列表
        oracle_url: Oracle服务URL
        timeout: 请求超时时间
        result_queue: 结果队列
        holder_did: Holder DID（用于进程间连接隔离）

    Returns:
        结果列表
    """
    results = []
    hash_count = len(vc_hashes)

    for i in range(iterations):
        # 循环使用不同的哈希值
        vc_hash = vc_hashes[i % hash_count] if hash_count > 0 else vc_hashes[0]

        result = verify_once(
            oracle_url=oracle_url,
            vc_hash=vc_hash,
            vc_type=vc_type,
            attributes=attributes,
            timeout=timeout,
            holder_did=holder_did
        )

        result["process_id"] = process_id
        result["iteration"] = i
        result["timestamp"] = datetime.now().isoformat()

        results.append(result)
        result_queue.put(result)

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

        total = len(self.results)
        successful = [r for r in self.results if r["success"]]
        verified = [r for r in self.results if r.get("verified")]
        failed = [r for r in self.results if not r["success"]]

        durations = [r["duration"] for r in self.results]
        successful_durations = [r["duration"] for r in successful] if successful else []

        # 时间统计
        total_time = 0
        if self.start_time and self.end_time:
            total_time = (self.end_time - self.start_time).total_seconds()

        # 计算百分位数
        def calc_percentile(data, p):
            if not data:
                return 0
            return statistics.quantiles(data, n=100)[int(p) - 1] if len(data) > 1 else data[0]

        stats = {
            "total_requests": total,
            "successful_requests": len(successful),
            "verified_requests": len(verified),
            "failed_requests": len(failed),
            "success_rate": len(successful) / total * 100 if total > 0 else 0,
            "verification_rate": len(verified) / total * 100 if total > 0 else 0,
            "duration": {
                "min": min(durations) if durations else 0,
                "max": max(durations) if durations else 0,
                "avg": statistics.mean(durations) if durations else 0,
                "median": statistics.median(durations) if durations else 0,
            },
            "total_time": total_time,
            "throughput": total / total_time if total_time > 0 else 0,
        }

        # 添加百分位数
        if len(durations) >= 2:
            percentiles = statistics.quantiles(durations, n=100)
            stats["duration"]["p50"] = percentiles[49]
            stats["duration"]["p75"] = percentiles[74]
            stats["duration"]["p90"] = percentiles[89]
            stats["duration"]["p95"] = percentiles[94]
            stats["duration"]["p99"] = percentiles[98]
        elif len(durations) == 1:
            stats["duration"]["p50"] = durations[0]
            stats["duration"]["p75"] = durations[0]
            stats["duration"]["p90"] = durations[0]
            stats["duration"]["p95"] = durations[0]
            stats["duration"]["p99"] = durations[0]
        else:
            stats["duration"]["p50"] = 0
            stats["duration"]["p75"] = 0
            stats["duration"]["p90"] = 0
            stats["duration"]["p95"] = 0
            stats["duration"]["p99"] = 0

        # 错误统计
        if failed:
            error_counts = {}
            for r in failed:
                error = r.get("error", "Unknown")
                # 将错误转换为字符串（如果是字典）
                if isinstance(error, dict):
                    error = json.dumps(error, ensure_ascii=False)
                else:
                    error = str(error)
                error_counts[error] = error_counts.get(error, 0) + 1
            stats["error_summary"] = error_counts

        return stats


# ============================================================================
# 终端输出类
# ============================================================================
class TerminalOutput:
    """终端输出管理"""

    def __init__(self, quiet: bool = False):
        self.quiet = quiet
        self.last_progress_len = 0

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

    def print_progress(self, current: int, total: int, result: Dict, show_bar: bool = True):
        """打印进度"""
        if self.quiet:
            return

        percent = int(current / total * 100) if total > 0 else 0
        bar_width = 20
        filled = int(bar_width * current / total) if total > 0 else 0
        bar = '█' * filled + '░' * (bar_width - filled)

        # 状态符号
        if result.get("verified"):
            status = f"{Colors.GREEN}✓{Colors.END} verified"
        elif result.get("success"):
            status = f"{Colors.YELLOW}○{Colors.END} unverified"
        else:
            status = f"{Colors.RED}✗{Colors.END} failed"

        duration_str = f"{result.get('duration', 0):.2f}s"

        if show_bar:
            line = f"\r[{current}/{total}] {status} ({duration_str})   [{Colors.CYAN}{bar}{Colors.END}] {percent}%"
        else:
            line = f"\r[{current}/{total}] {status} ({duration_str})"

        self.last_progress_len = len(Colors.strip(line)) + 5
        sys.stdout.write(line)
        sys.stdout.flush()

    def print_statistics(self, stats: Dict):
        """打印统计信息"""
        self._clear_progress()
        print()

        # 总体统计
        print(f"\n{Colors.BOLD}{Colors.CYAN}总体统计:{Colors.END}")
        print(f"  总请求数:      {Colors.BOLD}{stats.get('total_requests', 0)}{Colors.END}")
        print(f"  成功请求:      {Colors.GREEN}{stats.get('successful_requests', 0)}{Colors.END} "
              f"({stats.get('success_rate', 0):.1f}%)")
        print(f"  验证成功:      {Colors.GREEN}{stats.get('verified_requests', 0)}{Colors.END} "
              f"({stats.get('verification_rate', 0):.1f}%)")
        print(f"  失败请求:      {Colors.RED}{stats.get('failed_requests', 0)}{Colors.END}")

        # 响应时间统计
        dur = stats.get("duration", {})
        print(f"\n{Colors.BOLD}{Colors.CYAN}响应时间统计:{Colors.END}")
        print(f"  最小值:        {Colors.GREEN}{dur.get('min', 0):.2f}s{Colors.END}")
        print(f"  最大值:        {Colors.YELLOW}{dur.get('max', 0):.2f}s{Colors.END}")
        print(f"  平均值:        {Colors.GREEN}{dur.get('avg', 0):.2f}s{Colors.END}")
        print(f"  中位数:        {Colors.GREEN}{dur.get('median', 0):.2f}s{Colors.END}")
        print(f"  P50:          {dur.get('p50', 0):.2f}s")
        print(f"  P75:          {dur.get('p75', 0):.2f}s")
        print(f"  P90:          {dur.get('p90', 0):.2f}s")
        print(f"  P95:          {Colors.YELLOW}{dur.get('p95', 0):.2f}s{Colors.END}")
        print(f"  P99:          {Colors.YELLOW}{dur.get('p99', 0):.2f}s{Colors.END}")

        # 性能指标
        print(f"\n{Colors.BOLD}{Colors.CYAN}性能指标:{Colors.END}")
        print(f"  总耗时:        {stats.get('total_time', 0):.2f}s")
        print(f"  吞吐量:        {Colors.GREEN}{stats.get('throughput', 0):.2f} req/s{Colors.END}")
        print(f"  QPS:           {Colors.GREEN}{stats.get('throughput', 0):.2f}{Colors.END}")

        # 错误摘要
        if stats.get("error_summary"):
            print(f"\n{Colors.BOLD}{Colors.RED}错误摘要:{Colors.END}")
            for error, count in stats["error_summary"].items():
                error_str = str(error)[:50]
                if len(str(error)) > 50:
                    error_str += "..."
                print(f"  {Colors.RED}{error_str}{Colors.END}: {count}")

    def print_warning(self, msg: str):
        """打印警告"""
        self._clear_progress()
        print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")

    def print_error(self, msg: str):
        """打印错误"""
        self._clear_progress()
        print(f"{Colors.RED}✗ {msg}{Colors.END}")

    def print_success(self, msg: str):
        """打印成功消息"""
        self._clear_progress()
        print(f"{Colors.GREEN}✓ {msg}{Colors.END}")

    def print(self, msg: str):
        """打印普通消息"""
        self._clear_progress()
        print(msg)


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
    collector: StatsCollector = None
):
    """
    监控队列并显示进度

    Args:
        result_queue: 结果队列
        total_expected: 预期结果总数
        output: 输出管理器
        interrupt_flag: 中断标志
        collector: 统计收集器（可选）
    """
    received = 0

    while received < total_expected and not interrupt_flag.is_set():
        try:
            result = result_queue.get(timeout=0.1)
            received += 1
            # 更新统计收集器
            if collector is not None:
                collector.add_result(result)
            output.print_progress(received, total_expected, result)
        except queue.Empty:
            continue

    # 确保最后一条进度显示完整
    if received > 0:
        output.print_progress(received, total_expected, {"verified": True})


# ============================================================================
# 加载测试数据
# ============================================================================
def load_vc_hashes(uuid_path: Path, vc_type: str, limit: int = None) -> List[str]:
    """
    从uuid.json加载指定类型的VC哈希

    Args:
        uuid_path: uuid.json文件路径
        vc_type: VC类型
        limit: 最多返回的哈希数量

    Returns:
        VC哈希列表
    """
    try:
        with open(uuid_path, 'r', encoding='utf-8') as f:
            uuid_data = json.load(f)

        hashes = []
        for uuid_val, data in uuid_data.items():
            if data.get('vc_type') == vc_type:
                hashes.append(data.get('vc_hash'))
                if limit and len(hashes) >= limit:
                    break

        return hashes

    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []


# ============================================================================
# 结果导出
# ============================================================================
def export_results(results: List[Dict], stats: Dict, output_path: str):
    """导出结果到JSON文件"""
    export_data = {
        "timestamp": datetime.now().isoformat(),
        "statistics": stats,
        "raw_results": results
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)


# ============================================================================
# 主函数
# ============================================================================
def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="VP验证批量性能测试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基础测试: 4个进程，每进程执行10次验证
  python3 vp_batch_test.py

  # 高并发测试: 10个进程，每进程50次验证，间隔0.1秒
  python3 vp_batch_test.py --processes 10 --iterations 50 --interval 0.1

  # 压力测试: 20个进程，每进程100次验证
  python3 vp_batch_test.py -p 20 -i 100

  # 导出结果
  python3 vp_batch_test.py --output results.json
        """
    )

    parser.add_argument(
        '--processes', '-p',
        type=int,
        default=4,
        help='进程数量 (默认: 4)'
    )

    parser.add_argument(
        '--iterations', '-i',
        type=int,
        default=10,
        help='每进程循环次数 (默认: 10)'
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
        default=150,
        help='API请求超时秒数 (默认: 150)'
    )

    parser.add_argument(
        '--vc-type',
        default='InspectionReport',
        help='VC类型 (默认: InspectionReport)'
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
        '--vc-hash',
        type=str,
        default=None,
        help='指定单个VC哈希进行测试（覆盖uuid.json）'
    )

    parser.add_argument(
        '--attributes',
        nargs='+',
        default=['exporter', 'inspectionPassed', 'contractName'],
        help='请求的属性列表'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='结果输出文件路径 (JSON格式)'
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
    output.print_header("VP验证批量性能测试")

    # 准备VC哈希列表
    vc_hashes = None
    if args.vc_hash:
        vc_hashes = [args.vc_hash]
    else:
        vc_hashes = load_vc_hashes(Path(args.uuid_path), args.vc_type)
        if not vc_hashes:
            output.print_error(f"未找到 {args.vc_type} 类型的VC哈希")
            output.print_error(f"请检查 {args.uuid_path} 文件或使用 --vc-hash 指定哈希")
            return 1

    total_requests = args.processes * args.iterations

    # 打印配置
    config = {
        "进程数量": args.processes,
        "每进程迭代": args.iterations,
        "验证间隔": f"{args.interval}秒",
        "API超时": f"{args.timeout}秒",
        "VC类型": args.vc_type,
        "总请求数": total_requests,
        "可用VC哈希": len(vc_hashes),
        "Holder DID模式": args.holder_did_pattern,
    }
    output.print_config(config)

    # 确认继续（对于大量请求）
    if total_requests > 100 and not args.quiet:
        response = input(f"\n{Colors.YELLOW}即将发送 {total_requests} 个请求，按 Enter 继续...{Colors.END}")
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
        output.print_warning("\n接收到中断信号，正在停止...")
        interrupt_flag.set()
        # 等待子进程退出
        time.sleep(0.5)
        sys.exit(130)  # 128 + 2 (SIGINT)

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
                args=(result_queue, total_requests, output, interrupt_flag, collector),
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
                    args.vc_type,
                    args.attributes,
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
        output.print_warning("测试被中断")

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
        export_results(collector.results, stats, args.output)
        output.print_success(f"结果已导出到: {args.output}")

    # 完成
    output.print_header("测试完成")

    return 0


if __name__ == "__main__":
    sys.exit(main())
