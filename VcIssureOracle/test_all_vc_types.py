#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VP验证测试脚本 - 测试所有4种VC类型
对每种类型的VC进行一次验证，并计算总时间和各项统计
"""

import json
import requests
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List


# 颜色类
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


# 默认配置
ORACLE_URL = "http://localhost:7002"
UUID_JSON_PATH = Path(__file__).parent / "logs" / "uuid.json"
CONFIG_JSON_PATH = Path(__file__).parent / "vc_issuance_config.json"

# 4种VC类型及其默认请求属性
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


def print_header(title: str):
    """打印分节标题"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {title}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")


def print_success(msg: str):
    """打印成功消息"""
    print(f"{Colors.GREEN}✓{Colors.END} {msg}")


def print_error(msg: str):
    """打印错误消息"""
    print(f"{Colors.RED}✗{Colors.END} {msg}")


def print_info(msg: str):
    """打印信息"""
    print(f"{Colors.CYAN}ℹ{Colors.END} {msg}")


def print_warning(msg: str):
    """打印警告"""
    print(f"{Colors.YELLOW}⚠{Colors.END} {msg}")


def load_uuid_data() -> Dict:
    """加载uuid.json数据"""
    try:
        if UUID_JSON_PATH.exists():
            with open(UUID_JSON_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print_error(f"无法加载uuid.json: {e}")
        return {}


def load_config() -> Dict:
    """加载配置文件"""
    try:
        if CONFIG_JSON_PATH.exists():
            with open(CONFIG_JSON_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print_warning(f"无法加载配置文件: {e}")
        return {}


def get_latest_vc_hash(uuid_data: Dict, vc_type: str) -> Optional[str]:
    """
    获取指定VC类型的最新vc_hash

    参数:
        uuid_data: uuid数据字典
        vc_type: VC类型

    返回:
        最新的vc_hash，如果找不到返回None
    """
    matching_vcs = []
    for uuid_val, data in uuid_data.items():
        if data.get('vc_type') == vc_type:
            matching_vcs.append((uuid_val, data))

    if not matching_vcs:
        return None

    # 按时间戳排序，获取最新的
    matching_vcs.sort(key=lambda x: x[1].get('timestamp', ''), reverse=True)
    latest = matching_vcs[0][1]

    print_info(f"找到 {vc_type}:")
    print(f"    vc_hash: {latest.get('vc_hash')}")
    print(f"    contractName: {latest.get('original_contract_name')}")
    print(f"    timestamp: {latest.get('timestamp')}")

    return latest.get('vc_hash')


def verify_vc_type(
    vc_type: str,
    vc_hash: str,
    attributes: List[str],
    oracle_url: str,
    timeout: int = 150
) -> Dict:
    """
    执行单次VC验证

    参数:
        vc_type: VC类型
        vc_hash: VC哈希
        attributes: 请求的属性列表
        oracle_url: Oracle服务URL
        timeout: 超时时间

    返回:
        验证结果字典
    """
    result = {
        "vc_type": vc_type,
        "success": False,
        "verified": False,
        "duration": 0,
        "error": None,
        "revealed_attrs": None,
        "uuid": None
    }

    verify_request = {
        "vc_type": vc_type,
        "vc_hash": vc_hash,
        "requested_attributes": attributes
    }

    print(f"\n{Colors.BOLD}请求:{Colors.END}")
    print(json.dumps(verify_request, indent=2, ensure_ascii=False))

    try:
        print_info(f"发送验证请求...")
        start_time = time.time()

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
            result["revealed_attrs"] = data.get("revealed_attributes")
            result["uuid"] = data.get("uuid")

            print(f"\n{Colors.BOLD}响应:{Colors.END}")
            print(json.dumps(data, indent=2, ensure_ascii=False))

            if result["verified"]:
                print_success(f"验证成功! 耗时: {elapsed:.2f}秒")
            else:
                print_warning(f"请求成功但验证未通过 (耗时: {elapsed:.2f}秒)")
        else:
            result["error"] = f"HTTP {response.status_code}"
            print_error(f"请求失败: HTTP {response.status_code}")
            print(f"响应: {response.text}")

    except requests.exceptions.Timeout:
        result["duration"] = timeout
        result["error"] = "Timeout"
        print_error(f"请求超时 (超过{timeout}秒)")

    except requests.exceptions.RequestException as e:
        result["error"] = str(e)
        print_error(f"请求异常: {e}")

    return result


def test_health(oracle_url: str) -> bool:
    """测试健康检查"""
    try:
        response = requests.get(f"{oracle_url}/api/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_success(f"服务健康检查通过")
            print(f"    服务: {data.get('service')}")
            print(f"    状态: {data.get('status')}")
            print(f"    版本: {data.get('version')}")
            return True
        return False
    except requests.exceptions.RequestException as e:
        print_error(f"健康检查失败: {e}")
        return False


def print_summary(results: List[Dict], total_time: float):
    """打印测试摘要"""
    print_header("测试摘要")

    # 统计
    total = len(results)
    successful = sum(1 for r in results if r["success"])
    verified = sum(1 for r in results if r["verified"])

    print(f"\n{Colors.BOLD}总体统计:{Colors.END}")
    print(f"  总测试数:      {total}")
    print(f"  请求成功:      {Colors.GREEN}{successful}{Colors.END} ({successful/total*100:.1f}%)")
    print(f"  验证成功:      {Colors.GREEN}{verified}{Colors.END} ({verified/total*100:.1f}%)")
    print(f"  请求失败:      {Colors.RED}{total - successful}{Colors.END}")

    # 时间统计
    durations = [r["duration"] for r in results if r["success"]]
    if durations:
        print(f"\n{Colors.BOLD}时间统计:{Colors.END}")
        print(f"  总耗时:        {Colors.GREEN}{total_time:.2f}s{Colors.END}")
        print(f"  平均耗时:      {Colors.GREEN}{sum(durations)/len(durations):.2f}s{Colors.END}")
        print(f"  最快:          {min(durations):.2f}s")
        print(f"  最慢:          {max(durations):.2f}s")

    # 详细结果
    print(f"\n{Colors.BOLD}详细结果:{Colors.END}")
    for r in results:
        status_color = Colors.GREEN if r["verified"] else (Colors.YELLOW if r["success"] else Colors.RED)
        status = "✓ Verified" if r["verified"] else ("○ Unverified" if r["success"] else "✗ Failed")
        print(f"  {r['vc_type']:25s} {status_color}{status}{Colors.END} ({r['duration']:.2f}s)")
        if r.get("error"):
            print(f"    错误: {r['error']}")


def main():
    """主测试流程"""
    import argparse

    parser = argparse.ArgumentParser(
        description="VP验证测试 - 测试所有4种VC类型",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 测试所有4种VC类型
  python3 test_all_vc_types.py

  # 指定Oracle URL
  python3 test_all_vc_types.py --url http://localhost:7002

  # 导出结果
  python3 test_all_vc_types.py --output results.json
        """
    )

    parser.add_argument(
        '--url',
        default=ORACLE_URL,
        help=f'Oracle服务URL (默认: {ORACLE_URL})'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=150,
        help='请求超时时间（秒）(默认: 150)'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='结果输出文件 (JSON格式)'
    )

    parser.add_argument(
        '--vc-hash',
        action='append',
        nargs=2,
        metavar=('TYPE', 'HASH'),
        help='指定VC类型的哈希 (可多次使用: --vc-hash InspectionReport 0x123...)'
    )

    parser.add_argument(
        '--interval', '-t',
        type=float,
        default=3.0,
        help='每个验证请求之间的间隔秒数（默认: 3.0）'
    )

    args = parser.parse_args()

    print_header("VP验证测试 - 所有4种VC类型")
    print(f"目标地址: {args.url}")
    print(f"超时时间: {args.timeout}秒")

    # 健康检查
    print(f"\n{Colors.BOLD}[1/3]{Colors.END} 健康检查")
    if not test_health(args.url):
        print_error("健康检查失败，服务可能未启动")
        print(f"\n请先启动服务:")
        print(f"  bash /home/manifold/cursor/cross-chain-new/oracle/start_vp_oracle.sh")
        sys.exit(1)

    # 加载数据
    print(f"\n{Colors.BOLD}[2/3]{Colors.END} 加载测试数据")
    uuid_data = load_uuid_data()
    config_data = load_config()

    if not uuid_data:
        print_error("无法加载uuid.json，没有可用的VC进行测试")
        sys.exit(1)

    # 准备测试
    results = []
    test_start_time = time.time()

    print(f"\n{Colors.BOLD}[3/3]{Colors.END} 执行验证测试")

    # 处理手动指定的哈希
    manual_hashes = {}
    if args.vc_hash:
        for vc_type, vc_hash in args.vc_hash:
            manual_hashes[vc_type] = vc_hash

    # 对每种VC类型进行测试
    vc_type_list = list(VC_TYPES_CONFIG.items())
    for i, (vc_type, config) in enumerate(vc_type_list):
        # 第一个请求之后，添加间隔
        if i > 0 and args.interval > 0:
            print_info(f"等待 {args.interval} 秒后处理下一个请求...")
            time.sleep(args.interval)

        print_header(f"测试: {vc_type}")

        # 获取VC哈希
        if vc_type in manual_hashes:
            vc_hash = manual_hashes[vc_type]
            print_info(f"使用手动指定的哈希")
        else:
            vc_hash = get_latest_vc_hash(uuid_data, vc_type)

        if not vc_hash:
            print_warning(f"未找到 {vc_type} 类型的VC，跳过")
            results.append({
                "vc_type": vc_type,
                "success": False,
                "verified": False,
                "duration": 0,
                "error": "未找到VC"
            })
            continue

        # 执行验证
        result = verify_vc_type(
            vc_type=vc_type,
            vc_hash=vc_hash,
            attributes=config["attributes"],
            oracle_url=args.url,
            timeout=args.timeout
        )
        results.append(result)

    # 计算总时间
    total_time = time.time() - test_start_time

    # 打印摘要
    print_summary(results, total_time)

    # 导出结果
    if args.output:
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "oracle_url": args.url,
            "total_time": total_time,
            "results": results
        }
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        print_success(f"\n结果已导出到: {args.output}")

    # 完成提示
    print_header("测试完成")

    # 返回码：全部验证成功返回0，否则返回1
    all_verified = all(r["verified"] for r in results if r["success"])
    sys.exit(0 if all_verified else 1)


if __name__ == "__main__":
    main()
