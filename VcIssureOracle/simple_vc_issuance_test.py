#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化AIP 2.0 VC发行测试程序
使用同步requests库完成InspectionReport类型的VC发行测试

适用场景：
- ACA-Py 1.2.0
- Holder有--auto-store-credential参数
- HTTP传输模式
- 一次性测试，不写入区块链
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Optional

import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class SimpleVCIssuanceTest:
    """简化的AIP 2.0 VC发行测试类 - 使用同步requests库"""

    def __init__(self):
        """初始化测试类"""
        # 加载配置
        self.config = self._load_config()

        self.issuer_admin_url = self.config['issuer']['admin_url'].rstrip('/')
        self.holder_admin_url = self.config['holder']['admin_url'].rstrip('/')

        # InspectionReport的CredDef ID (AIP 2.0)
        # 注意：因钱包重置，原CredDef不在钱包中，需要使用新tag创建
        self.cred_def_id = "DPvobytTtKvmyeRTJZYjsg:3:CL:762:InspectionReport_V8"

        # 测试属性
        self.test_attributes = {
            "exporter": "测试出口商",
            "contractName": "auto-test-003",
            "productName": "电子产品",
            "productQuantity": "1000",
            "productBatch": "BATCH-2024-001",
            "inspectionPassed": "true",
            "Date": "2024-01-15"
        }

        self.issuer_connection_id: Optional[str] = None
        self.holder_connection_id: Optional[str] = None

    def _load_config(self) -> Dict:
        """从config/vc_config.json加载配置"""
        script_dir = Path(__file__).parent
        config_path = script_dir.parent / "config" / "vc_config.json"

        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    # ==================== 健康检查 ====================

    def check_health(self) -> bool:
        """检查ACA-Py服务状态"""
        logger.info("[步骤1] 检查ACA-Py服务状态")

        # 检查Issuer
        try:
            resp = requests.get(f"{self.issuer_admin_url}/status", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                version = data.get("version", "unknown")
                logger.info(f"  ✓ Issuer ACA-Py ({self.issuer_admin_url}) - 版本 {version}")
            else:
                logger.error(f"  ✗ Issuer ACA-Py响应错误: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"  ✗ Issuer ACA-Py连接失败: {e}")
            return False

        # 检查Holder
        try:
            resp = requests.get(f"{self.holder_admin_url}/status", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                version = data.get("version", "unknown")
                logger.info(f"  ✓ Holder ACA-Py ({self.holder_admin_url}) - 版本 {version}")
            else:
                logger.error(f"  ✗ Holder ACA-Py响应错误: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"  ✗ Holder ACA-Py连接失败: {e}")
            return False

        return True

    # ==================== 连接管理 ====================

    def get_existing_active_connection(self) -> Optional[str]:
        """获取已有的active连接"""
        try:
            resp = requests.get(f"{self.issuer_admin_url}/connections", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                connections = data.get('results', [])

                for conn in connections:
                    if conn.get('state') == 'active':
                        conn_id = conn.get('connection_id')
                        logger.info(f"  找到现有active连接: {conn_id}")
                        return conn_id
        except Exception as e:
            logger.warning(f"  检查现有连接失败: {e}")

        return None

    def create_connection(self) -> Optional[str]:
        """创建新连接"""
        logger.info("  创建新连接...")

        # 1. Issuer创建邀请
        payload = {
            "auto_accept": True,
            "multi_use": False,
            "alias": "simple-test-issuer"
        }

        try:
            resp = requests.post(
                f"{self.issuer_admin_url}/connections/create-invitation",
                json=payload,
                timeout=30
            )
            if resp.status_code not in [200, 201]:
                logger.error(f"  ✗ 创建邀请失败: {resp.status_code} - {resp.text}")
                return None

            data = resp.json()
            self.issuer_connection_id = data.get('connection_id')
            invitation = data.get('invitation')
            logger.info(f"  ✓ Issuer邀请创建成功: {self.issuer_connection_id}")

        except Exception as e:
            logger.error(f"  ✗ 创建邀请异常: {e}")
            return None

        # 2. Holder接受邀请
        params = {
            "auto_accept": "true",
            "alias": "simple-test-holder"
        }

        try:
            resp = requests.post(
                f"{self.holder_admin_url}/connections/receive-invitation",
                params=params,
                json=invitation,
                timeout=30
            )
            if resp.status_code not in [200, 201]:
                logger.error(f"  ✗ Holder接受邀请失败: {resp.status_code} - {resp.text}")
                return None

            data = resp.json()
            self.holder_connection_id = data.get('connection_id')
            logger.info(f"  ✓ Holder接受邀请成功: {self.holder_connection_id}")

        except Exception as e:
            logger.error(f"  ✗ Holder接受邀请异常: {e}")
            return None

        # 3. 等待连接active
        if self.wait_for_connection_active():
            return self.issuer_connection_id

        return None

    def wait_for_connection_active(self, timeout: int = 30) -> bool:
        """等待连接变为active或response状态"""
        logger.info("  等待连接就绪...")

        start_time = time.time()

        while (time.time() - start_time) < timeout:
            try:
                resp = requests.get(
                    f"{self.issuer_admin_url}/connections/{self.issuer_connection_id}",
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    state = data.get('state')

                    if state == 'active':
                        logger.info(f"  ✓ 连接已active: {self.issuer_connection_id}")
                        return True
                    elif state == 'response':
                        logger.info(f"  ✓ 连接处于response状态 (HTTP模式可用)")
                        return True
                    else:
                        logger.info(f"  连接状态: {state}")

            except Exception as e:
                logger.warning(f"  检查连接状态失败: {e}")

            time.sleep(1)

        logger.error(f"  ✗ 等待连接就绪超时({timeout}秒)")
        return False

    # ==================== VC发行 ====================

    def issue_vc_offer(self, conn_id: str) -> Optional[str]:
        """发送VC offer (使用AIP 2.0协议)"""
        # 构建credential preview
        attr_list = [
            {"name": k, "value": str(v)}
            for k, v in self.test_attributes.items()
        ]

        # 直接使用AIP 2.0 API
        logger.info("  使用 AIP 2.0 API (issue-credential-2.0)...")
        payload_v2 = {
            "connection_id": conn_id,
            "comment": "简化测试发行",
            "credential_preview": {
                "@type": "issue-credential/2.0/credential-preview",
                "attributes": attr_list
            },
            "filter": {
                "indy": {
                    "cred_def_id": self.cred_def_id
                }
            }
        }

        try:
            resp = requests.post(
                f"{self.issuer_admin_url}/issue-credential-2.0/send-offer",
                json=payload_v2,
                timeout=30
            )

            if resp.status_code in [200, 201]:
                data = resp.json()
                # 优先使用cred_ex_id，其次使用thread_id
                cred_ex_id = data.get("cred_ex_id") or data.get("thread_id")
                thread_id = data.get("thread_id")

                # 如果只有thread_id，尝试通过thread_id查找cred_ex_id
                if not data.get("cred_ex_id") and thread_id:
                    time.sleep(1)
                    cred_ex_id = self._find_cred_ex_by_thread_id(thread_id)

                logger.info(f"  ✓ VC offer已发送 (AIP 2.0): {cred_ex_id}")
                return cred_ex_id
            else:
                logger.error(f"  ✗ 发送offer失败: {resp.status_code} - {resp.text}")
                return None

        except Exception as e:
            logger.error(f"  ✗ 发送offer异常: {e}")
            return None

    def _find_cred_ex_by_thread_id(self, thread_id: str) -> Optional[str]:
        """通过thread_id查找cred_ex_id"""
        try:
            resp = requests.get(
                f"{self.issuer_admin_url}/issue-credential-2.0/records",
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                for record in data.get('results', []):
                    rec = record.get('cred_ex_record', record)
                    if rec.get('thread_id') == thread_id:
                        return rec.get('cred_ex_id')
        except Exception as e:
            logger.warning(f"  查找cred_ex_id失败: {e}")
        return None

    def create_holder_credential_exchange(self, conn_id: str) -> Optional[str]:
        """在Holder端主动创建credential exchange记录（HTTP模式解决方案）"""
        logger.info("  在Holder端主动创建credential exchange记录...")

        # 构建credential preview
        attr_list = [
            {"name": k, "value": str(v)}
            for k, v in self.test_attributes.items()
        ]

        # 先尝试send-request方式（Holder主动请求）
        payload = {
            "connection_id": conn_id,
            "comment": "Holder主动发起的VC请求",
            "credential_preview": {
                "@type": "issue-credential/1.0/credential-preview",
                "attributes": attr_list
            },
            "cred_def_id": self.cred_def_id
        }

        try:
            resp = requests.post(
                f"{self.holder_admin_url}/issue-credential/send-request",
                json=payload,
                timeout=30
            )

            if resp.status_code in [200, 201]:
                data = resp.json()
                cred_ex_id = data.get("credential_exchange_id") or data.get("thread_id")
                logger.info(f"  ✓ Holder端credential exchange已创建: {cred_ex_id}")
                return cred_ex_id
            else:
                logger.warning(f"  send-request失败: {resp.status_code}，尝试send-offer方式...")
        except Exception as e:
            logger.warning(f"  send-request异常: {e}，尝试send-offer方式...")

        # 备用：在Holder端创建一个"反向"offer
        payload_offer = {
            "connection_id": conn_id,
            "comment": "Holder主动创建的VC offer",
            "credential_preview": {
                "@type": "issue-credential/1.0/credential-preview",
                "attributes": attr_list
            },
            "cred_def_id": self.cred_def_id,
            "auto_issue": True
        }

        try:
            resp = requests.post(
                f"{self.holder_admin_url}/issue-credential/send-offer",
                json=payload_offer,
                timeout=30
            )

            if resp.status_code in [200, 201]:
                data = resp.json()
                cred_ex_id = data.get("credential_exchange_id") or data.get("thread_id")
                logger.info(f"  ✓ Holder端credential exchange已创建(offer方式): {cred_ex_id}")

                # 等待Holder自动处理
                time.sleep(2)

                # 检查状态并发送请求
                resp_check = requests.get(
                    f"{self.holder_admin_url}/issue-credential/records/{cred_ex_id}",
                    timeout=10
                )
                if resp_check.status_code == 200:
                    record = resp_check.json()
                    state = record.get('state')
                    logger.info(f"    Holder端状态: {state}")

                    # 如果是offer_received状态，发送请求
                    if state == 'offer_received':
                        resp_req = requests.post(
                            f"{self.holder_admin_url}/issue-credential/records/{cred_ex_id}/send-request",
                            json={},
                            timeout=10
                        )
                        if resp_req.status_code in [200, 201]:
                            logger.info(f"    ✓ Holder已发送request")

                return cred_ex_id
            else:
                logger.warning(f"  send-offer失败: {resp.status_code}")
                return None

        except Exception as e:
            logger.warning(f"  send-offer异常: {e}")
            return None

    def check_and_trigger_holder(self) -> bool:
        """检查Holder状态并触发send-request (支持旧API和新API)"""
        results = []
        api_version = None

        # 先尝试新API
        try:
            resp = requests.get(
                f"{self.holder_admin_url}/issue-credential-2.0/records",
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get('results', [])
                api_version = "v2"
        except Exception:
            pass

        # 如果新API没有结果，尝试旧API
        if not results:
            try:
                resp = requests.get(
                    f"{self.holder_admin_url}/issue-credential/records",
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get('results', [])
                    api_version = "v1"
            except Exception as e:
                logger.error(f"  查询Holder记录失败: {e}")
                return False

        if not results:
            logger.warning(f"  Holder端未找到credential exchange记录")
            return False

        for record in reversed(results):  # 从最新的开始
            state = record.get('state')
            cred_ex_id = record.get('cred_ex_id')

            # 旧API和新API的状态名称可能不同
            offer_states = ['offer-received', 'offer_received']
            progress_states = ['request-sent', 'request_sent', 'credential-received', 'credential_received', 'done', 'credential_acked']

            # 如果Holder处于offer-received状态，触发send-request
            if state in offer_states and cred_ex_id:
                logger.info(f"  Holder处于{state}状态，触发send-request")
                logger.info(f"    cred_ex_id: {cred_ex_id}")

                # 根据API版本选择端点
                if api_version == "v2":
                    endpoint = f"{self.holder_admin_url}/issue-credential-2.0/records/{cred_ex_id}/send-request"
                else:
                    endpoint = f"{self.holder_admin_url}/issue-credential/records/{cred_ex_id}/send-request"

                post_resp = requests.post(endpoint, json={}, timeout=10)

                if post_resp.status_code in [200, 201]:
                    logger.info(f"  ✓ 成功触发Holder发送request")
                    return True
                else:
                    logger.error(f"  ✗ 触发send-request失败: {post_resp.status_code}")
                    return False

            # 如果状态已经是request-sent或更高，说明Holder已自动响应
            if state in progress_states:
                logger.info(f"  ✓ Holder已自动响应，当前状态: {state}")
                return True

        return False

    def monitor_issuance_progress(self, issuer_cred_ex_id: str, timeout: int = 60) -> bool:
        """监控VC发行进度 (支持旧API和新API)"""
        logger.info("[步骤6] 监控发行进度...")

        start_time = time.time()

        # 获取初始凭证数量
        initial_creds = self._get_holder_credentials()
        initial_count = len(initial_creds)
        logger.info(f"  初始VC数量: {initial_count}")

        state_history = []

        while (time.time() - start_time) < timeout:
            try:
                # 先尝试新API，失败则尝试旧API
                state = None
                data = None

                # 尝试 AIP 2.0 API
                resp = requests.get(
                    f"{self.issuer_admin_url}/issue-credential-2.0/records/{issuer_cred_ex_id}",
                    timeout=10
                )

                if resp.status_code == 200:
                    data = resp.json()
                    # AIP 2.0的state在cred_ex_record中
                    cred_ex_record = data.get('cred_ex_record', data)
                    state = cred_ex_record.get('state') or data.get('state')
                else:
                    # 尝试旧API
                    resp = requests.get(
                        f"{self.issuer_admin_url}/issue-credential/records/{issuer_cred_ex_id}",
                        timeout=10
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        cred_ex_record = data.get('cred_ex_record', data)
                        state = cred_ex_record.get('state') or data.get('state')

                if data and state:
                    if state not in state_history:
                        state_history.append(state)
                        logger.info(f"  Issuer状态: {state}")

                    # 如果状态为request-received，触发颁发
                    if state == 'request-received':
                        logger.info("  Issuer收到请求，自动颁发凭证...")
                        if self._issue_credential(issuer_cred_ex_id):
                            logger.info(f"  ✓ 凭证颁发成功")
                            # 颁发成功后等待Holder接收并存储
                            time.sleep(3)
                            current_creds = self._get_holder_credentials()
                            if len(current_creds) > initial_count:
                                logger.info(f"  ✓ Holder已存储新VC!")
                                return True
                            # 继续监控，可能需要更多时间
                        else:
                            logger.error(f"  ✗ 凭证颁发失败")
                            return False

                    # 如果状态为done或credential_acked，检查Holder
                    if state in ['done', 'credential_acked']:
                        logger.info(f"  ✓ 凭证交换完成!")
                        time.sleep(2)
                        current_creds = self._get_holder_credentials()

                        if len(current_creds) > initial_count:
                            logger.info(f"  ✓ Holder已存储新VC!")
                            return True
                        else:
                            logger.warning(f"  ⚠ Holder未检测到新VC")
                            # 继续检查，可能只是延迟
                            pass

                # 检查并触发Holder
                self.check_and_trigger_holder()

            except Exception as e:
                logger.warning(f"  检查状态时出错: {e}")

            time.sleep(2)

        logger.error(f"  ✗ 监控超时({timeout}秒)")
        logger.error(f"  状态历史: {' -> '.join(state_history)}")
        return False

    def _issue_credential(self, cred_ex_id: str) -> bool:
        """颁发凭证 (支持旧API和新API)"""
        # 先尝试新API
        try:
            resp = requests.post(
                f"{self.issuer_admin_url}/issue-credential-2.0/records/{cred_ex_id}/issue",
                json={},
                timeout=30
            )
            if resp.status_code in [200, 201]:
                return True
        except Exception:
            pass

        # 尝试旧API
        try:
            resp = requests.post(
                f"{self.issuer_admin_url}/issue-credential/records/{cred_ex_id}/issue",
                json={},
                timeout=30
            )
            return resp.status_code in [200, 201]
        except Exception:
            return False

    def _get_holder_credentials(self) -> list:
        """获取Holder的所有凭证"""
        try:
            resp = requests.get(f"{self.holder_admin_url}/credentials", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('results', [])
        except Exception:
            pass
        return []

    # ==================== 验证 ====================

    def verify_credential_stored(self) -> Optional[Dict]:
        """验证Holder是否已存储VC"""
        logger.info("[步骤7] 验证VC已存储")

        try:
            resp = requests.get(f"{self.holder_admin_url}/credentials", timeout=10)
            if resp.status_code != 200:
                logger.error(f"  ✗ 查询凭证失败: {resp.status_code}")
                return None

            data = resp.json()
            results = data.get('results', [])

            # 查找最新匹配的凭证
            for cred in reversed(results):
                attrs = cred.get('attrs', {})

                # 使用contractName匹配
                if attrs.get('contractName') == self.test_attributes.get('contractName'):
                    logger.info(f"  ✓ Holder已存储新凭证")
                    logger.info(f"    Referent: {cred.get('referent')}")
                    logger.info(f"    CredDef ID: {cred.get('cred_def_id')}")
                    logger.info(f"    Schema ID: {cred.get('schema_id')}")

                    # 显示所有属性
                    for key, value in attrs.items():
                        logger.info(f"    {key}: {value}")

                    return cred

            logger.warning(f"  ⚠ 未找到匹配的凭证")
            return None

        except Exception as e:
            logger.error(f"  ✗ 验证失败: {e}")
            return None

    # ==================== 主测试流程 ====================

    def run_test(self) -> bool:
        """运行完整测试流程"""
        logger.info("=" * 70)
        logger.info("  简化AIP 2.0 VC发行测试程序")
        logger.info("=" * 70)
        logger.info("")

        try:
            # 步骤1: 健康检查
            if not self.check_health():
                logger.error("健康检查失败，退出测试")
                return False

            logger.info("")

            # 步骤2: 获取CredDef ID
            logger.info("[步骤2] 获取Credential Definition")
            logger.info(f"  ✓ CredDef ID: {self.cred_def_id}")
            logger.info("")

            # 步骤3: 检查连接
            logger.info("[步骤3] 检查连接")
            existing_conn = self.get_existing_active_connection()
            if existing_conn:
                logger.info(f"  使用现有连接: {existing_conn}")
                self.issuer_connection_id = existing_conn
            else:
                conn_id = self.create_connection()
                if not conn_id:
                    logger.error("创建连接失败")
                    return False
            logger.info("")

            # 步骤4: 发送VC offer
            logger.info("[步骤4] 发送VC Offer")
            cred_ex_id = self.issue_vc_offer(self.issuer_connection_id)
            if not cred_ex_id:
                logger.error("发送VC offer失败")
                return False
            logger.info("")

            # 步骤5: 检查Holder状态并触发request
            logger.info("[步骤5] 检查Holder状态并触发request")
            time.sleep(2)  # 给Holder一点时间自动处理
            if not self.check_and_trigger_holder():
                logger.info("  Holder可能已自动处理，继续监控...")
            logger.info("")

            # 步骤6: 监控发行进度
            if not self.monitor_issuance_progress(cred_ex_id):
                logger.error("VC发行失败")
                return False
            logger.info("")

            # 步骤7: 验证VC已存储
            stored_cred = self.verify_credential_stored()
            logger.info("")

            # 输出结果
            logger.info("=" * 70)
            if stored_cred:
                logger.info("  测试结果: ✓ 成功")
            else:
                logger.info("  测试结果: ✗ 失败 (VC未存储)")
            logger.info("=" * 70)

            return stored_cred is not None

        except Exception as e:
            logger.error(f"测试异常: {e}", exc_info=True)
            logger.info("=" * 70)
            logger.info("  测试结果: ✗ 异常")
            logger.info("=" * 70)
            return False


def main():
    """主函数"""
    # 切换到脚本所在目录
    script_dir = Path(__file__).parent
    import os
    os.chdir(script_dir)

    test = SimpleVCIssuanceTest()
    success = test.run_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
