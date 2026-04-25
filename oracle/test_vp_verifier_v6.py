#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VP验证测试脚本 - V6版本

测试VP验证服务的各项功能：
1. 健康检查
2. 基础验证测试（不带vc_hash）
3. UUID匹配测试（带vc_hash）
4. 错误场景测试
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Optional

import aiohttp


class VPVerifierTester:
    """VP验证服务测试类"""

    def __init__(self, vc_type: str, vc_hash: str, base_url: str = "http://localhost:7000"):
        self.base_url = base_url.rstrip('/')
        self.vc_type = vc_type
        self.vc_hash = vc_hash
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """关闭session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/health") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ 健康检查通过")
                        print(f"   服务: {data.get('service', 'unknown')}")
                        print(f"   版本: {data.get('version', 'unknown')}")
                        print(f"   Verifier DID: {data.get('verifier_did', 'unknown')}")
                        return True
                    else:
                        print(f"❌ 健康检查失败: HTTP {response.status}")
                        return False
        except Exception as e:
            print(f"❌ 健康检查异常: {e}")
            return False

    async def test_basic_verification(self, holder_did: str) -> Dict:
        """基础验证测试（不带vc_hash）"""
        print("\n=== 测试1: 基础验证 ===")

        request_data = {
            "verification_type": "InspectionReport",
            "holder_did": holder_did,
            "requested_attributes": ["exporter", "inspectionPassed"]
        }

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/api/verify-vp",
                json=request_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ 验证请求已发送")
                        print(f"   Verification ID: {data.get('verification_id')}")
                        print(f"   状态: {data.get('status')}")
                        print(f"   轮询端点: {data.get('polling_endpoint')}")
                    else:
                        print(f"❌ 请求失败: HTTP {response.status}")
                        text = await response.text()
                        print(f"   错误: {text[:200]}")
        except Exception as e:
            print(f"❌ 请求异常: {e}")

    async def test_uuid_matching(self, holder_did: str) -> Dict:
        """UUID匹配测试（带vc_hash）"""
        print("\n=== 测试2: UUID匹配 ===")

        request_data = {
            "verification_type": self.vc_type,
            "holder_did": holder_did,
            "requested_attributes": ["exporter", "shippingCompany", "contractName"],
            "vc_hash": self.vc_hash
        }

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/api/verify-vp",
                json=request_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ UUID匹配验证已发送")
                        print(f"   Verification ID: {data.get('verification_id')}")
                        print(f"   状态: {data.get('status')}")
                    else:
                        print(f"❌ 请求失败: HTTP {response.status}")
                        text = await response.text()
                        print(f"   错误: {text[:200]}")
        except Exception as e:
            print(f"❌ 请求异常: {e}")

    async def poll_verification_status(self, verification_id: str, max_wait: int = 30) -> Dict:
        """轮询验证状态"""
        print(f"\n轮询验证状态 (最多等待 {max_wait}秒)...")

        start_time = time.time()
        while True:
            try:
                session = await self._get_session()
                async with session.get(f"{self.base_url}/api/verification-status/{verification_id}") as response:
                        if response.status == 200:
                            data = await response.json()
                            state = data.get('verification_result', {}).get('status', 'unknown')
                            verified = data.get('verified', False)

                            if state == 'verified':
                                print(f"✅ 验证完成: {verified}")
                                return {"success": True, "data": data}
                            elif time.time() - start_time > max_wait:
                                print(f"⏱ 超时 ({max_wait}秒）")
                                return {"success": False, "error": "timeout"}
                            else:
                                print(f"⏳ 等待中... ({int(time.time() - start_time)}秒)")
                                await asyncio.sleep(2)
                        else:
                            print(f"❌ 轮询失败: HTTP {response.status}")
                            return {"success": False, "error": f"HTTP {response.status}"}
            except Exception as e:
                print(f"❌ 轮询异常: {e}")
                return {"success": False, "error": str(e)}

    async def test_error_scenarios(self, holder_did: str) -> None:
        """错误场景测试"""
        print("\n=== 测试3: 错误场景 ===")

        # 测试1: 无效的verification_type
        print("\n--- 场景1: 无效的VC类型 ---")
        try:
            session = await self._get_session()
            async with session.post(
                    f"{self.base_url}/api/verify-vp",
                    json={
                        "verification_type": "InvalidVCType",
                        "holder_did": holder_did,
                        "requested_attributes": ["exporter"]
                    },
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 400:
                        print(f"✅ 正确返回400错误")
                    else:
                        print(f"❌ 应该返回400但实际: {response.status}")
        except Exception as e:
            print(f"❌ 请求异常: {e}")

        # 测试2: 无效的holder_did
        print("\n--- 场景2: 无效的Holder DID ---")
        try:
            session = await self._get_session()
            async with session.post(
                    f"{self.base_url}/api/verify-vp",
                    json={
                        "verification_type": "InspectionReport",
                        "holder_did": "invalid_did",
                        "requested_attributes": ["exporter"]
                    },
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 400:
                        print(f"✅ 正确返回400错误")
                    else:
                        print(f"❌ 应该返回400但实际: {response.status}")
        except Exception as e:
            print(f"❌ 请求异常: {e}")


def get_latest_vc_hash() -> tuple[str, str]:
    """从 uuid.json 获取最新的 vc_hash 和 vc_type"""
    uuid_file = Path(__file__).parent / "logs" / "uuid.json"
    if not uuid_file.exists():
        print("❌ uuid.json 文件不存在")
        return None, None

    with open(uuid_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 按时间戳排序，获取最新的
    records = [(uuid, info) for uuid, info in data.items()]
    records.sort(key=lambda x: x[1].get('timestamp', ''), reverse=True)

    if records:
        uuid, info = records[0]
        vc_hash = info.get('vc_hash')
        vc_type = info.get('vc_type')
        return vc_hash, vc_type
    return None, None


async def main():
    """主测试函数"""
    # 获取最新的 vc_hash 和 vc_type
    vc_hash, vc_type = get_latest_vc_hash()
    if not vc_hash:
        print("❌ 无法获取最新 vc_hash，退出")
        return

    print(f"✅ 使用最新 VC:")
    print(f"   类型: {vc_type}")
    print(f"   Hash: {vc_hash[:20]}...")
    print()

    tester = VPVerifierTester(vc_type, vc_hash)

    print("=" * 60)
    print("VP验证服务测试 - V6版本")
    print("=" * 60)
    print()

    # 测试配置
    holder_did = "YL2HDxkVL8qMrssaZbvtfH"

    # 执行测试
    await tester.health_check()
    await tester.test_basic_verification(holder_did)
    await tester.test_uuid_matching(holder_did)
    await tester.test_error_scenarios(holder_did)

    # 等待最后的轮询完成
    await asyncio.sleep(2)

    # 关闭
    await tester.close()

    print()
    print("=" * 60)
    print("所有测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
