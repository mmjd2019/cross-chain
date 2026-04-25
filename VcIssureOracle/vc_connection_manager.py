#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VC发行Oracle连接管理器
参考vp_verifier.py实现，提供稳定的ACA-Py连接管理
"""

import asyncio
import logging
import aiohttp
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger('vc_connection_manager')


class ACAPyConnectionError(Exception):
    """ACA-Py连接错误"""
    pass


class ConnectionManager:
    """
    ACA-Py连接管理器（单例模式）
    参考vp_verifier.py实现
    """
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        issuer_admin_url: str = "http://localhost:8080",
        holder_admin_url: str = "http://localhost:8081",
        issuer_did: str = "",
        holder_did: str = ""
    ):
        if self._initialized:
            return

        self.issuer_admin_url = issuer_admin_url.rstrip('/')
        self.holder_admin_url = holder_admin_url.rstrip('/')
        self.issuer_did = issuer_did
        self.holder_did = holder_did

        # 连接状态
        self.issuer_connected = False
        self.holder_connected = False
        self.last_health_check = None

        # 双方的连接ID（连接过程中双方各自有不同的connection_id）
        self.issuer_connection_id: Optional[str] = None
        self.holder_connection_id: Optional[str] = None

        # 连接中实际的临时DID（Pairwise DID）
        self.connection_dids = {
            'issuer': {'my_did': None, 'their_did': None},  # Issuer端的my_did和their_did
            'holder': {'my_did': None, 'their_did': None}   # Holder端的my_did和their_did
        }

        # aiohttp会话（带超时配置）
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_timeout = aiohttp.ClientTimeout(
            total=30,           # 总超时
            connect=10,         # 连接超时
            sock_read=20        # 读取超时
        )

        # 连接池配置
        self._connector = aiohttp.TCPConnector(
            limit=100,                  # 连接池大小
            limit_per_host=20,          # 每个主机的连接数
            ttl_dns_cache=300,          # DNS缓存时间
            use_dns_cache=True,
            enable_cleanup_closed=True  # 清理关闭的连接
        )

        self._initialized = True
        logger.info("ConnectionManager初始化完成")

    @property
    def session(self) -> aiohttp.ClientSession:
        """获取或创建aiohttp会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self._session_timeout,
                connector=self._connector,
                headers={"Content-Type": "application/json"}
            )
        return self._session

    async def close(self):
        """关闭连接管理器"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        if self._connector and not self._connector.closed:
            await self._connector.close()
        logger.info("ConnectionManager已关闭")

    async def check_connections(self) -> Dict[str, Any]:
        """
        检查ACA-Py连接状态（参考vp_verifier.py）
        主动健康检查，确保服务可用
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "issuer": {"connected": False, "version": None, "error": None},
            "holder": {"connected": False, "version": None, "error": None},
            "overall": False
        }

        # 检查Issuer ACA-Py
        try:
            async with self.session.get(f"{self.issuer_admin_url}/status") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result["issuer"]["connected"] = True
                    result["issuer"]["version"] = data.get("version", "unknown")
                    self.issuer_connected = True
                else:
                    result["issuer"]["error"] = f"HTTP {resp.status}"
                    self.issuer_connected = False
        except Exception as e:
            result["issuer"]["error"] = str(e)
            self.issuer_connected = False

        # 检查Holder ACA-Py
        try:
            async with self.session.get(f"{self.holder_admin_url}/status") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result["holder"]["connected"] = True
                    result["holder"]["version"] = data.get("version", "unknown")
                    self.holder_connected = True
                else:
                    result["holder"]["error"] = f"HTTP {resp.status}"
                    self.holder_connected = False
        except Exception as e:
            result["holder"]["error"] = str(e)
            self.holder_connected = False

        result["overall"] = self.issuer_connected and self.holder_connected
        self.last_health_check = datetime.now()

        return result

    async def wait_for_healthy(self, max_wait: int = 30) -> bool:
        """等待ACA-Py服务健康"""
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < max_wait:
            health = await self.check_connections()
            if health["overall"]:
                logger.info("ACA-Py服务健康检查通过")
                return True
            logger.warning("ACA-Py服务未就绪，等待重试...")
            await asyncio.sleep(2)
        return False


    # ========== 连接管理方法 ==========
    async def get_existing_active_connection(self) -> Optional[str]:
        """获取已有的active连接，并保存双方connection_id和DID信息"""
        try:
            # 1. 查询Issuer端的active连接
            async with self.session.get(
                f"{self.issuer_admin_url}/connections"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    connections = data.get('results', [])

                    for conn in connections:
                        if conn.get('state') == 'active':
                            self.issuer_connection_id = conn.get('connection_id')
                            self.connection_dids['issuer']['my_did'] = conn.get('my_did')
                            self.connection_dids['issuer']['their_did'] = conn.get('their_did')
                            logger.info(f"找到Issuer端active连接: {self.issuer_connection_id}")
                            logger.info(f"  Issuer my_did: {self.connection_dids['issuer']['my_did']}")
                            logger.info(f"  Issuer their_did: {self.connection_dids['issuer']['their_did']}")

                            # 2. 查询Holder端对应的连接
                            await self._find_holder_connection()
                            return self.issuer_connection_id

                    logger.debug("未找到active状态的连接")
                return None
        except Exception as e:
            logger.warning(f"获取已有连接时出错: {e}")
            return None

    async def _find_holder_connection(self) -> bool:
        """根据Issuer端的their_did查找Holder端对应的连接"""
        try:
            issuer_their_did = self.connection_dids['issuer'].get('their_did')
            if not issuer_their_did:
                return False

            async with self.session.get(
                f"{self.holder_admin_url}/connections"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    connections = data.get('results', [])

                    for conn in connections:
                        # Holder端的my_did应该等于Issuer端的their_did
                        if conn.get('my_did') == issuer_their_did:
                            self.holder_connection_id = conn.get('connection_id')
                            self.connection_dids['holder']['my_did'] = conn.get('my_did')
                            self.connection_dids['holder']['their_did'] = conn.get('their_did')
                            logger.info(f"找到Holder端对应连接: {self.holder_connection_id}")
                            logger.info(f"  Holder my_did: {self.connection_dids['holder']['my_did']}")
                            logger.info(f"  Holder their_did: {self.connection_dids['holder']['their_did']}")
                            return True

            logger.warning("未找到Holder端对应的连接")
            return False
        except Exception as e:
            logger.warning(f"查找Holder连接时出错: {e}")
            return False

    async def create_invitation(self, alias: str = "vc-issuer") -> Optional[Dict]:
        """创建连接邀请"""
        try:
            async with self.session.post(
                f"{self.issuer_admin_url}/connections/create-invitation",
                json={"auto_accept": True, "multi_use": False, "alias": alias}
            ) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    logger.info(f"创建邀请成功: {data.get('connection_id')}")
                    return data
                else:
                    error_text = await response.text()
                    raise ACAPyConnectionError(f"创建邀请失败: {response.status} - {error_text}")
        except Exception as e:
            logger.error(f"创建邀请失败: {e}")
            raise

    async def receive_invitation(self, invitation: Dict, my_did: Optional[str] = None) -> Optional[Dict]:
        """接收连接邀请"""
        try:
            params = {
                "auto_accept": "true",
                "alias": "vc-holder",
                "my_endpoint": "http://192.168.1.27:8001"  # 设置Holder的endpoint
            }
            if my_did:
                params["my_did"] = my_did

            async with self.session.post(
                f"{self.holder_admin_url}/connections/receive-invitation",
                json=invitation,
                params=params
            ) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    logger.info(f"接收邀请成功: {data.get('connection_id')}")
                    return data
                else:
                    error_text = await response.text()
                    raise ACAPyConnectionError(f"接收邀请失败: {response.status} - {error_text}")
        except Exception as e:
            logger.error(f"接收邀请失败: {e}")
            raise

    async def wait_for_connection_active(
        self,
        connection_id: str,
        max_wait: int = 30,
        check_interval: float = 1.0
    ) -> bool:
        """等待Issuer端连接变为response或active状态（HTTP模式可能无法达到active）"""
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < max_wait:
            try:
                async with self.session.get(
                    f"{self.issuer_admin_url}/connections/{connection_id}"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        state = data.get('state')

                        if state == 'active':
                            logger.info(f"Issuer端连接已active: {connection_id}")
                            # 保存Issuer端连接信息
                            self.issuer_connection_id = connection_id
                            self.connection_dids['issuer']['my_did'] = data.get('my_did')
                            self.connection_dids['issuer']['their_did'] = data.get('their_did')
                            logger.info(f"  Issuer my_did: {self.connection_dids['issuer']['my_did']}")
                            logger.info(f"  Issuer their_did: {self.connection_dids['issuer']['their_did']}")

                            # 查找Holder端对应的连接
                            await self._find_holder_connection()
                            return True
                        elif state == 'response':
                            # HTTP模式下，连接可能停留在response状态
                            # 检查是否可以继续使用这个连接
                            logger.info(f"Issuer端连接处于response状态（HTTP模式）: {connection_id}")
                            # 保存Issuer端连接信息
                            self.issuer_connection_id = connection_id
                            self.connection_dids['issuer']['my_did'] = data.get('my_did')
                            self.connection_dids['issuer']['their_did'] = data.get('their_did')
                            logger.info(f"  Issuer my_did: {self.connection_dids['issuer']['my_did']}")
                            logger.info(f"  Issuer their_did: {self.connection_dids['issuer']['their_did']}")
                            logger.warning("⚠️ HTTP连接模式可能无法完成凭证交换，建议使用WebSocket")

                            # 查找Holder端对应的连接
                            await self._find_holder_connection()
                            return True
                        elif state == 'error':
                            error_msg = data.get('error_msg', 'Unknown error')
                            raise ACAPyConnectionError(f"连接错误: {error_msg}")

                    await asyncio.sleep(check_interval)
            except Exception as e:
                logger.warning(f"检查连接状态时出错: {e}")
                await asyncio.sleep(check_interval)

        raise ACAPyConnectionError(f"等待连接active超时({max_wait}秒)")

    async def get_or_create_connection(self, max_wait: int = 30) -> Optional[str]:
        """
        获取或创建ACA-Py连接（增强版）
        参考vp_verifier.py的连接管理策略
        """
        # 1. 首先检查ACA-Py服务是否健康
        if not await self.wait_for_healthy(max_wait=10):
            raise ACAPyConnectionError("ACA-Py服务未就绪")

        # 2. 查找现有active连接
        existing = await self.get_existing_active_connection()
        if existing:
            logger.info(f"使用现有连接: {existing}")
            return existing

        # 3. 创建新连接
        logger.info("未找到active连接，创建新连接...")

        # 创建邀请
        invitation_data = await self.create_invitation()
        connection_id = invitation_data.get('connection_id')
        invitation = invitation_data.get('invitation')

        # 接收邀请
        await self.receive_invitation(invitation, self.holder_did)

        # 等待连接active
        await self.wait_for_connection_active(connection_id, max_wait=max_wait)

        return connection_id

    async def delete_all_connections(self, admin_url: str) -> int:
        """删除指定端的所有连接（带重试）"""
        deleted_count = 0
        try:
            async with self.session.get(f"{admin_url}/connections") as response:
                if response.status != 200:
                    return 0

                data = await response.json()
                connections = data.get('results', [])

                for conn in connections:
                    conn_id = conn.get('connection_id')
                    try:
                        # 使用DELETE方法，比POST /remove更可靠
                        async with self.session.delete(
                            f"{admin_url}/connections/{conn_id}"
                        ) as del_response:
                            if del_response.status in [200, 201, 204]:
                                deleted_count += 1
                    except Exception as e:
                        logger.warning(f"删除连接 {conn_id} 失败: {e}")

                logger.info(f"已删除 {deleted_count}/{len(connections)} 个连接")
                return deleted_count
        except Exception as e:
            logger.error(f"删除连接失败: {e}")
            return 0

    async def reset_connections(self):
        """重置所有连接"""
        logger.info("=" * 80)
        logger.info("开始重置ACA-Py连接...")
        logger.info("=" * 80)

        issuer_deleted = await self.delete_all_connections(self.issuer_admin_url)
        holder_deleted = await self.delete_all_connections(self.holder_admin_url)

        logger.info(f"已删除连接: Issuer={issuer_deleted}, Holder={holder_deleted}")

        new_conn_id = await self.get_or_create_connection()
        if new_conn_id:
            logger.info(f"✓ 连接重置完成，新连接ID: {new_conn_id}")
        else:
            logger.error("✗ 连接重置失败")

        logger.info("=" * 80)

    # ========== 凭证交换相关方法 ==========
    async def send_credential_offer_v2(
        self,
        connection_id: str,
        cred_def_id: str,
        attributes: Dict[str, str]
    ) -> Optional[Dict]:
        """发送凭证提供 (Issue Credential v2.0协议)"""
        attr_list = [{"name": name, "value": str(value)} for name, value in attributes.items()]

        # v2.0 API格式：filter (singular) 对象，包含indy
        offer_data = {
            "connection_id": connection_id,
            "comment": "VC发行",
            "credential_preview": {
                "@type": "https://didcomm.org/issue-credential/2.0/credential-preview",
                "attributes": attr_list
            },
            "filter": {
                "indy": {
                    "cred_def_id": cred_def_id
                }
            }
        }

        try:
            async with self.session.post(
                f"{self.issuer_admin_url}/issue-credential-2.0/send-offer",
                json=offer_data
            ) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    # v2.0 API返回的是thread_id，也可以用作为cred_ex_id
                    cred_ex_id = data.get("thread_id") or data.get("cred_ex_id")
                    logger.info(f"凭证提供发送成功 (v2.0): {cred_ex_id}")
                    return data
                else:
                    error_text = await response.text()
                    raise ACAPyConnectionError(f"发送凭证提供失败: {response.status} - {error_text}")
        except Exception as e:
            logger.error(f"发送凭证提供失败: {e}")
            raise

    async def get_credential_exchange_v2(self, cred_ex_id: str) -> Optional[Dict]:
        """获取凭证交换记录 (v2.0 API)"""
        try:
            # 首先尝试直接获取
            async with self.session.get(
                f"{self.issuer_admin_url}/issue-credential-2.0/records/{cred_ex_id}"
            ) as response:
                if response.status == 200:
                    return await response.json()

            # 如果直接获取失败，列出所有记录并找到匹配thread_id的记录
            async with self.session.get(
                f"{self.issuer_admin_url}/issue-credential-2.0/records"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    records = data.get('results', [])
                    logger.info(f"v2.0凭证记录列表: 共{len(records)}条记录")

                    # v2.0 API使用cred_ex_record嵌套结构
                    for i, result in enumerate(records[:3]):
                        cred_ex_record = result.get('cred_ex_record', {})
                        thread_id = cred_ex_record.get('thread_id')
                        state = cred_ex_record.get('state')
                        logger.info(f"  记录{i+1}: thread_id={thread_id}, state={state}")

                    # 查找thread_id匹配的记录
                    for result in records:
                        cred_ex_record = result.get('cred_ex_record', {})
                        if cred_ex_record.get('thread_id') == cred_ex_id:
                            logger.info(f"找到匹配thread_id的记录: {cred_ex_id}")
                            # 返回cred_ex_record的内容，它包含schema_id等字段
                            return cred_ex_record

                    logger.warning(f"未找到匹配thread_id的记录: {cred_ex_id}")
                    return None

                logger.warning(f"获取v2.0凭证记录列表失败: status={response.status}")
                return None
        except Exception as e:
            logger.warning(f"获取凭证交换记录失败: {e}")
            return None

    async def get_holder_credential_exchanges_v2(self, connection_id: Optional[str] = None) -> list:
        """获取Holder端凭证交换记录 (v2.0 API)

        Args:
            connection_id: Holder端的connection_id，默认使用self.holder_connection_id
        """
        try:
            # 使用传入的connection_id或全局保存的holder_connection_id
            target_conn_id = connection_id or self.holder_connection_id

            async with self.session.get(
                f"{self.holder_admin_url}/issue-credential-2.0/records"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    records = data.get('results', [])

                    # 如果指定了connection_id，只返回该连接的记录
                    if target_conn_id:
                        filtered = [r for r in records if r.get('connection_id') == target_conn_id]
                        return filtered

                    return records
                return []
        except Exception as e:
            logger.warning(f"获取Holder凭证记录失败: {e}")
            return []

    async def send_holder_request_v2(self, holder_cred_ex_id: str) -> bool:
        """触发Holder发送凭证请求 (v2.0 API)"""
        try:
            async with self.session.post(
                f"{self.holder_admin_url}/issue-credential-2.0/records/{holder_cred_ex_id}/send-request",
                json={}
            ) as response:
                if response.status in [200, 201]:
                    logger.info(f"Holder请求发送成功 (v2.0): {holder_cred_ex_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"发送请求失败: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"发送请求时出错: {e}")
            return False

    async def store_holder_credential_v2(self, holder_cred_ex_id: str) -> bool:
        """手动触发Holder存储凭证 (v2.0 API)"""
        try:
            async with self.session.post(
                f"{self.holder_admin_url}/issue-credential-2.0/records/{holder_cred_ex_id}/store",
                json={}
            ) as response:
                if response.status in [200, 201]:
                    logger.info(f"Holder凭证存储成功 (v2.0): {holder_cred_ex_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"存储凭证失败: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"存储凭证时出错: {e}")
            return False

    async def issue_credential_v2(self, issuer_cred_ex_id: str) -> bool:
        """颁发凭证 (v2.0 API)"""
        try:
            async with self.session.post(
                f"{self.issuer_admin_url}/issue-credential-2.0/records/{issuer_cred_ex_id}/issue",
                json={}
            ) as response:
                if response.status in [200, 201]:
                    logger.info(f"凭证颁发成功 (v2.0): {issuer_cred_ex_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"颁发凭证失败: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"颁发凭证时出错: {e}")
            return False


# 全局连接管理器实例
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager(
    issuer_admin_url: str = "http://localhost:8080",
    holder_admin_url: str = "http://localhost:8081",
    issuer_did: str = "",
    holder_did: str = ""
) -> ConnectionManager:
    """获取全局连接管理器实例（工厂函数）"""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager(
            issuer_admin_url=issuer_admin_url,
            holder_admin_url=holder_admin_url,
            issuer_did=issuer_did,
            holder_did=holder_did
        )
    return _connection_manager


async def close_connection_manager():
    """关闭全局连接管理器"""
    global _connection_manager
    if _connection_manager:
        await _connection_manager.close()
        _connection_manager = None
