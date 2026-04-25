#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从JSON配置文件读取测试数据并发送到VC发行Oracle服务

使用方法:
    python3 test_vc_issuance_from_json.py                    # 使用默认测试用例
    python3 test_vc_issuance_from_json.py --test full_test   # 指定测试用例
    python3 test_vc_issuance_from_json.py --list             # 列出所有测试用例
    python3 test_vc_issuance_from_json.py --all              # 运行所有测试用例
    python3 test_vc_issuance_from_json.py --verify           # 只验证不创建新VC
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, Optional

import requests


# ACA-Py Admin端点配置
ISSUER_ADMIN_URL = "http://localhost:8080"
HOLDER_ADMIN_URL = "http://localhost:8081"


def load_test_data() -> Dict:
    """加载测试数据配置文件"""
    config_path = Path(__file__).parent / "vc_issuance_test_data.json"

    if not config_path.exists():
        print(f"错误: 测试数据文件不存在: {config_path}")
        sys.exit(1)

    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_oracle_health(endpoint: str) -> bool:
    """检查Oracle服务健康状态"""
    try:
        resp = requests.get(f"{endpoint}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"Oracle服务状态: {data.get('status', 'unknown')}")
            print(f"  - ACA-Py Issuer: {data.get('connections', {}).get('acapy_issuer', 'unknown')}")
            print(f"  - ACA-Py Holder: {data.get('connections', {}).get('acapy_holder', 'unknown')}")
            print(f"  - Web3: {data.get('connections', {}).get('web3', 'unknown')}")
            return data.get('status') in ['ok', 'degraded']
        return False
    except Exception as e:
        print(f"健康检查失败: {e}")
        return False


def check_issuer_holder_connection(quiet: bool = False) -> bool:
    """检查Issuer和Holder之间是否有有效连接"""
    try:
        # 获取Issuer的连接列表
        resp = requests.get(f"{ISSUER_ADMIN_URL}/connections", timeout=10)
        if resp.status_code != 200:
            return False

        data = resp.json()
        for conn in data.get('results', []):
            # 检查是否有到Holder的active或response连接
            state = conn.get('state')
            their_label = conn.get('their_label', '')
            if state in ['active', 'response'] and 'Holder' in their_label:
                issuer_conn_id = conn.get('connection_id')
                issuer_their_did = conn.get('their_did')

                # 验证Holder端是否也有对应的连接（通过DID匹配）
                holder_resp = requests.get(f"{HOLDER_ADMIN_URL}/connections", timeout=10)
                if holder_resp.status_code == 200:
                    holder_data = holder_resp.json()
                    for holder_conn in holder_data.get('results', []):
                        holder_state = holder_conn.get('state')
                        holder_label = holder_conn.get('their_label', '')
                        holder_my_did = holder_conn.get('my_did')

                        # 检查DID是否匹配：Issuer的Their DID 应该等于 Holder的My DID
                        if (holder_state in ['active', 'response'] and
                            'Issuer' in holder_label and
                            holder_my_did == issuer_their_did):
                            if not quiet:
                                print(f"✅ 发现有效连接 (DID匹配):")
                                print(f"   Issuer端: {issuer_conn_id} ({state})")
                                print(f"   Holder端: {holder_conn.get('connection_id')} ({holder_state})")
                                print(f"   匹配DID: {issuer_their_did}")
                            return True

        if not quiet:
            print("⚠️  未发现DID匹配的有效连接")
        return False
    except Exception as e:
        if not quiet:
            print(f"连接检查失败: {e}")
        return False


def create_issuer_holder_connection(quiet: bool = False) -> bool:
    """创建Issuer和Holder之间的新连接"""
    if not quiet:
        print("正在创建Issuer-Holder连接...")

    try:
        # 1. Issuer创建邀请
        resp = requests.post(
            f"{ISSUER_ADMIN_URL}/connections/create-invitation",
            params={"alias": "oracle-holder", "auto_accept": "true"},
            timeout=30
        )

        if resp.status_code not in [200, 201]:
            if not quiet:
                print(f"❌ 创建邀请失败: {resp.status_code}")
            return False

        data = resp.json()
        issuer_conn_id = data.get('connection_id')
        invitation = data.get('invitation')
        if not quiet:
            print(f"✅ Issuer创建邀请: {issuer_conn_id}")

        # 2. Holder接受邀请
        resp2 = requests.post(
            f"{HOLDER_ADMIN_URL}/connections/receive-invitation",
            params={"alias": "oracle-issuer", "auto_accept": "true"},
            json=invitation,
            timeout=30
        )

        if resp2.status_code not in [200, 201]:
            if not quiet:
                print(f"❌ Holder接受邀请失败: {resp2.status_code}")
            return False

        holder_data = resp2.json()
        holder_conn_id = holder_data.get('connection_id')
        if not quiet:
            print(f"✅ Holder接受邀请: {holder_conn_id}")

        # 3. 等待连接建立
        if not quiet:
            print("等待连接建立...")
        time.sleep(5)

        # 4. 验证连接状态
        resp3 = requests.get(f"{ISSUER_ADMIN_URL}/connections/{issuer_conn_id}", timeout=10)
        if resp3.status_code == 200:
            conn_data = resp3.json()
            state = conn_data.get('state')
            if not quiet:
                print(f"✅ 连接已建立 (状态: {state})")
            return True

        return False

    except Exception as e:
        if not quiet:
            print(f"❌ 创建连接异常: {e}")
        return False


def ensure_connection(quiet: bool = False, smart: bool = True) -> bool:
    """确保Issuer-Holder之间有有效连接

    Args:
        quiet: 静默模式
        smart: 智能模式（默认True）- 只检查和创建，不主动清理

    修改说明：
        - 移除强制清理旧连接的逻辑
        - 默认 smart=True，避免破坏 Oracle 的连接管理
    """
    if not quiet:
        print("\n" + "=" * 60)
        print("检查Issuer-Holder连接")
        print("=" * 60)

    # 智能模式：先检查是否已有有效连接（DID匹配）
    if smart:
        if not quiet:
            print("智能模式：检查现有连接...")
        if check_issuer_holder_connection(quiet=True):
            if not quiet:
                print("✅ 发现有效连接，直接使用")
            return True
        if not quiet:
            print("未发现有效连接，将创建新连接")

    # 移除清理逻辑：不再强制删除旧连接
    # 让 Oracle 自己管理连接生命周期

    # 只创建新连接（如果需要）
    if not quiet:
        print("\n创建新连接...")
    if create_issuer_holder_connection(quiet=quiet):
        if not quiet:
            print("✅ 连接创建成功")
        return True

    if not quiet:
        print("❌ 连接创建失败")
    return False


def list_test_cases(test_data: Dict):
    """列出所有测试用例"""
    print("=" * 60)
    print("可用的测试用例:")
    print("=" * 60)

    test_cases = test_data.get('test_cases', {})
    default_test = test_data.get('default_test', '')

    for name, case in test_cases.items():
        marker = " (默认)" if name == default_test else ""
        print(f"\n  {name}{marker}")
        print(f"    描述: {case.get('description', '无描述')}")
        print(f"    VC类型: {case.get('vc_type', 'unknown')}")
        attrs = case.get('attributes', {})
        print(f"    属性数量: {len(attrs)}")
        if attrs.get('contractName'):
            print(f"    合同名: {attrs.get('contractName')}")

    print("\n" + "=" * 60)


def verify_vc_in_holder(vc_uuid: str, expected_attrs: Dict) -> bool:
    """验证VC是否已存储在Holder中"""
    print("\n" + "-" * 40)
    print("验证Holder中的VC...")
    print("-" * 40)

    try:
        resp = requests.get(f"{HOLDER_ADMIN_URL}/credentials", timeout=10)
        if resp.status_code != 200:
            print(f"❌ 查询失败: {resp.status_code}")
            return False

        data = resp.json()
        creds = data.get('results', [])

        # 查找特定UUID的VC
        for vc in creds:
            attrs = vc.get('attrs', {})
            if attrs.get('contractName') == vc_uuid:
                print(f"✅ 找到VC (referent: {vc.get('referent')})")
                print(f"   Schema ID: {vc.get('schema_id')}")
                print(f"   Cred Def ID: {vc.get('cred_def_id')}")

                # 验证属性
                print("\n   属性验证:")
                all_match = True
                for key, expected_value in expected_attrs.items():
                    actual_value = attrs.get(key)
                    match = actual_value == expected_value
                    symbol = "✅" if match else "❌"
                    print(f"     {symbol} {key}: {actual_value}")
                    if not match:
                        all_match = False

                return all_match

        print(f"❌ 未找到UUID为 {vc_uuid} 的VC")
        return False

    except Exception as e:
        print(f"❌ 验证异常: {e}")
        return False


def run_single_test(endpoint: str, test_case: Dict, test_name: str, verify: bool = True) -> Dict:
    """运行单个测试用例"""
    print(f"\n{'=' * 60}")
    print(f"运行测试: {test_name}")
    print(f"描述: {test_case.get('description', '无描述')}")
    print("=" * 60)

    vc_type = test_case.get('vc_type')
    metadata = test_case.get('metadata', {})
    attributes = test_case.get('attributes', {}).copy()  # 复制以避免修改原数据

    # 添加时间戳使contractName唯一
    original_contract = attributes.get('contractName', '')
    if original_contract:
        attributes['contractName'] = f"{original_contract}-{int(time.time())}"
        print(f"唯一合同名: {attributes['contractName']}")

    payload = {
        "vc_type": vc_type,
        "metadata": metadata,
        "attributes": attributes
    }

    print(f"\n发送请求到: {endpoint}/issue-vc")
    print(f"VC类型: {vc_type}")

    start_time = time.time()

    try:
        resp = requests.post(
            f"{endpoint}/issue-vc",
            json=payload,
            timeout=120  # VC发行可能需要较长时间
        )

        elapsed = time.time() - start_time

        if resp.status_code == 200:
            result = resp.json()
            status = result.get('status', 'unknown')

            print(f"\n结果: {status}")
            print(f"耗时: {elapsed:.2f}秒")

            if status == 'success':
                vc_uuid = result.get('vc_uuid')
                vc_hash = result.get('vc_hash')
                tx_hash = result.get('tx_hash')

                print(f"\n✅ VC发行成功:")
                print(f"   Request ID: {result.get('request_id', 'N/A')}")
                print(f"   VC UUID: {vc_uuid}")
                print(f"   VC Hash: {vc_hash}")
                print(f"   TX Hash: {tx_hash}")

                # 验证VC是否存储在Holder中
                if verify and vc_uuid:
                    verify_result = verify_vc_in_holder(vc_uuid, attributes)
                    result['holder_verified'] = verify_result
                    if not verify_result:
                        result['status'] = 'partial'

                return result
            else:
                error = result.get('error', '未知错误')
                print(f"\n❌ 错误: {error}")
                return {"status": "failed", "error": error}

        else:
            print(f"\n❌ 请求失败: {resp.status_code}")
            print(f"响应: {resp.text}")
            return {"status": "failed", "error": f"HTTP {resp.status_code}: {resp.text}"}

    except requests.exceptions.Timeout:
        print(f"\n❌ 请求超时 (120秒)")
        return {"status": "failed", "error": "请求超时"}
    except Exception as e:
        print(f"\n❌ 请求异常: {e}")
        return {"status": "failed", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description='从JSON配置文件测试VC发行',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                          # 运行默认测试
  %(prog)s -t insurance_contract_basic  # 运行指定测试
  %(prog)s -l                       # 列出所有测试用例
  %(prog)s -a                       # 运行所有测试用例
  %(prog)s --check-conn             # 只检查连接状态
        """
    )
    parser.add_argument('--test', '-t', type=str, help='指定测试用例名称')
    parser.add_argument('--list', '-l', action='store_true', help='列出所有测试用例')
    parser.add_argument('--all', '-a', action='store_true', help='运行所有测试用例')
    parser.add_argument('--endpoint', '-e', type=str, default='http://localhost:6000',
                        help='Oracle服务端点 (默认: http://localhost:6000)')
    parser.add_argument('--skip-health', action='store_true', help='跳过健康检查')
    parser.add_argument('--skip-verify', action='store_true', help='跳过Holder验证')
    parser.add_argument('--check-conn', action='store_true', help='只检查连接状态')
    parser.add_argument('--create-conn', action='store_true', help='强制创建新连接')

    args = parser.parse_args()

    # 加载测试数据
    test_data = load_test_data()

    # 列出测试用例
    if args.list:
        list_test_cases(test_data)
        return

    # 只检查连接
    if args.check_conn:
        print("检查Issuer-Holder连接状态...")
        if check_issuer_holder_connection():
            print("\n✅ 连接正常")
            sys.exit(0)
        else:
            print("\n❌ 连接不存在或已断开")
            sys.exit(1)

    # 强制创建连接
    if args.create_conn:
        print("强制创建新连接...")
        if create_issuer_holder_connection():
            print("\n✅ 连接创建成功")
            sys.exit(0)
        else:
            print("\n❌ 连接创建失败")
            sys.exit(1)

    # 获取端点
    endpoint = args.endpoint or test_data.get('oracle_endpoint', {}).get('url', 'http://localhost:6000')

    # 健康检查
    if not args.skip_health:
        print("=" * 60)
        print("步骤1: 检查Oracle服务健康状态")
        print("=" * 60)
        if not check_oracle_health(endpoint):
            print("\n⚠️  Oracle服务健康检查未通过")
            response = input("是否继续? (y/n): ")
            if response.lower() != 'y':
                print("已取消")
                sys.exit(1)
        print()

    # 确保Issuer-Holder连接
    if not ensure_connection():
        print("\n❌ 无法建立Issuer-Holder连接，测试无法继续")
        sys.exit(1)

    # 确定要运行的测试用例
    test_cases = test_data.get('test_cases', {})
    default_test = test_data.get('default_test', 'inspection_report_basic')

    if args.all:
        # 运行所有测试
        print("\n" + "=" * 60)
        print("运行所有测试用例")
        print("=" * 60)

        results = {}
        verify = not args.skip_verify
        for name, case in test_cases.items():
            results[name] = run_single_test(endpoint, case, name, verify=verify)
            time.sleep(3)  # 测试之间稍作等待

        # 汇总结果
        print("\n" + "=" * 60)
        print("测试汇总")
        print("=" * 60)
        success_count = sum(1 for r in results.values() if r.get('status') == 'success')
        partial_count = sum(1 for r in results.values() if r.get('status') == 'partial')
        failed_count = len(results) - success_count - partial_count

        print(f"总计: {len(results)} 个测试")
        print(f"✅ 完全成功: {success_count}")
        if partial_count > 0:
            print(f"⚠️  部分成功: {partial_count} (VC已发行但验证失败)")
        print(f"❌ 失败: {failed_count}")

        # 显示失败的测试
        if failed_count > 0 or partial_count > 0:
            print("\n失败的测试:")
            for name, result in results.items():
                if result.get('status') != 'success':
                    status_icon = "⚠️" if result.get('status') == 'partial' else "❌"
                    print(f"  {status_icon} {name}: {result.get('error', 'N/A')}")

    else:
        # 运行单个测试
        test_name = args.test or default_test

        if test_name not in test_cases:
            print(f"❌ 测试用例 '{test_name}' 不存在")
            print(f"可用测试用例: {', '.join(test_cases.keys())}")
            sys.exit(1)

        verify = not args.skip_verify
        result = run_single_test(endpoint, test_cases[test_name], test_name, verify=verify)

        # 返回码
        sys.exit(0 if result.get('status') == 'success' else 1)


if __name__ == "__main__":
    main()
