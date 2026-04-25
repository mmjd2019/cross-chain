#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VC 跨链传输性能分析程序

功能：
1. 单次传输统计：从发起跨链传输到确认写入 chain-b 的总时间、Gas 消耗、成功/失败状态
2. 多进程支持：可配置多个进程并发执行
3. 每进程多次传输：每个进程可配置连续传输次数
4. 统计指标：时间均值、方差、最快/最慢、吞吐量

注意：创建随机 VC 的时间不计入传输总时间
"""

import argparse
import json
import multiprocessing
import os
import queue
import secrets
import signal
import statistics
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from web3 import Web3
from web3.middleware import geth_poa_middleware


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
# 数据类
# ============================================================================
@dataclass
class TransferResult:
    """单次传输结果"""
    process_id: int
    iteration: int
    timestamp: str
    vc_creation_time: float      # 创建 VC 时间 (不计入总时间)
    initiate_time: float         # 发起跨链传输时间
    transfer_time: float         # 等待传输完成时间
    total_time: float            # 总时间 = initiate + transfer
    initiate_gas_used: int       # Gas 消耗
    success: bool
    error: Optional[str]
    vc_hash: str
    tx_hash_initiate: str


@dataclass
class ProcessStats:
    """单个进程统计"""
    process_id: int
    total_transfers: int
    successful_transfers: int
    failed_transfers: int
    min_time: float
    max_time: float
    avg_time: float
    times: List[float]
    gas_list: List[int]
    total_gas: int
    avg_gas: float
    throughput: float
    start_time: Optional[str] = None
    end_time: Optional[str] = None


@dataclass
class GlobalStats:
    """全局统计"""
    total_transfers: int
    successful_transfers: int
    failed_transfers: int
    success_rate: float
    min_time: float
    max_time: float
    avg_time: float
    variance: float
    std_dev: float
    median: float
    p50: float
    p75: float
    p90: float
    p95: float
    p99: float
    total_gas: int
    avg_gas: float
    throughput: float
    total_duration: float


# ============================================================================
# 配置加载
# ============================================================================
CONFIG_FILE = Path(__file__).parent.parent / "config" / "cross_chain_oracle_config.json"
VC_ISSUANCE_CONFIG_FILE = Path(__file__).parent / "vc_issuance_config.json"

VC_MANAGERS = {
    'InspectionReport': {
        'contract_name': 'InspectionReportVCManager',
        'abi_file': 'InspectionReportVCManager.json'
    },
    'InsuranceContract': {
        'contract_name': 'InsuranceContractVCManager',
        'abi_file': 'InsuranceContractVCManager.json'
    },
    'CertificateOfOrigin': {
        'contract_name': 'CertificateOfOriginVCManager',
        'abi_file': 'CertificateOfOriginVCManager.json'
    },
    'BillOfLadingCertificate': {
        'contract_name': 'BillOfLadingVCManager',
        'abi_file': 'BillOfLadingVCManager.json'
    }
}


def load_config() -> dict:
    """加载配置文件"""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"配置文件不存在: {CONFIG_FILE}")

    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)


def load_vc_issuance_config() -> dict:
    """加载 VC 发行配置"""
    if VC_ISSUANCE_CONFIG_FILE.exists():
        with open(VC_ISSUANCE_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}


def load_contract_abi(contract_name: str) -> dict:
    """加载合约ABI"""
    possible_paths = [
        Path(__file__).parent.parent / "contracts" / "kept" / "contract_abis" / f"{contract_name}.json",
        Path(__file__).parent.parent / "contracts" / "kept" / f"{contract_name}.json",
        Path(__file__).parent.parent / "contracts" / "kept" / "build" / f"{contract_name}.json",
    ]

    for path in possible_paths:
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)['abi']

    raise FileNotFoundError(f"找不到合约ABI文件: {contract_name}")


def get_vc_manager_config(vc_type: str, config: dict) -> dict:
    """根据VC类型获取对应的VC Manager配置"""
    vc_type_to_key = {
        'InspectionReport': 'InspectionReportVCManager',
        'InsuranceContract': 'InsuranceContractVCManager',
        'CertificateOfOrigin': 'CertificateOfOriginVCManager',
        'BillOfLadingCertificate': 'BillOfLadingVCManager'
    }

    config_key = vc_type_to_key.get(vc_type)
    if not config_key:
        raise ValueError(f"未知的VC类型: {vc_type}")

    vc_managers = config.get('vc_managers', {}).get('chain_a', {})
    if config_key not in vc_managers:
        raise ValueError(f"未找到VC Manager配置: {config_key}")

    vc_manager_info = vc_managers[config_key]

    owner_config = config.get('vc_manager_owner', {})
    if not owner_config:
        raise ValueError("配置文件中缺少vc_manager_owner配置")

    return {
        'vc_manager_address': vc_manager_info.get('address'),
        'vc_manager_did': vc_manager_info.get('did'),
        'vc_manager_name': config_key,
        'abi_file': VC_MANAGERS[vc_type]['abi_file'],
        'caller_address': owner_config.get('address'),
        'caller_private_key': owner_config.get('private_key'),
        'vc_type': vc_type
    }


# ============================================================================
# 核心传输函数
# ============================================================================
def create_random_vc_for_benchmark(
    config: dict,
    vc_issuance_config: dict,
    vc_type: str,
    w3: Web3,
    caller_address: str,
    caller_private_key: str,
    vc_manager_abi: dict,
    auth_config: dict,
    nonce: int = None
) -> Tuple[str, float]:
    """创建随机 VC（不计入传输时间）

    Args:
        nonce: 指定的 nonce 值（用于并发控制），如果为 None 则自动获取

    Returns:
        (vc_hash, creation_time)
    """
    start_time = time.time()

    # 生成随机 VC Hash
    vc_hash_bytes = secrets.token_bytes(32)
    vc_hash = "0x" + vc_hash_bytes.hex()

    # 准备元数据
    timestamp = int(time.time())
    vc_name = f"BenchmarkVC-{timestamp}-{secrets.token_hex(4)}"
    vc_description = f"性能测试VC，自动生成"

    # 从配置获取 DID 信息
    issuer_did = vc_issuance_config.get('acapy', {}).get('issuer', {}).get('did', 'DPvobytTtKvmyeRTJZYjsg')
    holder_did = vc_issuance_config.get('acapy', {}).get('holder', {}).get('did', 'YL2HDxkVL8qMrssaZbvtfH')
    issuer_endpoint = vc_issuance_config.get('acapy', {}).get('issuer', {}).get('endpoint', 'http://localhost:8000')
    holder_endpoint = vc_issuance_config.get('acapy', {}).get('holder', {}).get('endpoint', 'http://localhost:8001')

    chain_a_config = config['chains']['chain_a']
    blockchain_endpoint = chain_a_config['rpc_url']
    blockchain_type = "Hyperledger Besu"
    expiry_time = timestamp + 365 * 24 * 3600

    # 加载 VC Manager 合约
    vc_manager = w3.eth.contract(
        address=Web3.to_checksum_address(auth_config['vc_manager_address']),
        abi=vc_manager_abi
    )

    # 获取 gas 配置
    gas_price = config.get('blockchain', {}).get('gas_price', 1000000000)
    gas_limit = config.get('blockchain', {}).get('gas_limit', 5000000)

    # 使用指定的 nonce 或自动获取
    tx_nonce = nonce if nonce is not None else w3.eth.get_transaction_count(caller_address)

    # 构建 addVCMetadata 交易
    txn = vc_manager.functions.addVCMetadata(
        vc_hash_bytes,
        vc_name,
        vc_description,
        issuer_endpoint,
        issuer_did,
        holder_endpoint,
        holder_did,
        blockchain_endpoint,
        blockchain_type,
        expiry_time
    ).build_transaction({
        'from': caller_address,
        'gas': gas_limit,
        'gasPrice': gas_price,
        'nonce': tx_nonce
    })

    # 签名并发送交易
    signed_txn = w3.eth.account.sign_transaction(txn, caller_private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

    # 等待交易确认
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt['status'] != 1:
        raise Exception(f"addVCMetadata 交易失败! tx_hash: {tx_hash.hex()}")

    creation_time = time.time() - start_time
    return vc_hash, creation_time


def initiate_cross_chain_transfer_for_benchmark(
    config: dict,
    vc_hash: str,
    vc_type: str,
    w3: Web3,
    caller_address: str,
    caller_private_key: str,
    vc_manager_abi: dict,
    auth_config: dict,
    target_chain: str = "chain_b",
    nonce: int = None
) -> Tuple[str, int, float]:
    """发起跨链传输

    Args:
        nonce: 指定的 nonce 值（用于并发控制），如果为 None 则自动获取

    Returns:
        (tx_hash, gas_used, duration)
    """
    start_time = time.time()

    # 加载 VC Manager 合约
    vc_manager = w3.eth.contract(
        address=Web3.to_checksum_address(auth_config['vc_manager_address']),
        abi=vc_manager_abi
    )

    vc_hash_bytes = bytes.fromhex(vc_hash.replace('0x', ''))

    # 获取 gas 配置
    gas_price = config.get('blockchain', {}).get('gas_price', 1000000000)
    gas_limit = config.get('blockchain', {}).get('gas_limit', 5000000)

    # 使用指定的 nonce 或自动获取
    tx_nonce = nonce if nonce is not None else w3.eth.get_transaction_count(caller_address)

    # 构建 initiateCrossChainTransfer 交易
    txn = vc_manager.functions.initiateCrossChainTransfer(
        vc_hash_bytes,
        target_chain
    ).build_transaction({
        'from': caller_address,
        'gas': gas_limit,
        'gasPrice': gas_price,
        'nonce': tx_nonce
    })

    # 签名并发送交易
    signed_txn = w3.eth.account.sign_transaction(txn, caller_private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

    # 等待交易确认
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt['status'] != 1:
        raise Exception(f"initiateCrossChainTransfer 交易失败! tx_hash: {tx_hash.hex()}")

    gas_used = receipt['gasUsed']
    duration = time.time() - start_time

    return tx_hash.hex(), gas_used, duration


def wait_for_cross_chain_transfer_for_benchmark(
    config: dict,
    vc_hash: str,
    w3_b: Web3,
    bridge_abi: dict,
    timeout: int
) -> Tuple[bool, float]:
    """等待跨链传输完成

    Returns:
        (success, duration)
    """
    start_time = time.time()

    chain_b_config = config['chains']['chain_b']
    bridge_b = w3_b.eth.contract(
        address=Web3.to_checksum_address(chain_b_config['bridge_address']),
        abi=bridge_abi
    )

    vc_hash_bytes = bytes.fromhex(vc_hash.replace('0x', ''))

    while time.time() - start_time < timeout:
        try:
            receive_record = bridge_b.functions.receiveList(vc_hash_bytes).call()

            if receive_record and len(receive_record) > 3 and receive_record[3]:
                duration = time.time() - start_time
                return True, duration
        except Exception:
            pass

        time.sleep(1)  # 1秒轮询间隔

    duration = time.time() - start_time
    return False, duration


def execute_single_transfer(
    process_id: int,
    iteration: int,
    config: dict,
    vc_issuance_config: dict,
    vc_type: str,
    timeout: int,
    nonce_add_vc: int = None,
    nonce_initiate: int = None
) -> TransferResult:
    """执行单次完整传输测试

    流程：
    1. 创建随机 VC（不计入时间）
    2. 发起跨链传输（计时开始）
    3. 等待传输完成（计时结束）

    Args:
        nonce_add_vc: addVCMetadata 交易的 nonce
        nonce_initiate: initiateCrossChainTransfer 交易的 nonce
    """
    timestamp = datetime.now().isoformat()

    # 获取配置
    auth_config = get_vc_manager_config(vc_type, config)

    # 连接到 Chain A
    chain_a_config = config['chains']['chain_a']
    w3_a = Web3(Web3.HTTPProvider(chain_a_config['rpc_url']))
    w3_a.middleware_onion.inject(geth_poa_middleware, layer=0)

    # 连接到 Chain B
    chain_b_config = config['chains']['chain_b']
    w3_b = Web3(Web3.HTTPProvider(chain_b_config['rpc_url']))
    w3_b.middleware_onion.inject(geth_poa_middleware, layer=0)

    # 加载 ABI
    vc_manager_abi = load_contract_abi(VC_MANAGERS[vc_type]['abi_file'].replace('.json', ''))
    bridge_abi = load_contract_abi("VCCrossChainBridgeSimple")

    caller_address = Web3.to_checksum_address(auth_config['caller_address'])
    caller_private_key = auth_config['caller_private_key']

    result = TransferResult(
        process_id=process_id,
        iteration=iteration,
        timestamp=timestamp,
        vc_creation_time=0,
        initiate_time=0,
        transfer_time=0,
        total_time=0,
        initiate_gas_used=0,
        success=False,
        error=None,
        vc_hash="",
        tx_hash_initiate=""
    )

    try:
        # 步骤 1: 创建随机 VC（不计入时间）
        vc_hash, vc_creation_time = create_random_vc_for_benchmark(
            config, vc_issuance_config, vc_type,
            w3_a, caller_address, caller_private_key,
            vc_manager_abi, auth_config,
            nonce=nonce_add_vc
        )
        result.vc_hash = vc_hash
        result.vc_creation_time = vc_creation_time

        # 步骤 2: 发起跨链传输（计时开始）
        tx_hash, gas_used, initiate_time = initiate_cross_chain_transfer_for_benchmark(
            config, vc_hash, vc_type,
            w3_a, caller_address, caller_private_key,
            vc_manager_abi, auth_config,
            nonce=nonce_initiate
        )
        result.tx_hash_initiate = tx_hash
        result.initiate_gas_used = gas_used
        result.initiate_time = initiate_time

        # 步骤 3: 等待传输完成
        success, transfer_time = wait_for_cross_chain_transfer_for_benchmark(
            config, vc_hash, w3_b, bridge_abi, timeout
        )
        result.transfer_time = transfer_time
        result.total_time = initiate_time + transfer_time
        result.success = success

        if not success:
            result.error = "传输超时"

    except Exception as e:
        result.error = str(e)
        result.success = False

    return result


# ============================================================================
# 进程工作函数
# ============================================================================
def worker_process(
    process_id: int,
    iterations: int,
    config: dict,
    vc_issuance_config: dict,
    vc_type: str,
    timeout: int,
    result_queue: multiprocessing.Queue,
    shared_nonce: multiprocessing.Value,
    nonce_lock: multiprocessing.Lock
) -> List[Dict]:
    """单个进程的工作循环

    Args:
        shared_nonce: 共享的 nonce 计数器
        nonce_lock: nonce 锁，用于保护 nonce 的获取和递增
    """
    results = []

    for i in range(iterations):
        # 获取两个 nonce（addVCMetadata + initiateCrossChainTransfer）
        with nonce_lock:
            nonce_add_vc = shared_nonce.value
            shared_nonce.value += 1
            nonce_initiate = shared_nonce.value
            shared_nonce.value += 1

        result = execute_single_transfer(
            process_id=process_id,
            iteration=i,
            config=config,
            vc_issuance_config=vc_issuance_config,
            vc_type=vc_type,
            timeout=timeout,
            nonce_add_vc=nonce_add_vc,
            nonce_initiate=nonce_initiate
        )

        results.append(asdict(result))
        result_queue.put(asdict(result))

    return results


# ============================================================================
# 统计收集器
# ============================================================================
class BenchmarkStatsCollector:
    """收集和计算统计数据"""

    def __init__(self):
        self.results: List[TransferResult] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    def add_result(self, result: Dict):
        """添加单个结果"""
        if self.start_time is None:
            self.start_time = datetime.fromisoformat(result["timestamp"])
        self.results.append(result)
        self.end_time = datetime.fromisoformat(result["timestamp"])

    def calculate_process_stats(self, process_id: int) -> ProcessStats:
        """计算单个进程的统计"""
        process_results = [r for r in self.results if r['process_id'] == process_id]

        if not process_results:
            return ProcessStats(
                process_id=process_id,
                total_transfers=0,
                successful_transfers=0,
                failed_transfers=0,
                min_time=0,
                max_time=0,
                avg_time=0,
                times=[],
                gas_list=[],
                total_gas=0,
                avg_gas=0,
                throughput=0
            )

        successful = [r for r in process_results if r['success']]
        times = [r['total_time'] for r in successful] if successful else []
        gas_list = [r['initiate_gas_used'] for r in successful] if successful else []

        # 计算进程持续时间
        timestamps = [datetime.fromisoformat(r['timestamp']) for r in process_results]
        if len(timestamps) >= 2:
            process_duration = (max(timestamps) - min(timestamps)).total_seconds()
        else:
            process_duration = times[0] if times else 0

        return ProcessStats(
            process_id=process_id,
            total_transfers=len(process_results),
            successful_transfers=len(successful),
            failed_transfers=len(process_results) - len(successful),
            min_time=min(times) if times else 0,
            max_time=max(times) if times else 0,
            avg_time=statistics.mean(times) if times else 0,
            times=times,
            gas_list=gas_list,
            total_gas=sum(gas_list) if gas_list else 0,
            avg_gas=statistics.mean(gas_list) if gas_list else 0,
            throughput=len(successful) / process_duration if process_duration > 0 else 0,
            start_time=min(timestamps).isoformat() if timestamps else None,
            end_time=max(timestamps).isoformat() if timestamps else None
        )

    def calculate_global_stats(self) -> GlobalStats:
        """计算全局统计"""
        if not self.results:
            return GlobalStats(
                total_transfers=0,
                successful_transfers=0,
                failed_transfers=0,
                success_rate=0,
                min_time=0,
                max_time=0,
                avg_time=0,
                variance=0,
                std_dev=0,
                median=0,
                p50=0,
                p75=0,
                p90=0,
                p95=0,
                p99=0,
                total_gas=0,
                avg_gas=0,
                throughput=0,
                total_duration=0
            )

        successful = [r for r in self.results if r['success']]
        times = [r['total_time'] for r in successful] if successful else []
        gas_list = [r['initiate_gas_used'] for r in successful] if successful else []

        # 计算总持续时间
        total_duration = 0
        if self.start_time and self.end_time:
            total_duration = (self.end_time - self.start_time).total_seconds()

        # 计算百分位数
        def calc_percentile(data: List[float], p: int) -> float:
            if not data:
                return 0
            if len(data) == 1:
                return data[0]
            sorted_data = sorted(data)
            n = len(sorted_data)
            idx = (p / 100) * (n - 1)
            lower = int(idx)
            upper = lower + 1
            if upper >= n:
                return sorted_data[-1]
            weight = idx - lower
            return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight

        return GlobalStats(
            total_transfers=len(self.results),
            successful_transfers=len(successful),
            failed_transfers=len(self.results) - len(successful),
            success_rate=len(successful) / len(self.results) * 100 if self.results else 0,
            min_time=min(times) if times else 0,
            max_time=max(times) if times else 0,
            avg_time=statistics.mean(times) if times else 0,
            variance=statistics.variance(times) if len(times) >= 2 else 0,
            std_dev=statistics.stdev(times) if len(times) >= 2 else 0,
            median=statistics.median(times) if times else 0,
            p50=calc_percentile(times, 50),
            p75=calc_percentile(times, 75),
            p90=calc_percentile(times, 90),
            p95=calc_percentile(times, 95),
            p99=calc_percentile(times, 99),
            total_gas=sum(gas_list) if gas_list else 0,
            avg_gas=statistics.mean(gas_list) if gas_list else 0,
            throughput=len(successful) / total_duration if total_duration > 0 else 0,
            total_duration=total_duration
        )


# ============================================================================
# 终端输出类
# ============================================================================
class BenchmarkOutput:
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
        print(f"\n{Colors.BOLD}测试配置:{Colors.END}")
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
        if result.get("success"):
            status = f"{Colors.GREEN}✓{Colors.END} 成功"
        else:
            status = f"{Colors.RED}✗{Colors.END} 失败"

        duration_str = f"{result.get('total_time', 0):.2f}s"
        process_id = result.get('process_id', '?')
        iteration = result.get('iteration', '?')

        if show_bar:
            line = f"\r[{current}/{total}] P{process_id}-I{iteration} {status} ({duration_str}) [{Colors.CYAN}{bar}{Colors.END}] {percent}%"
        else:
            line = f"\r[{current}/{total}] P{process_id}-I{iteration} {status} ({duration_str})"

        self.last_progress_len = len(Colors.strip(line)) + 5
        sys.stdout.write(line)
        sys.stdout.flush()

    def print_process_stats(self, process_stats: ProcessStats):
        """打印进程统计"""
        self._clear_progress()

        pid = process_stats.process_id
        success = process_stats.successful_transfers
        total = process_stats.total_transfers
        failed = process_stats.failed_transfers

        print(f"\n{Colors.BOLD}进程 {pid} 统计:{Colors.END}")
        print(f"  传输数: {total} | 成功: {Colors.GREEN}{success}{Colors.END} | 失败: {Colors.RED}{failed}{Colors.END}")
        if process_stats.times:
            print(f"  时间: 最小 {Colors.GREEN}{process_stats.min_time:.2f}s{Colors.END} | "
                  f"最大 {Colors.YELLOW}{process_stats.max_time:.2f}s{Colors.END} | "
                  f"平均 {Colors.GREEN}{process_stats.avg_time:.2f}s{Colors.END}")
            print(f"  Gas: 总计 {process_stats.total_gas} | 平均 {process_stats.avg_gas:.0f}")
            print(f"  吞吐量: {Colors.GREEN}{process_stats.throughput:.4f}{Colors.END} transfers/s")

    def print_global_stats(self, stats: GlobalStats):
        """打印全局统计"""
        self._clear_progress()
        print()

        # 总体统计
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}  全局统计汇总{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")

        print(f"\n{Colors.BOLD}总体:{Colors.END}")
        print(f"  总传输数: {stats.total_transfers}")
        print(f"  成功: {Colors.GREEN}{stats.successful_transfers}{Colors.END} ({stats.success_rate:.1f}%)")
        print(f"  失败: {Colors.RED}{stats.failed_transfers}{Colors.END}")

        # 时间统计
        print(f"\n{Colors.BOLD}时间统计 (秒):{Colors.END}")
        print(f"  最小: {Colors.GREEN}{stats.min_time:.2f}{Colors.END}    "
              f"最大: {Colors.YELLOW}{stats.max_time:.2f}{Colors.END}    "
              f"平均: {Colors.GREEN}{stats.avg_time:.2f}{Colors.END}")
        print(f"  方差: {stats.variance:.4f}    标准差: {stats.std_dev:.4f}")
        print(f"  P50: {stats.p50:.2f}    P75: {stats.p75:.2f}    P90: {stats.p90:.2f}")
        print(f"  P95: {Colors.YELLOW}{stats.p95:.2f}{Colors.END}    P99: {Colors.YELLOW}{stats.p99:.2f}{Colors.END}")

        # Gas 统计
        print(f"\n{Colors.BOLD}Gas 统计:{Colors.END}")
        print(f"  总消耗: {stats.total_gas}    平均: {stats.avg_gas:.0f}")

        # 吞吐量
        print(f"\n{Colors.BOLD}吞吐量:{Colors.END}")
        print(f"  {Colors.GREEN}{stats.throughput:.4f}{Colors.END} transfers/second")
        print(f"  总耗时: {stats.total_duration:.2f} 秒")

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
    output: BenchmarkOutput,
    interrupt_flag: InterruptFlag,
    collector: BenchmarkStatsCollector
):
    """监控队列并显示进度"""
    received = 0

    while received < total_expected and not interrupt_flag.is_set():
        try:
            result = result_queue.get(timeout=0.1)
            received += 1
            collector.add_result(result)
            output.print_progress(received, total_expected, result)
        except queue.Empty:
            continue

    if received > 0:
        output.print_progress(received, total_expected, {"success": True})


# ============================================================================
# 结果导出
# ============================================================================
def export_results(
    collector: BenchmarkStatsCollector,
    global_stats: GlobalStats,
    process_stats_list: List[ProcessStats],
    output_path: str,
    config_info: Dict
):
    """导出结果到JSON文件"""
    export_data = {
        "timestamp": datetime.now().isoformat(),
        "config": config_info,
        "global_statistics": asdict(global_stats),
        "process_statistics": [asdict(ps) for ps in process_stats_list],
        "raw_results": collector.results
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)


# ============================================================================
# 主函数
# ============================================================================
def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="VC 跨链传输性能分析程序",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基础测试: 2个进程，每进程3次传输
  python3 oracle/vc_transfer_benchmark.py -p 2 -i 3

  # 标准测试: 4个进程，每进程5次传输
  python3 oracle/vc_transfer_benchmark.py -p 4 -i 5

  # 压力测试: 8个进程，每进程10次传输，导出结果
  python3 oracle/vc_transfer_benchmark.py -p 8 -i 10 -o benchmark_results.json

  # 安静模式
  python3 oracle/vc_transfer_benchmark.py -p 4 -i 5 -q
        """
    )

    parser.add_argument(
        '-p', '--processes',
        type=int,
        default=4,
        help='并发进程数量 (默认: 4)'
    )

    parser.add_argument(
        '-i', '--iterations',
        type=int,
        default=5,
        help='每个进程的传输次数 (默认: 5)'
    )

    parser.add_argument(
        '--vc-type',
        type=str,
        default='InspectionReport',
        choices=['InspectionReport', 'InsuranceContract', 'CertificateOfOrigin', 'BillOfLadingCertificate'],
        help='VC 类型 (默认: InspectionReport)'
    )

    parser.add_argument(
        '-t', '--timeout',
        type=int,
        default=120,
        help='单次传输超时时间，秒 (默认: 120)'
    )

    parser.add_argument(
        '-c', '--config',
        type=str,
        default=None,
        help='配置文件路径'
    )

    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='结果输出文件路径 (JSON 格式)'
    )

    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='安静模式'
    )

    args = parser.parse_args()

    # 加载配置
    config = load_config()
    vc_issuance_config = load_vc_issuance_config()

    # 初始化输出
    output = BenchmarkOutput(quiet=args.quiet)

    # 打印标题
    output.print_header("VC 跨链传输性能分析")

    total_transfers = args.processes * args.iterations

    # 打印配置
    config_info = {
        "进程数量": args.processes,
        "每进程传输次数": args.iterations,
        "总传输数": total_transfers,
        "VC类型": args.vc_type,
        "传输超时": f"{args.timeout}秒"
    }
    output.print_config(config_info)

    # 确认继续（对于大量请求）
    if total_transfers > 20 and not args.quiet:
        try:
            response = input(f"\n{Colors.YELLOW}即将执行 {total_transfers} 次跨链传输，按 Enter 继续...{Colors.END}")
            if response.lower() in ['q', 'quit', 'exit', 'n', 'no']:
                print("测试已取消")
                return 0
        except EOFError:
            pass

    # 获取当前 nonce 并创建共享 nonce 计数器
    auth_config = get_vc_manager_config(args.vc_type, config)
    chain_a_config = config['chains']['chain_a']
    w3_a = Web3(Web3.HTTPProvider(chain_a_config['rpc_url']))
    w3_a.middleware_onion.inject(geth_poa_middleware, layer=0)

    caller_address = Web3.to_checksum_address(auth_config['caller_address'])
    current_nonce = w3_a.eth.get_transaction_count(caller_address)

    # 创建共享 nonce 计数器和锁
    shared_nonce = multiprocessing.Value('i', current_nonce)
    nonce_lock = multiprocessing.Lock()

    output.print(f"\n{Colors.BOLD}Nonce 管理:{Colors.END}")
    output.print(f"  当前 nonce: {current_nonce}")
    output.print(f"  预期总 nonce 消耗: {total_transfers * 2}")

    # 初始化
    interrupt_flag = InterruptFlag()
    collector = BenchmarkStatsCollector()
    result_queue = multiprocessing.Queue()

    # 设置信号处理
    original_handler = signal.getsignal(signal.SIGINT)

    def signal_handler(sig, frame):
        output.print_warning("\n接收到中断信号，正在停止...")
        interrupt_flag.set()
        time.sleep(0.5)
        sys.exit(130)

    signal.signal(signal.SIGINT, signal_handler)

    # 启动时间
    test_start_time = time.time()

    # 创建并启动进程池
    processes = []
    output.print(f"\n{Colors.BOLD}启动性能测试...{Colors.END}")

    try:
        # 启动进度监控线程
        import threading
        monitor_thread = None
        if not args.quiet:
            monitor_thread = threading.Thread(
                target=progress_monitor,
                args=(result_queue, total_transfers, output, interrupt_flag, collector),
                daemon=True
            )
            monitor_thread.start()

        # 启动工作进程
        for process_id in range(args.processes):
            p = multiprocessing.Process(
                target=worker_process,
                args=(
                    process_id,
                    args.iterations,
                    config,
                    vc_issuance_config,
                    args.vc_type,
                    args.timeout,
                    result_queue,
                    shared_nonce,
                    nonce_lock
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

    # 计算统计
    global_stats = collector.calculate_global_stats()

    # 获取所有进程 ID
    process_ids = set(r['process_id'] for r in collector.results)
    process_stats_list = [collector.calculate_process_stats(pid) for pid in sorted(process_ids)]

    # 打印进程统计
    output.print_header("进程统计")
    for ps in process_stats_list:
        output.print_process_stats(ps)

    # 打印全局统计
    output.print_global_stats(global_stats)

    # 导出结果
    if args.output:
        export_results(collector, global_stats, process_stats_list, args.output, config_info)
        output.print_success(f"结果已导出到: {args.output}")

    # 完成
    output.print_header("测试完成")

    return 0


if __name__ == "__main__":
    sys.exit(main())
