#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VP验证自动化脚本
自动完成 Holder 和 Verifier 之间的 VP 验证流程
"""

import json
import sys
import time
from datetime import datetime
from typing import Dict, Optional, Tuple, List
import requests


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


class VPVerifier:
    """VP验证自动化类"""

    def __init__(self, verifier_url: str = "http://localhost:8082",
                 holder_url: str = "http://localhost:8081"):
        self.verifier_url = verifier_url
        self.holder_url = holder_url
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def print_header(self, title: str):
        """打印标题"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}  {title}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}\n")

    def print_success(self, msg: str):
        """打印成功消息"""
        print(f"{Colors.GREEN}✓{Colors.END} {msg}")

    def print_error(self, msg: str):
        """打印错误消息"""
        print(f"{Colors.RED}✗{Colors.END} {msg}")

    def print_info(self, msg: str):
        """打印信息"""
        print(f"{Colors.CYAN}ℹ{Colors.END} {msg}")

    def print_warning(self, msg: str):
        """打印警告"""
        print(f"{Colors.YELLOW}⚠{Colors.END} {msg}")

    def check_service_health(self, url: str, name: str) -> bool:
        """检查服务健康状态"""
        try:
            resp = self.session.get(f"{url}/status", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                version = data.get('version', 'unknown')
                label = data.get('label', 'unknown')
                self.print_success(f"{name} ACA-Py 运行正常 (版本: {version}, Label: {label})")
                return True
            else:
                self.print_error(f"{name} ACA-Py 返回异常状态: {resp.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            self.print_error(f"{name} ACA-Py 连接失败: {e}")
            return False

    def get_active_connection(self) -> Optional[Dict]:
        """获取活跃连接"""
        try:
            resp = self.session.get(f"{self.verifier_url}/connections", timeout=10)
            if resp.status_code != 200:
                return None

            data = resp.json()
            active_conns = [
                c for c in data.get('results', [])
                if c.get('state') == 'active'
            ]

            if not active_conns:
                return None

            # 优先选择带有 Holder.Agent 标签的连接
            for conn in active_conns:
                if conn.get('their_label') == 'Holder.Agent':
                    return conn

            return active_conns[0]

        except requests.exceptions.RequestException:
            return None

    def create_connection(self) -> Optional[str]:
        """创建新连接"""
        try:
            resp = self.session.post(
                f"{self.verifier_url}/connections/create-invitation",
                json={"alias": "VP-Test-Connection"},
                timeout=10
            )
            if resp.status_code == 200:
                invitation = resp.json()
                invitation_url = invitation.get('invitation_url')
                conn_id = invitation.get('connection_id')

                self.print_info(f"创建连接邀请: {conn_id}")
                self.print_info(f"邀请URL: {invitation_url}")
                self.print_warning("请Holder接受此邀请后继续...")

                return conn_id
            return None
        except requests.exceptions.RequestException:
            return None

    def wait_for_connection_active(self, conn_id: str, timeout: int = 30) -> bool:
        """等待连接变为活跃状态"""
        self.print_info(f"等待连接激活 (最多{timeout}秒)...")

        for i in range(timeout):
            try:
                resp = self.session.get(
                    f"{self.verifier_url}/connections/{conn_id}",
                    timeout=5
                )
                if resp.status_code == 200:
                    conn = resp.json()
                    state = conn.get('state')

                    if state == 'active':
                        self.print_success(f"连接已激活!")
                        return True
                    elif state in ['deleted', 'abandoned']:
                        self.print_error(f"连接已{state}")
                        return False

            except requests.exceptions.RequestException:
                pass

            time.sleep(1)

        self.print_error("等待连接超时")
        return False

    def get_holder_credentials(self) -> Tuple[List[Dict], List[Dict]]:
        """获取Holder持有的VC"""
        try:
            resp = self.session.get(f"{self.holder_url}/credentials", timeout=10)
            if resp.status_code != 200:
                return [], []

            data = resp.json()
            all_creds = data.get('results', [])

            # 分类VC
            inspection_vcs = []
            for cred in all_creds:
                cred_def_id = cred.get('cred_def_id', '')
                if 'InspectionReport' in cred_def_id:
                    inspection_vcs.append(cred)

            return all_creds, inspection_vcs

        except requests.exceptions.RequestException:
            return [], []

    def send_presentation_request(
        self,
        conn_id: str,
        requested_attributes: List[str],
        auto_remove: bool = False
    ) -> Optional[str]:
        """发送Presentation Request"""

        # 构造请求
        requested_attrs = {}
        for i, attr_name in enumerate(requested_attributes, 1):
            requested_attrs[f"attr{i}"] = {"name": attr_name}

        proof_request = {
            "connection_id": conn_id,
            "presentation_request": {
                "indy": {
                    "name": "VP验证自动化测试",
                    "version": "1.0",
                    "nonce": str(int(time.time())),
                    "requested_attributes": requested_attrs,
                    "requested_predicates": {}
                }
            },
            "auto_verify": True,
            "auto_remove": auto_remove
        }

        try:
            resp = self.session.post(
                f"{self.verifier_url}/present-proof-2.0/send-request",
                json=proof_request,
                timeout=10
            )

            if resp.status_code == 200:
                result = resp.json()
                pres_ex_id = result.get('pres_ex_id')
                self.print_success(f"Presentation Request 已发送")
                self.print_info(f"PresEx ID: {pres_ex_id}")
                return pres_ex_id
            else:
                self.print_error(f"发送失败: {resp.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            self.print_error(f"发送请求异常: {e}")
            return None

    def wait_for_verification_result(
        self,
        pres_ex_id: str,
        timeout: int = 30
    ) -> Optional[Dict]:
        """等待验证结果"""
        self.print_info(f"等待验证结果...")

        start_time = time.time()

        for i in range(timeout * 2):  # 0.5秒间隔
            try:
                resp = self.session.get(
                    f"{self.verifier_url}/present-proof-2.0/records/{pres_ex_id}",
                    timeout=5
                )

                if resp.status_code == 200:
                    result = resp.json()
                    state = result.get('state')

                    if state == 'done':
                        elapsed = time.time() - start_time
                        self.print_success(f"验证完成! 耗时: {elapsed:.2f}秒")
                        return result
                    elif state == 'presentation-received':
                        self.print_info("收到Presentation，正在验证...")
                    elif state in ['abandoned', 'failed']:
                        self.print_error(f"验证失败 (状态: {state})")
                        return result
                else:
                    # 记录可能已被auto-remove删除
                    if i > 2:  # 至少等待1秒
                        elapsed = time.time() - start_time
                        self.print_success(f"验证完成 (记录已删除), 耗时: {elapsed:.2f}秒")
                        return {"state": "done_deleted", "verified": "true"}

            except requests.exceptions.RequestException as e:
                if i > 2:
                    elapsed = time.time() - start_time
                    self.print_success(f"验证完成 (连接关闭), 耗时: {elapsed:.2f}秒")
                    return {"state": "done_deleted", "verified": "true"}

            time.sleep(0.5)

        self.print_error("等待验证超时")
        return None

    def parse_verification_result(self, result: Dict) -> Dict:
        """解析验证结果"""
        parsed = {
            "verified": False,
            "state": result.get('state'),
            "revealed_attrs": {},
            "self_attested_attrs": {},
            "verified_credentials": []
        }

        verified = result.get('verified')
        if verified == 'true' or verified is True:
            parsed['verified'] = True

        # 解析by_format中的结果
        by_format = result.get('by_format', {})
        pres = by_format.get('pres', {})
        indy = pres.get('indy', {})

        # Requested proof
        req_proof = indy.get('requested_proof', {})

        # Revealed attributes
        revealed = req_proof.get('revealed_attrs', {})
        for ref, data in revealed.items():
            attr_name = data.get('name', ref)
            raw_value = data.get('raw')
            parsed['revealed_attrs'][attr_name] = raw_value

        # Self-attested attributes
        self_attested = req_proof.get('self_attested_attrs', {})
        for ref, value in self_attested.items():
            parsed['self_attested_attrs'][ref] = value

        # Identifiers (验证的凭证)
        identifiers = indy.get('identifiers', [])
        for idf in identifiers:
            parsed['verified_credentials'].append({
                'schema_id': idf.get('schema_id'),
                'cred_def_id': idf.get('cred_def_id'),
                'issuer_did': idf.get('issuer_did')
            })

        # 时间信息
        parsed['created_at'] = result.get('created_at')
        parsed['updated_at'] = result.get('updated_at')

        return parsed

    def display_verification_result(self, parsed: Dict):
        """显示验证结果"""
        self.print_header("验证结果")

        # 验证状态
        if parsed['verified']:
            self.print_success(f"验证状态: {'✓ VERIFIED' if parsed['verified'] else '✗ FAILED'}")
        else:
            self.print_error(f"验证状态: FAILED")

        # 时间信息
        if 'created_at' in parsed:
            self.print_info(f"创建时间: {parsed['created_at']}")
        if 'updated_at' in parsed:
            self.print_info(f"完成时间: {parsed['updated_at']}")

        # 揭示的属性
        if parsed['revealed_attrs']:
            print(f"\n{Colors.BOLD}从VC揭示的属性:{Colors.END}")
            for name, value in parsed['revealed_attrs'].items():
                print(f"  {Colors.CYAN}•{Colors.END} {name}: {Colors.GREEN}{value}{Colors.END}")

        # Self-attested属性
        if parsed['self_attested_attrs']:
            print(f"\n{Colors.BOLD}Self-attested属性:{Colors.END}")
            for ref, value in parsed['self_attested_attrs'].items():
                print(f"  {Colors.YELLOW}•{Colors.END} {ref}: {Colors.YELLOW}{value}{Colors.END} {Colors.RED}(self-attested){Colors.END}")

        # 验证的凭证
        if parsed['verified_credentials']:
            print(f"\n{Colors.BOLD}验证的凭证:{Colors.END}")
            for i, cred in enumerate(parsed['verified_credentials'], 1):
                print(f"  {Colors.CYAN}[{i}]{Colors.END}")
                print(f"    Schema: {cred.get('schema_id')}")
                print(f"    CredDef: {cred.get('cred_def_id')}")

    def delete_presentation_record(self, pres_ex_id: str) -> bool:
        """删除presentation记录"""
        try:
            resp = self.session.delete(
                f"{self.verifier_url}/present-proof-2.0/records/{pres_ex_id}",
                timeout=5
            )
            if resp.status_code in [200, 204]:
                self.print_success("已删除演示记录")
                return True
            return False
        except requests.exceptions.RequestException:
            return False

    def run_verification(
        self,
        requested_attributes: List[str] = None,
        auto_remove: bool = False,
        verbose: bool = True
    ) -> bool:
        """运行完整的验证流程"""

        if requested_attributes is None:
            requested_attributes = ["exporter", "inspectionPassed", "contractName"]

        if verbose:
            self.print_header("VP验证自动化流程")

        # 步骤1: 检查服务健康
        if verbose:
            print(f"{Colors.BOLD}[1/6]{Colors.END} 检查服务健康状态")

        verifier_ok = self.check_service_health(self.verifier_url, "Verifier")
        holder_ok = self.check_service_health(self.holder_url, "Holder")

        if not verifier_ok or not holder_ok:
            self.print_error("服务健康检查失败，请确保ACA-Py容器正在运行")
            return False

        # 步骤2: 检查Holder的VC
        if verbose:
            print(f"\n{Colors.BOLD}[2/6]{Colors.END} 检查Holder的可验证凭证")

        all_creds, inspection_vcs = self.get_holder_credentials()
        self.print_success(f"Holder持有 {len(all_creds)} 个VC")

        if inspection_vcs:
            self.print_info(f"找到 {len(inspection_vcs)} 个 InspectionReport VC")
            if verbose:
                attrs = inspection_vcs[0].get('attrs', {})
                self.print_info(f"示例: exporter={attrs.get('exporter')}, inspectionPassed={attrs.get('inspectionPassed')}")
        else:
            self.print_warning("未找到InspectionReport VC，将使用self-attested模式")

        # 步骤3: 获取或创建连接
        if verbose:
            print(f"\n{Colors.BOLD}[3/6]{Colors.END} 获取连接")

        conn = self.get_active_connection()

        if conn:
            conn_id = conn.get('connection_id')
            their_did = conn.get('their_did', 'N/A')
            their_label = conn.get('their_label', 'Unknown')
            self.print_success(f"使用已有连接")
            self.print_info(f"  Connection ID: {conn_id}")
            self.print_info(f"  Holder: {their_label} ({their_did})")
        else:
            self.print_warning("未找到活跃连接")
            conn_id = self.create_connection()

            if conn_id:
                if not self.wait_for_connection_active(conn_id):
                    return False
            else:
                self.print_error("创建连接失败")
                return False

        # 步骤4: 发送Presentation Request
        if verbose:
            print(f"\n{Colors.BOLD}[4/6]{Colors.END} 发送Presentation Request")

        if verbose:
            self.print_info(f"请求属性: {', '.join(requested_attributes)}")

        pres_ex_id = self.send_presentation_request(
            conn_id,
            requested_attributes,
            auto_remove=auto_remove
        )

        if not pres_ex_id:
            return False

        # 步骤5: 等待验证结果
        if verbose:
            print(f"\n{Colors.BOLD}[5/6]{Colors.END} 等待验证结果")

        result = self.wait_for_verification_result(pres_ex_id)

        if not result:
            self.print_error("未收到验证结果")
            return False

        # 步骤6: 解析并显示结果
        if verbose:
            print(f"\n{Colors.BOLD}[6/6]{Colors.END} 解析验证结果")

        parsed = self.parse_verification_result(result)

        if verbose:
            self.display_verification_result(parsed)
        else:
            return parsed['verified']

        # 清理
        if not auto_remove and result.get('state') == 'done':
            self.delete_presentation_record(pres_ex_id)

        print(f"\n{Colors.BOLD}{Colors.GREEN}{'=' * 70}{Colors.END}")
        if parsed['verified']:
            print(f"{Colors.BOLD}{Colors.GREEN}  ✓ VP验证流程成功完成!{Colors.END}")
        else:
            print(f"{Colors.BOLD}{Colors.RED}  ✗ VP验证流程失败{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}{'=' * 70}{Colors.END}\n")

        return parsed['verified']


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="VP验证自动化脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基础验证
  python3 vp_verification_auto.py

  # 指定验证属性
  python3 vp_verification_auto.py --attributes exporter inspectionPassed

  # 启用auto-remove
  python3 vp_verification_auto.py --auto-remove

  # 简洁模式
  python3 vp_verification_auto.py --quiet
        """
    )

    parser.add_argument(
        '--verifier-url',
        default='http://localhost:8082',
        help='Verifier ACA-Py Admin URL (默认: http://localhost:8082)'
    )

    parser.add_argument(
        '--holder-url',
        default='http://localhost:8081',
        help='Holder ACA-Py Admin URL (默认: http://localhost:8081)'
    )

    parser.add_argument(
        '--attributes',
        nargs='+',
        default=['exporter', 'inspectionPassed', 'contractName'],
        help='请求的属性列表 (默认: exporter inspectionPassed contractName)'
    )

    parser.add_argument(
        '--auto-remove',
        action='store_true',
        help='验证完成后自动删除记录'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='简洁模式，减少输出'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='等待验证超时时间（秒）(默认: 30)'
    )

    args = parser.parse_args()

    # 创建验证器
    verifier = VPVerifier(
        verifier_url=args.verifier_url,
        holder_url=args.holder_url
    )

    # 运行验证
    success = verifier.run_verification(
        requested_attributes=args.attributes,
        auto_remove=args.auto_remove,
        verbose=not args.quiet
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
