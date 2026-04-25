#!/usr/bin/env python3
"""
自动接受Proof Requests的Holder服务
监听Holder ACA-Py的proof request事件并自动接受
"""

import asyncio
import logging
import json
from typing import Dict

import aiohttp
from aiohttp import web


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


HOLDER_ADMIN_URL = "http://localhost:8081"
VERIFIER_ADMIN_URL = "http://localhost:8082"


async def handle_proof_request_event(request):
    """处理proof request webhook事件"""
    try:
        event = await request.json()
        topic = event.get('topic')
        state = event.get('state')

        logger.info(f"收到事件: topic={topic}, state={state}")

        if topic == 'present_proof' and state == 'request_received':
            pres_ex_id = event.get('presentation_exchange_id')

            if pres_ex_id:
                logger.info(f"🎯 自动接受proof request: {pres_ex_id}")

                # 调用Holder ACA-Py API接受proof request
                async with aiohttp.ClientSession() as session:
                    url = f"{HOLDER_ADMIN_URL}/present-proof-2.0/records/{pres_ex_id}/accept-presentation"

                    async with session.post(url) as response:
                        if response.status == 200:
                            logger.info(f"✅ 成功接受proof request: {pres_ex_id}")
                        else:
                            text = await response.text()
                            logger.error(f"❌ 接受proof request失败: {response.status} - {text}")

        return web.Response(status=200)

    except Exception as e:
        logger.error(f"处理webhook事件失败: {e}", exc_info=True)
        return web.Response(status=500)


async def start_webhook_server(port=7001):
    """启动webhook服务器"""
    app = web.Application()
    app.router.add_post('/webhook', handle_proof_request_event)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    logger.info(f"🚀 Webhook服务器已启动: http://0.0.0.0:{port}/webhook")
    logger.info(f"  监听proof request事件并自动接受")

    return runner


async def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("Holder自动接受Proof Requests服务")
    logger.info("=" * 80)

    # 启动webhook服务器
    runner = await start_webhook_server(port=7001)

    logger.info("")
    logger.info("⚠️  重要提示:")
    logger.info(f"  1. 需要在Holder ACA-Py中配置webhook URL:")
    logger.info(f"     docker exec holder-acapy aca-py ... \\")
    logger.info(f"       --webhook-url http://localhost:7001/webhook")
    logger.info("")
    logger.info(f"  2. 或者手动设置webhook:")
    logger.info(f"     docker exec holder-acapy aca-py \\")
    logger.info(f"       --endpoint http://<HOLDER_ENDPOINT>:8001 \\")
    logger.info(f"       --webhook-url http://<WEBHOOK_SERVER>:7001/webhook")
    logger.info("")
    logger.info(f"  3. 服务正在运行，按Ctrl+C停止")
    logger.info("=" * 80)

    try:
        # 保持运行
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n停止服务...")
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
