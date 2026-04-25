#!/usr/bin/env python3
"""
VP验证Oracle服务测试脚本
测试各个API端点
"""

import json
import requests
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List


# 默认配置
ORACLE_URL = "http://localhost:7002"
UUID_JSON_PATH = Path(__file__).parent / "logs" / "uuid.json"


def print_section(title: str):
    """打印分节标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_response(response: requests.Response):
    """打印响应信息"""
    print(f"状态码: {response.status_code}")
    try:
        data = response.json()
        print(f"响应:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except:
        print(f"响应: {response.text}")


def load_uuid_data() -> Dict:
    """加载uuid.json数据"""
    try:
        if UUID_JSON_PATH.exists():
            with open(UUID_JSON_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"警告: 无法加载uuid.json: {e}")
        return {}


def get_latest_vc_hash(vc_type: str = "InspectionReport") -> Optional[str]:
    """
    获取指定VC类型的最新vc_hash

    参数:
        vc_type: VC类型（默认InspectionReport）

    返回:
        最新的vc_hash，如果找不到返回None
    """
    uuid_data = load_uuid_data()
    if not uuid_data:
        return None

    # 按时间戳排序，获取最新的
    matching_vcs = []
    for uuid_val, data in uuid_data.items():
        if data.get('vc_type') == vc_type:
            matching_vcs.append((uuid_val, data))

    if not matching_vcs:
        return None

    # 按时间戳排序，获取最新的
    matching_vcs.sort(key=lambda x: x[1].get('timestamp', ''), reverse=True)
    latest = matching_vcs[0][1]

    print(f"找到最新的 {vc_type} VC:")
    print(f"  UUID: {matching_vcs[0][0]}")
    print(f"  vc_hash: {latest.get('vc_hash')}")
    print(f"  contractName: {latest.get('original_contract_name')}")
    print(f"  timestamp: {latest.get('timestamp')}")

    return latest.get('vc_hash')


def test_health(oracle_url: str = ORACLE_URL) -> bool:
    """测试健康检查"""
    print_section("健康检查")

    try:
        response = requests.get(f"{oracle_url}/api/health", timeout=10)
        print_response(response)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"❌ 连接失败: {e}")
        return False


def test_get_vc_types(oracle_url: str = ORACLE_URL) -> bool:
    """测试获取支持的VC类型"""
    print_section("获取支持的VC类型")

    try:
        response = requests.get(f"{oracle_url}/api/vc-types", timeout=10)
        print_response(response)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_get_vc_attributes(vc_type: str = "InspectionReport",
                           oracle_url: str = ORACLE_URL) -> bool:
    """测试获取VC属性"""
    print_section(f"获取 {vc_type} 的属性列表")

    try:
        response = requests.get(
            f"{oracle_url}/api/vc-types/{vc_type}/attributes",
            timeout=10
        )
        print_response(response)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_get_vc_info(vc_type: str = "InspectionReport",
                     oracle_url: str = ORACLE_URL) -> bool:
    """测试获取VC信息"""
    print_section(f"获取 {vc_type} 的配置信息")

    try:
        response = requests.get(
            f"{oracle_url}/api/vc-types/{vc_type}/info",
            timeout=10
        )
        print_response(response)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_verify_vc(vc_type: str = "InspectionReport",
                   vc_hash: Optional[str] = None,
                   attributes: Optional[list] = None,
                   oracle_url: str = ORACLE_URL) -> bool:
    """测试VC验证"""
    print_section("执行VC验证")

    # 如果没有提供vc_hash，从uuid.json获取最新的
    if vc_hash is None:
        print(f"未提供vc_hash，从uuid.json获取最新的 {vc_type} VC...")
        vc_hash = get_latest_vc_hash(vc_type)
        if not vc_hash:
            print(f"⚠️  未找到 {vc_type} 类型的VC，使用测试哈希")
            vc_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

    if attributes is None:
        attributes = ["exporter", "inspectionPassed", "contractName"]

    verify_request = {
        "vc_type": vc_type,
        "vc_hash": vc_hash,
        "requested_attributes": attributes
    }

    print(f"请求:")
    print(json.dumps(verify_request, indent=2, ensure_ascii=False))

    try:
        print(f"\n⏳ 发送验证请求（可能需要最多120秒）...")
        response = requests.post(
            f"{oracle_url}/api/verify",
            json=verify_request,
            timeout=150
        )

        print(f"\n响应:")
        print_response(response)
        return response.status_code == 200

    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_verify_vc_error_handling(oracle_url: str = ORACLE_URL):
    """测试错误处理"""
    print_section("错误处理测试")

    # 测试缺少vc_type
    print("\n1. 测试缺少vc_type:")
    response = requests.post(
        f"{oracle_url}/api/verify",
        json={"vc_hash": "0x" + "0" * 64, "requested_attributes": []},
        timeout=10
    )
    print(f"   状态码: {response.status_code} (期望: 400)")
    print(f"   响应: {response.json()}")

    # 测试缺少vc_hash
    print("\n2. 测试缺少vc_hash:")
    response = requests.post(
        f"{oracle_url}/api/verify",
        json={"vc_type": "InspectionReport", "requested_attributes": []},
        timeout=10
    )
    print(f"   状态码: {response.status_code} (期望: 400)")
    print(f"   响应: {response.json()}")

    # 测试无效的vc_hash格式
    print("\n3. 测试无效的vc_hash格式:")
    response = requests.post(
        f"{oracle_url}/api/verify",
        json={
            "vc_type": "InspectionReport",
            "vc_hash": "invalid_hash",
            "requested_attributes": []
        },
        timeout=10
    )
    print(f"   状态码: {response.status_code} (期望: 400)")
    print(f"   响应: {response.json()}")

    # 测试不支持的VC类型
    print("\n4. 测试不支持的VC类型:")
    response = requests.post(
        f"{oracle_url}/api/verify",
        json={
            "vc_type": "UnsupportedType",
            "vc_hash": "0x" + "0" * 64,
            "requested_attributes": []
        },
        timeout=10
    )
    print(f"   状态码: {response.status_code} (期望: 400)")
    print(f"   响应: {response.json()}")


def main():
    """主测试流程"""
    import argparse

    parser = argparse.ArgumentParser(description="VP验证Oracle服务测试脚本")
    parser.add_argument(
        '--url',
        default=ORACLE_URL,
        help=f'Oracle服务URL (默认: {ORACLE_URL})'
    )
    parser.add_argument(
        '--vc-type',
        default='InspectionReport',
        help='VC类型 (默认: InspectionReport)'
    )
    parser.add_argument(
        '--vc-hash',
        help='VC哈希 (66位十六进制)。如果不提供，将从uuid.json获取最新的VC'
    )
    parser.add_argument(
        '--attributes',
        nargs='+',
        default=['exporter', 'inspectionPassed', 'contractName'],
        help='请求的属性列表'
    )
    parser.add_argument(
        '--skip-verify',
        action='store_true',
        help='跳过验证测试（仅测试基础端点）'
    )
    parser.add_argument(
        '--test-errors',
        action='store_true',
        help='测试错误处理'
    )
    parser.add_argument(
        '--list-vc',
        action='store_true',
        help='列出uuid.json中的所有VC'
    )

    args = parser.parse_args()

    print(f"VP验证Oracle服务测试")
    print(f"目标地址: {args.url}")
    print(f"VC类型: {args.vc_type}")

    # 列出所有VC
    if args.list_vc:
        print_section("uuid.json中的VC列表")
        uuid_data = load_uuid_data()
        if not uuid_data:
            print("uuid.json为空或不存在")
            return

        # 按类型分组
        by_type = {}
        for uuid_val, data in uuid_data.items():
            vc_type = data.get('vc_type', 'Unknown')
            if vc_type not in by_type:
                by_type[vc_type] = []
            by_type[vc_type].append((uuid_val, data))

        for vc_type, vcs in sorted(by_type.items()):
            print(f"\n{vc_type}:")
            # 按时间戳排序
            vcs.sort(key=lambda x: x[1].get('timestamp', ''), reverse=True)
            for uuid_val, data in vcs[:5]:  # 只显示最新的5个
                print(f"  - {uuid_val}")
                print(f"    vc_hash: {data.get('vc_hash')}")
                print(f"    contractName: {data.get('original_contract_name')}")
                print(f"    timestamp: {data.get('timestamp')}")
            if len(vcs) > 5:
                print(f"  ... 还有 {len(vcs) - 5} 个")
        return

    # 测试健康检查
    if not test_health(args.url):
        print("\n❌ 健康检查失败，服务可能未启动")
        print(f"\n请先启动服务:")
        print(f"  bash /home/manifold/cursor/cross-chain-new/oracle/start_vp_oracle.sh")
        sys.exit(1)

    print("✅ 健康检查通过")

    # 测试获取VC类型
    if not test_get_vc_types(args.url):
        print("❌ 获取VC类型失败")
        sys.exit(1)

    print("✅ 获取VC类型成功")

    # 测试获取VC属性
    if not test_get_vc_attributes(args.vc_type, args.url):
        print("❌ 获取VC属性失败")
        sys.exit(1)

    print("✅ 获取VC属性成功")

    # 测试获取VC信息
    if not test_get_vc_info(args.vc_type, args.url):
        print("⚠️  获取VC信息失败（非关键）")

    # 测试错误处理
    if args.test_errors:
        test_verify_vc_error_handling(args.url)

    # 测试VC验证
    if not args.skip_verify:
        print_section("VC验证测试")
        print("⚠️  注意: 此测试需要Holder ACA-Py正在运行并持有对应的VC")
        print("⚠️  如果Holder没有VC，验证将失败")

        test_verify_vc(
            vc_type=args.vc_type,
            vc_hash=args.vc_hash,  # None时自动从uuid.json获取
            attributes=args.attributes,
            oracle_url=args.url
        )

    print_section("测试完成")
    print("✅ 所有基础测试通过")


if __name__ == "__main__":
    main()
