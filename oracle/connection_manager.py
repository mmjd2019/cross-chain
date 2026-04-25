#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
连接管理器
管理Verifier与Holder之间的Aries连接
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from acapy_client import ACAPyClient


logger = logging.getLogger(__name__)


class ConnectionManagerError(Exception):
    """连接管理器错误"""
    pass


class ConnectionNotFoundError(ConnectionManagerError):
    """连接不存在错误"""
    pass


class ConnectionTimeoutError(ConnectionManagerError):
    """连接超时错误"""
    pass


class ConnectionManager:
    """
    Aries连接管理器

    负责：
    - 在Verifier和Holder之间建立连接
    - 连接复用（避免重复创建）
    - 连接状态监控
    - 清理过期连接
    """

    # 连接状态常量
    STATE_INIT = "init"
    STATE_INVITATION = "invitation"
    STATE_REQUEST = "request"
    STATE_RESPONSE = "response"
    STATE_ACTIVE = "active"
    STATE_ERROR = "error"
    STATE_COMPLETED = "completed"

    def __init__(
        self,
        verifier_admin_url: str,
        holder_admin_url: str,
        cleanup_interval_seconds: int = 300,
        connection_ttl_seconds: int = 3600
    ):
        """
        初始化连接管理器

        参数:
            verifier_admin_url: Verifier ACA-Py管理URL
            holder_admin_url: Holder ACA-Py管理URL
            cleanup_interval_seconds: 清理间隔（秒）
            connection_ttl_seconds: 连接存活时间（秒）
        """
        self.verifier_client = ACAPyClient(verifier_admin_url, "verifierWallet")
        self.holder_client = ACAPyClient(holder_admin_url, "holderWallet")

        self.cleanup_interval = cleanup_interval_seconds
        self.connection_ttl = timedelta(seconds=connection_ttl_seconds)

        # 连接缓存: holder_did -> (connection_id, created_at)
        self._connections: Dict[str, tuple] = {}

        # 清理任务
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info("连接管理器初始化完成")

    async def wait_for_connection_active(
        self,
        connection_id: str,
        timeout_seconds: int = 30,
        check_interval_seconds: float = 1.0
    ) -> bool:
        """
        等待连接变为活跃状态

        适用于 ACA-Py 0.8.2+，连接应该能正常达到 active 状态。

        参数:
            connection_id: 连接ID
            timeout_seconds: 超时时间
            check_interval_seconds: 检查间隔

        返回:
            是否成功激活
        """
        logger.info(f"等待连接激活: {connection_id}, 超时: {timeout_seconds}秒")
        start_time = datetime.now()
        deadline = start_time + timedelta(seconds=timeout_seconds)

        while datetime.now() < deadline:
            try:
                # 使用 AIP 2.0 API 获取连接
                endpoint = f"/connections/{connection_id}"
                resp = await self.verifier_client.session.get(
                    f"{self.verifier_client.admin_url}{endpoint}"
                )

                if resp.status == 200:
                    conn_data = await resp.json()
                    state = conn_data.get("state")
                    their_did = conn_data.get("their_did")
                    my_did = conn_data.get("my_did")

                    logger.debug(f"连接状态: {state}, my_did: {my_did}, their_did: {their_did}")

                    if state == self.STATE_ACTIVE:
                        logger.info(f"连接已激活: {connection_id}")
                        return True
                    # AIP 2.0 中，response 状态也可能可用
                    elif state == self.STATE_RESPONSE:
                        logger.info(f"连接已就绪 (response): {connection_id}")
                        return True
                    elif state == self.STATE_ERROR:
                        error_msg = conn_data.get("error", "Unknown error")
                        raise ConnectionError(f"连接进入错误状态: {error_msg}")
                    elif state in [self.STATE_COMPLETED, "deleted"]:
                        raise ConnectionError(f"连接已完成或删除: {state}")

                await asyncio.sleep(check_interval_seconds)

            except Exception as e:
                logger.warning(f"检查连接状态失败: {e}")
                await asyncio.sleep(check_interval_seconds)

        raise ConnectionTimeoutError(
            f"连接在 {timeout_seconds} 秒内未激活: {connection_id}"
        )

    async def start(self):
        """启动连接管理器（开始后台清理任务）"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info(f"连接管理器已启动，清理间隔: {self.cleanup_interval}秒")

    async def stop(self):
        """停止连接管理器"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("连接管理器已停止")

        await self.verifier_client.close()
        await self.holder_client.close()

    async def get_or_create_connection(
        self,
        holder_did: Optional[str] = None,
        timeout_seconds: int = 30
    ) -> str:
        """
        获取或创建连接

        参数:
            holder_did: Holder的DID（可选，用于查找现有连接）
            timeout_seconds: 等待连接激活的超时时间

        返回:
            connection_id

        异常:
            ConnectionTimeoutError: 连接超时
            ConnectionManagerError: 连接失败
        """
        # 尝试查找现有连接
        if holder_did:
            existing_connection = await self.find_existing_connection(holder_did)
            if existing_connection:
                logger.info(f"复用现有连接: {existing_connection} (holder_did={holder_did})")
                return existing_connection

        # 创建新连接
        logger.info(f"创建新连接" + (f" (holder_did={holder_did})" if holder_did else ""))
        connection_id = await self.create_new_connection(holder_did, timeout_seconds)

        # 缓存连接
        if holder_did:
            self._connections[holder_did] = (connection_id, datetime.now())

        # 等待连接激活（新连接创建后）
        await self.wait_for_connection_active(connection_id, timeout_seconds=15)

        return connection_id

    async def find_existing_connection(self, holder_did: str) -> Optional[str]:
        """
        查找与指定Holder的现有活跃连接

        使用连接alias来匹配holder_did，实现连接隔离。
        每个不同的holder_did会使用独立的连接。

        参数:
            holder_did: Holder的DID（用于连接隔离和缓存查找）

        返回:
            connection_id，如果未找到返回None
        """
        # 先从缓存中查找
        if holder_did in self._connections:
            cached_connection_id, created_at = self._connections[holder_did]

            # 检查是否过期
            if datetime.now() - created_at < self.connection_ttl:
                # 验证连接仍然可用
                try:
                    connection = await self.verifier_client.get_connection(cached_connection_id)
                    state = connection.get("state")

                    # ACA-Py 0.8.2+: 只接受active状态
                    if state == self.STATE_ACTIVE:
                        logger.debug(f"从缓存找到活跃连接: {cached_connection_id} (holder_did={holder_did})")
                        return cached_connection_id
                    else:
                        logger.warning(f"缓存的连接不可用: {cached_connection_id}, state={state}")
                        del self._connections[holder_did]
                except Exception as e:
                    logger.warning(f"验证缓存连接失败: {e}")
                    del self._connections[holder_did]
            else:
                logger.debug(f"缓存的连接已过期: {cached_connection_id}")
                del self._connections[holder_did]

        # 从ACA-Py查询与指定alias匹配的连接
        expected_alias = f"holder-{holder_did[:8]}"
        try:
            all_connections = await self.verifier_client.get_connections()

            # 查找匹配预期alias的活跃连接
            for conn in all_connections:
                conn_id = conn.get("connection_id")
                state = conn.get("state")
                alias = conn.get("their_label", "")

                if state == self.STATE_ACTIVE and alias == expected_alias:
                    logger.info(f"从ACA-Py找到匹配的活跃连接: {conn_id} (alias={alias}, holder_did={holder_did})")
                    # 更新缓存
                    self._connections[holder_did] = (conn_id, datetime.now())
                    return conn_id

            logger.debug(f"未找到holder_did={holder_did}对应的活跃连接 (expected_alias={expected_alias})")
            return None

        except Exception as e:
            logger.error(f"查询连接失败: {e}")

        return None

    async def find_connection_by_label(self, their_label: str) -> Optional[Dict]:
        """
        通过 their_label 查找连接

        参数:
            their_label: Holder的标签（如 "Holder.Agent"）

        返回:
            连接信息字典，包含 connection_id, their_did 等，如果未找到返回None
        """
        try:
            all_connections = await self.verifier_client.get_connections()

            for conn in all_connections:
                if conn.get("their_label") == their_label and conn.get("state") == self.STATE_ACTIVE:
                    conn_id = conn.get("connection_id")
                    their_did = conn.get("their_did")
                    logger.info(f"通过标签找到连接: label={their_label}, connection_id={conn_id}, their_did={their_did}")
                    return conn

            logger.warning(f"未找到标签为 '{their_label}' 的活跃连接")
            return None

        except Exception as e:
            logger.error(f"通过标签查询连接失败: {e}")
            return None

    async def find_connection_by_their_did(self, their_did: str) -> Optional[Dict]:
        """
        通过 their_did (Peer DID) 查找连接

        参数:
            their_did: 对端的DID

        返回:
            连接信息字典，如果未找到返回None
        """
        try:
            all_connections = await self.verifier_client.get_connections()

            for conn in all_connections:
                if conn.get("their_did") == their_did and conn.get("state") == self.STATE_ACTIVE:
                    conn_id = conn.get("connection_id")
                    logger.info(f"通过their_did找到连接: their_did={their_did}, connection_id={conn_id}")
                    return conn

            logger.warning(f"未找到their_did为 '{their_did}' 的活跃连接")
            return None

        except Exception as e:
            logger.error(f"通过their_did查询连接失败: {e}")
            return None

    async def create_new_connection(
        self,
        holder_did: Optional[str],
        timeout_seconds: int = 30,
        max_attempts: int = 2
    ) -> str:
        """
        创建新的Aries连接（带重试）

        参数:
            holder_did: Holder的DID（用于连接别名）
            timeout_seconds: 等待连接激活的超时时间
            max_attempts: 最大尝试次数

        返回:
            connection_id

        异常:
            ConnectionTimeoutError: 连接超时
            ConnectionManagerError: 连接失败
        """
        for attempt in range(max_attempts):
            try:
                # Verifier创建邀请
                alias = f"holder-{holder_did[:8]}" if holder_did else f"holder-{datetime.now().strftime('%H%M%S')}"
                invitation_response = await self.verifier_client.create_invitation(
                    auto_accept=True,
                    multi_use=False,
                    alias=alias
                )

                connection_id = invitation_response.get("connection_id")
                invitation = invitation_response.get("invitation")

                if not connection_id or not invitation:
                    raise ConnectionManagerError("创建邀请失败：未返回connection_id或invitation")

                logger.info(f"Verifier创建邀请成功, connection_id={connection_id}, alias={alias}")

                # Holder接收邀请
                holder_alias = f"verifier-{alias}"
                holder_response = await self.holder_client.receive_invitation(
                    invitation=invitation,
                    alias=holder_alias,
                    auto_accept=True
                )

                logger.info(f"Holder接收邀请成功")

                # 等待连接激活
                await self.wait_for_connection_active(connection_id, timeout_seconds)

                logger.info(f"新连接已激活: {connection_id}")
                return connection_id

            except ConnectionTimeoutError as e:
                if attempt < max_attempts - 1:
                    wait_time = 5 * (attempt + 1)  # 5秒, 10秒
                    logger.warning(
                        f"连接创建超时（尝试{attempt + 1}/{max_attempts}），"
                        f"{wait_time}秒后重试..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"连接创建超时，已重试{max_attempts}次")
                    raise
            except Exception as e:
                # 其他异常不重试
                logger.error(f"创建连接失败: {e}", exc_info=True)
                raise ConnectionManagerError(f"创建连接失败: {e}")

    async def wait_for_connection_active(
        self,
        connection_id: str,
        timeout_seconds: int = 30,
        check_interval_seconds: float = 1.0
    ) -> bool:
        """
        等待连接变为活跃状态

        适用于ACA-Py 0.8.2+，连接应该能正常达到active状态。

        参数:
            connection_id: 连接ID
            timeout_seconds: 超时时间
            check_interval_seconds: 检查间隔

        返回:
            是否成功激活

        异常:
            ConnectionTimeoutError: 超时未激活
            ConnectionManagerError: 连接错误
        """
        start_time = datetime.now()
        deadline = start_time + timedelta(seconds=timeout_seconds)

        logger.info(f"等待连接激活: {connection_id}, 超时: {timeout_seconds}秒")

        while datetime.now() < deadline:
            try:
                connection = await self.verifier_client.get_connection(connection_id)
                state = connection.get("state")
                my_did = connection.get("my_did")
                their_did = connection.get("their_did")
                rfc23_state = connection.get("rfc23_state", "")

                logger.debug(f"连接状态: {connection_id} -> {state} (rfc23: {rfc23_state})")

                if state == self.STATE_ACTIVE:
                    logger.info(f"连接已激活: {connection_id}")
                    return True

                elif state == self.STATE_RESPONSE:
                    # ACA-Py 0.8.2中，尝试发送ping来促进连接激活
                    if my_did and their_did:
                        logger.debug(f"连接处于response状态，尝试发送ping: {connection_id}")
                        try:
                            await self.verifier_client.send_ping(connection_id)
                            await asyncio.sleep(1)
                            # 继续循环检查状态
                            continue
                        except Exception as e:
                            logger.debug(f"发送ping失败: {e}")

                elif state == self.STATE_ERROR:
                    error_msg = connection.get("error", "Unknown error")
                    raise ConnectionManagerError(f"连接进入错误状态: {error_msg}")

                elif state in [self.STATE_COMPLETED, "deleted"]:
                    raise ConnectionManagerError(f"连接已完成或删除: {state}")

                # 继续等待
                await asyncio.sleep(check_interval_seconds)

            except ConnectionManagerError:
                raise
            except Exception as e:
                logger.warning(f"检查连接状态失败: {e}")
                await asyncio.sleep(check_interval_seconds)

        # 超时
        raise ConnectionTimeoutError(
            f"连接在 {timeout_seconds} 秒内未激活: {connection_id}"
        )

    async def get_connection_state(self, connection_id: str) -> str:
        """
        获取连接状态

        参数:
            connection_id: 连接ID

        返回:
            连接状态字符串
        """
        try:
            connection = await self.verifier_client.get_connection(connection_id)
            return connection.get("state", "unknown")
        except Exception as e:
            logger.error(f"获取连接状态失败: {e}")
            return "error"

    async def delete_connection(self, connection_id: str) -> bool:
        """
        删除连接

        参数:
            connection_id: 连接ID

        返回:
            是否成功
        """
        try:
            # 从缓存中移除
            to_remove = []
            for holder_did, (conn_id, _) in self._connections.items():
                if conn_id == connection_id:
                    to_remove.append(holder_did)

            for holder_did in to_remove:
                del self._connections[holder_did]

            # 从ACA-Py删除
            await self.verifier_client.delete_connection(connection_id)

            logger.info(f"连接已删除: {connection_id}")
            return True

        except Exception as e:
            logger.error(f"删除连接失败: {e}")
            return False

    async def cleanup_inactive_connections(self):
        """
        清理不活跃的连接
        """
        logger.info("开始清理不活跃连接")

        try:
            # 获取所有连接
            all_connections = await self.verifier_client.get_connections()

            cleaned_count = 0
            for conn in all_connections:
                conn_id = conn.get("connection_id")
                state = conn.get("state")

                # 删除非活跃状态的连接
                if state not in [self.STATE_ACTIVE, self.STATE_REQUEST, self.STATE_RESPONSE]:
                    try:
                        await self.verifier_client.delete_connection(conn_id)
                        cleaned_count += 1
                        logger.info(f"清理不活跃连接: {conn_id} (state={state})")
                    except Exception as e:
                        logger.warning(f"清理连接失败: {conn_id}, {e}")

            logger.info(f"清理完成，共清理 {cleaned_count} 个不活跃连接")

        except Exception as e:
            logger.error(f"清理连接失败: {e}")

    async def _cleanup_loop(self):
        """后台清理循环"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_inactive_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理循环出错: {e}", exc_info=True)

    def get_connection_stats(self) -> Dict:
        """
        获取连接统计信息

        返回:
            统计字典
        """
        return {
            "cached_connections": len(self._connections),
            "connection_ttl_seconds": self.connection_ttl.total_seconds(),
            "cleanup_interval_seconds": self.cleanup_interval,
            "holder_dids": list(self._connections.keys())
        }

    async def _verify_connection_usable(self, connection_id: str) -> bool:
        """
        验证连接是否可用于Present Proof协议 (ACA-Py 0.8.2+)

        参数:
            connection_id: 连接ID

        返回:
            是否可用
        """
        try:
            # 获取连接信息
            conn = await self.verifier_client.get_connection(connection_id)

            # 检查DID是否已交换
            my_did = conn.get('my_did')
            their_did = conn.get('their_did')

            if not my_did:
                logger.warning(f"连接缺少my_did: {connection_id}")
                return False

            if not their_did:
                logger.warning(f"连接缺少their_did: {connection_id}")
                return False

            # ACA-Py 0.8.2+: 只接受active状态
            state = conn.get('state')
            if state != self.STATE_ACTIVE:
                logger.warning(f"连接状态不可用: {state} (需要active)")
                return False

            # 发送ping测试连接是否响应
            try:
                await self.verifier_client.send_ping(connection_id)
                logger.info(f"连接可用性测试成功: {connection_id}")
                return True
            except Exception as e:
                logger.warning(f"Ping测试失败: {e}")
                return False

        except Exception as e:
            logger.error(f"验证连接可用性失败: {e}")
            return False

    async def diagnose_connection(self, connection_id: str) -> Dict:
        """
        诊断连接问题 (ACA-Py 0.8.2+)

        参数:
            connection_id: 连接ID

        返回:
            诊断信息字典
        """
        try:
            conn = await self.verifier_client.get_connection(connection_id)

            diagnosis = {
                "connection_id": connection_id,
                "state": conn.get("state"),
                "rfc23_state": conn.get("rfc23_state", ""),
                "my_did": conn.get("my_did"),
                "their_did": conn.get("their_did"),
                "their_label": conn.get("their_label"),
                "invitation_mode": conn.get("invitation_mode"),
                "created_at": conn.get("created_at"),
                "updated_at": conn.get("updated_at"),
                "issues": [],
                "usable": False
            }

            # 检查DID
            if not diagnosis["my_did"]:
                diagnosis["issues"].append("缺少my_did")
            if not diagnosis["their_did"]:
                diagnosis["issues"].append("缺少their_did")

            # ACA-Py 0.8.2+: 只接受active状态
            if diagnosis["state"] == self.STATE_ACTIVE:
                diagnosis["usable"] = True
            else:
                diagnosis["issues"].append(f"连接状态异常: {diagnosis['state']} (需要active)")

            return diagnosis

        except Exception as e:
            return {
                "connection_id": connection_id,
                "error": str(e),
                "usable": False,
                "issues": [f"诊断失败: {e}"]
            }

