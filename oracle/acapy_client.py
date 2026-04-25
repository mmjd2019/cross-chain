#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ACA-Py API客户端
封装ACA-Py的HTTP API调用，支持Present Proof协议和连接管理
"""

import asyncio
import logging
from typing import Dict, Optional, List, Any, Callable, TypeVar

import aiohttp


logger = logging.getLogger(__name__)


class ACAPyClientError(Exception):
    """ACA-Py客户端错误基类"""
    pass


class ACAPyConnectionError(ACAPyClientError):
    """连接错误"""
    pass


class ACAPyAPIError(ACAPyClientError):
    """API调用错误"""
    pass


T = TypeVar('T')


async def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (aiohttp.ClientError, ACAPyConnectionError)
) -> T:
    """
    带指数退避的重试装饰器

    参数:
        func: 要重试的异步函数
        max_retries: 最大重试次数
        initial_delay: 初始延迟时间（秒）
        backoff_factor: 退避因子
        exceptions: 需要重试的异常类型

    返回:
        函数执行结果
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e

            if attempt == max_retries:
                logger.error(
                    f"操作失败，已重试{max_retries}次: {e}"
                )
                raise

            logger.warning(
                f"操作失败（尝试{attempt + 1}/{max_retries + 1}），"
                f"{delay}秒后重试: {e}"
            )
            await asyncio.sleep(delay)
            delay *= backoff_factor

    raise last_exception



class ACAPyClient:
    """
    ACA-Py API客户端

    封装与ACA-Py实例的所有HTTP交互，包括：
    - Present Proof协议（发送证明请求、获取验证状态）
    - 连接管理（创建邀请、接收邀请、查询连接）
    """

    def __init__(self, admin_url: str, wallet_name: str, timeout: int = 30):
        """
        初始化ACA-Py客户端

        参数:
            admin_url: ACA-Py管理API URL（如 http://localhost:8082）
            wallet_name: 钱包名称
            timeout: HTTP请求超时时间（秒）
        """
        self.admin_url = admin_url.rstrip('/')
        self.wallet_name = wallet_name
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self):
        """关闭HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        发送GET请求（带重试）

        参数:
            endpoint: API端点（如 /connections）
            params: URL查询参数

        返回:
            响应JSON数据

        异常:
            ACAPyConnectionError: 连接失败
            ACAPyAPIError: API返回错误
        """
        async def _do_get():
            session = await self._get_session()
            url = f"{self.admin_url}{endpoint}"

            logger.debug(f"GET {url} params={params}")
            async with session.get(url, params=params) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    logger.error(f"GET {url} failed: {response.status} - {error_text}")
                    raise ACAPyAPIError(f"API error {response.status}: {error_text}")

                data = await response.json()
                logger.debug(f"GET {url} response: {data}")
                return data

        try:
            return await retry_with_backoff(
                _do_get,
                max_retries=3,
                initial_delay=1.0,
                exceptions=(aiohttp.ClientError, ACAPyConnectionError)
            )
        except Exception as e:
            logger.error(f"Connection error GET {endpoint}: {e}")
            raise ACAPyConnectionError(f"Failed to connect to {self.admin_url}{endpoint}: {e}")

    async def _post(self, endpoint: str, json_data: Optional[Dict] = None) -> Dict:
        """
        发送POST请求（带重试）

        参数:
            endpoint: API端点
            json_data: 请求体JSON数据

        返回:
            响应JSON数据
        """
        async def _do_post():
            session = await self._get_session()
            url = f"{self.admin_url}{endpoint}"

            logger.debug(f"POST {url} data={json_data}")
            async with session.post(url, json=json_data) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    logger.error(f"POST {url} failed: {response.status} - {error_text}")
                    raise ACAPyAPIError(f"API error {response.status}: {error_text}")

                data = await response.json()
                logger.debug(f"POST {url} response: {data}")
                return data

        try:
            return await retry_with_backoff(
                _do_post,
                max_retries=3,
                initial_delay=1.0,
                exceptions=(aiohttp.ClientError, ACAPyConnectionError)
            )
        except Exception as e:
            logger.error(f"Connection error POST {endpoint}: {e}")
            raise ACAPyConnectionError(f"Failed to connect to {self.admin_url}{endpoint}: {e}")

    async def _delete(self, endpoint: str) -> Dict:
        """
        发送DELETE请求（带重试）

        参数:
            endpoint: API端点

        返回:
            响应JSON数据
        """
        async def _do_delete():
            session = await self._get_session()
            url = f"{self.admin_url}{endpoint}"

            logger.debug(f"DELETE {url}")
            async with session.delete(url) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    logger.error(f"DELETE {url} failed: {response.status} - {error_text}")
                    raise ACAPyAPIError(f"API error {response.status}: {error_text}")

                # DELETE可能返回204无内容
                if response.status == 204:
                    return {}

                data = await response.json()
                logger.debug(f"DELETE {url} response: {data}")
                return data

        try:
            return await retry_with_backoff(
                _do_delete,
                max_retries=3,
                initial_delay=1.0,
                exceptions=(aiohttp.ClientError, ACAPyConnectionError)
            )
        except Exception as e:
            logger.error(f"Connection error DELETE {endpoint}: {e}")
            raise ACAPyConnectionError(f"Failed to connect to {self.admin_url}{endpoint}: {e}")

    # ==================== Present Proof 协议 ====================

    async def send_proof_request(
        self,
        connection_id: str,
        proof_request: Dict,
        comment: Optional[str] = None
    ) -> str:
        """
        发送证明请求给Holder

        参数:
            connection_id: Aries连接ID
            proof_request: 证明请求对象
            comment: 可选备注

        返回:
            presentation_exchange_id (pres_ex_id)

        异常:
            ACAPyAPIError: 发送失败
        """
        endpoint = "/present-proof/send-request"

        payload = {
            "connection_id": connection_id,
            "proof_request": proof_request
        }

        if comment:
            payload["comment"] = comment

        logger.info(f"发送证明请求到连接 {connection_id}")
        response = await self._post(endpoint, payload)

        # 根据ACA-Py版本，返回格式可能不同
        # 通常返回 {"presentation_exchange_id": "..."} 或 {"thread_id": "..."}
        pres_ex_id = response.get("presentation_exchange_id") or response.get("thread_id")

        if not pres_ex_id:
            # 某些版本直接返回response
            pres_ex_id = response.get("presentation_exchange_id")

        if not pres_ex_id:
            raise ACAPyAPIError(f"未返回presentation_exchange_id: {response}")

        logger.info(f"证明请求已发送，pres_ex_id: {pres_ex_id}")
        return pres_ex_id

    # ==================== AIP 2.0 Present Proof 协议 ====================

    async def send_proof_request_v2(
        self,
        connection_id: str,
        proof_request: Dict,
        comment: Optional[str] = None,
        auto_verify: bool = True,
        auto_remove: bool = False
    ) -> str:
        """
        发送证明请求 (AIP 2.0)

        参数:
            connection_id: Aries连接ID
            proof_request: 证明请求对象 (AIP 2.0 使用 presentation_request)
            comment: 可选备注
            auto_verify: 是否自动验证
            auto_remove: 验证完成后是否自动删除记录（默认False，与vp_verification_auto.py一致）

        返回:
            presentation_exchange_id (pres_ex_id)

        异常:
            ACAPyAPIError: 发送失败
        """
        endpoint = "/present-proof-2.0/send-request"

        # AIP 2.0 需要指定格式（indy 或 dif）
        payload = {
            "connection_id": connection_id,
            "presentation_request": {
                "indy": proof_request  # 使用 indy 格式
            },
            "auto_verify": auto_verify,
            "auto_remove": auto_remove
        }

        if comment:
            payload["comment"] = comment

        logger.info(f"[AIP 2.0] 发送证明请求到连接 {connection_id}")
        response = await self._post(endpoint, payload)

        # AIP 2.0 返回 pres_ex_id
        pres_ex_id = response.get("pres_ex_id")

        if not pres_ex_id:
            raise ACAPyAPIError(f"未返回pres_ex_id: {response}")

        logger.info(f"[AIP 2.0] 证明请求已发送，pres_ex_id: {pres_ex_id}")
        return pres_ex_id

    async def get_presentation_exchange_v2(self, pres_ex_id: str) -> Dict:
        """
        获取presentation exchange记录 (AIP 2.0)

        参数:
            pres_ex_id: presentation exchange ID

        返回:
            presentation exchange对象，包含:
            - state: 协议状态
            - presentation_request: 原始证明请求
            - presentation: Holder返回的VP
            - verified: 验证结果
        """
        endpoint = f"/present-proof-2.0/records/{pres_ex_id}"

        logger.debug(f"[AIP 2.0] 获取presentation exchange: {pres_ex_id}")
        return await self._get(endpoint)

    async def verify_presentation_v2(self, pres_ex_id: str) -> Dict:
        """
        验证presentation (AIP 2.0)

        参数:
            pres_ex_id: presentation exchange ID

        返回:
            验证结果
        """
        endpoint = f"/present-proof-2.0/records/{pres_ex_id}/verify"

        logger.info(f"[AIP 2.0] 验证presentation: {pres_ex_id}")
        return await self._post(endpoint, {})

    async def get_presentation_records_v2(
        self,
        connection_id: Optional[str] = None,
        state: Optional[str] = None
    ) -> List[Dict]:
        """
        获取presentation records列表 (AIP 2.0)

        参数:
            connection_id: 过滤连接ID
            state: 过滤状态

        返回:
            记录列表
        """
        endpoint = "/present-proof-2.0/records"

        params = {}
        if connection_id:
            params["connection_id"] = connection_id
        if state:
            params["state"] = state

        logger.debug(f"[AIP 2.0] 获取presentation records, params={params}")
        response = await self._get(endpoint, params)
        return response

    async def get_presentation_exchange(self, pres_ex_id: str) -> Dict:
        """
        获取presentation exchange记录

        参数:
            pres_ex_id: presentation exchange ID

        返回:
            presentation exchange对象，包含:
            - state: 协议状态 (request_sent, presentation_received, verified, abandoned等)
            - verified: 验证结果 (true/false)
            - presentation_request: 原始证明请求
            - presentation: Holder返回的VP
            - verified_credentials: 验证的凭证列表
        """
        endpoint = f"/present-proof/records/{pres_ex_id}"

        logger.debug(f"获取presentation exchange: {pres_ex_id}")
        return await self._get(endpoint)

    async def get_presentation_records(
        self,
        connection_id: Optional[str] = None,
        state: Optional[str] = None
    ) -> List[Dict]:
        """
        获取presentation exchange记录列表

        参数:
            connection_id: 过滤连接ID
            state: 过滤状态

        返回:
            记录列表
        """
        endpoint = "/present-proof/records"

        params = {}
        if connection_id:
            params["connection_id"] = connection_id
        if state:
            params["state"] = state

        logger.debug(f"获取presentation records, params={params}")
        response = await self._get(endpoint, params)
        return response.get("results", [])

    async def verify_presentation(self, pres_ex_id: str) -> Dict:
        """
        验证presentation（某些ACA-Py版本需要显式调用验证）

        参数:
            pres_ex_id: presentation exchange ID

        返回:
            验证结果
        """
        # 大多数ACA-Py版本会自动验证，此方法用于兼容性
        endpoint = f"/present-proof/records/{pres_ex_id}/verify-presentation"

        logger.info(f"验证presentation: {pres_ex_id}")
        try:
            return await self._post(endpoint, {})
        except ACAPyAPIError as e:
            # 可能已经自动验证了
            if "already verified" in str(e).lower():
                logger.warning(f"Presentation已验证: {pres_ex_id}")
                return await self.get_presentation_exchange(pres_ex_id)
            raise

    async def remove_presentation_record(self, pres_ex_id: str, state: str = "done") -> Dict:
        """
        删除presentation exchange记录

        参数:
            pres_ex_id: presentation exchange ID
            state: 记录状态（必须匹配）

        返回:
            删除结果
        """
        endpoint = f"/present-proof/records/{pres_ex_id}"

        logger.info(f"删除presentation记录: {pres_ex_id}")
        return await self._delete(endpoint)

    # ==================== 连接管理 ====================

    async def create_invitation(
        self,
        auto_accept: bool = True,
        multi_use: bool = False,
        alias: Optional[str] = None
    ) -> Dict:
        """
        创建连接邀请

        参数:
            auto_accept: 自动接受连接
            multi_use: 是否可多次使用
            alias: 连接别名

        返回:
            邀请对象，包含:
            - connection_id: 连接ID
            - invitation: 邀请消息（需要发送给Holder）
            - invitation_url: 邀请URL
        """
        endpoint = "/connections/create-invitation"

        payload = {
            "auto_accept": auto_accept,
            "multi_use": multi_use
        }

        if alias:
            payload["alias"] = alias

        logger.info(f"创建连接邀请, alias={alias}, multi_use={multi_use}")
        response = await self._post(endpoint, payload)

        logger.info(f"连接邀请已创建, connection_id={response.get('connection_id')}")
        return response

    async def receive_invitation(
        self,
        invitation: Dict,
        alias: Optional[str] = None,
        auto_accept: bool = True
    ) -> Dict:
        """
        接收连接邀请

        参数:
            invitation: 邀请对象
            alias: 连接别名
            auto_accept: 自动接受连接

        返回:
            连接对象
        """
        endpoint = "/connections/receive-invitation"

        payload = {"auto_accept": auto_accept}
        if alias:
            payload["alias"] = alias

        logger.info(f"接收连接邀请, alias={alias}")
        response = await self._post(endpoint, invitation)
        return response

    async def get_connections(self) -> List[Dict]:
        """
        获取所有连接

        返回:
            连接列表
        """
        endpoint = "/connections"

        logger.debug("获取所有连接")
        response = await self._get(endpoint)
        return response.get("results", [])

    async def get_connection(self, connection_id: str) -> Dict:
        """
        获取指定连接

        参数:
            connection_id: 连接ID

        返回:
            连接对象，包含:
            - state: 连接状态 (init, invitation, request, response, active, response, error)
            - their_did: 对方DID
            - their_label: 对方标签
        """
        endpoint = f"/connections/{connection_id}"

        logger.debug(f"获取连接: {connection_id}")
        return await self._get(endpoint)

    async def get_connections_by_state(self, state: str) -> List[Dict]:
        """
        按状态获取连接

        参数:
            state: 连接状态 (active, invitation, request, response)

        返回:
            连接列表
        """
        endpoint = "/connections"
        params = {"state": state}

        logger.debug(f"获取状态为 {state} 的连接")
        response = await self._get(endpoint, params)
        return response.get("results", [])

    async def delete_connection(self, connection_id: str) -> bool:
        """
        删除连接

        参数:
            connection_id: 连接ID

        返回:
            是否成功
        """
        endpoint = f"/connections/{connection_id}"

        logger.info(f"删除连接: {connection_id}")
        await self._delete(endpoint)
        return True

    async def send_ping(self, connection_id: str) -> Dict:
        """
        向连接发送ping消息（用于激活卡在response状态的连接）

        参数:
            connection_id: 连接ID

        返回:
            ping响应，包含thread_id
        """
        endpoint = f"/connections/{connection_id}/send-ping"

        # ACA-Py的ping端点需要空的JSON object作为body
        logger.info(f"发送ping到连接: {connection_id}")
        response = await self._post(endpoint, {})

        logger.info(f"Ping已发送, thread_id: {response.get('thread_id')}")
        return response

    # ==================== 辅助方法 ====================

    async def ping(self) -> bool:
        """
        检查ACA-Py服务是否可用

        返回:
            是否可用
        """
        try:
            # 尝试获取当前活跃的连接数
            connections = await self.get_connections_by_state("active")
            logger.info(f"ACA-Py服务正常，活跃连接数: {len(connections)}")
            return True
        except Exception as e:
            logger.error(f"ACA-Py服务不可用: {e}")
            return False

    async def get_wallet_info(self) -> Dict:
        """
        获取钱包信息

        返回:
            钱包信息
        """
        endpoint = "/wallet/did"

        logger.debug("获取钱包信息")
        return await self._get(endpoint)

    async def get_public_did(self) -> Optional[str]:
        """
        获取公共DID

        返回:
            公共DID，如果没有设置则返回None
        """
        try:
            wallet_info = await self.get_wallet_info()
            results = wallet_info.get("results", [])
            if results:
                return results[0].get("did")
        except Exception as e:
            logger.warning(f"获取公共DID失败: {e}")
        return None

    def __repr__(self) -> str:
        return f"ACAPyClient(url={self.admin_url}, wallet={self.wallet_name})"
