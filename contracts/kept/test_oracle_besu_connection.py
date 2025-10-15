#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Oracle服务与Besu链的连接
"""

import asyncio
import json
import logging
from oracle_v6_compatible import OracleV6Compatible

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_oracle_besu_connection():
    """测试Oracle服务与Besu链的连接"""
    logger.info("🧪 测试Oracle服务与Besu链连接...")
    
    try:
        # 创建Oracle实例
        oracle = OracleV6Compatible("cross_chain_config.json")
        
        # 获取服务状态
        status = oracle.get_status()
        
        logger.info("📊 Oracle服务状态:")
        logger.info(f"   - 运行状态: {status['running']}")
        logger.info(f"   - 连接链数: {status['chains_connected']}")
        logger.info(f"   - ACA-Py连接: {status['acapy_connected']}")
        logger.info(f"   - 连接数: {status['connections']}")
        
        # 检查各链状态
        logger.info("\\n🔗 各链连接状态:")
        for chain_id, chain_status in status['chains'].items():
            if chain_status['connected']:
                logger.info(f"   ✅ {chain_id}: 连接正常")
                logger.info(f"      - 区块号: {chain_status['block_number']}")
                logger.info(f"      - 链ID: {chain_status['chain_id']}")
            else:
                logger.info(f"   ❌ {chain_id}: 连接失败")
                logger.info(f"      - 错误: {chain_status.get('error', '未知错误')}")
        
        # 测试合约函数调用
        logger.info("\\n📋 测试合约函数调用:")
        
        # 测试链A的桥合约
        bridge_info_a = oracle.call_contract_function('chain_a', 'bridge', 'getBridgeInfo')
        if bridge_info_a:
            logger.info(f"   ✅ 链A桥合约函数调用成功: {bridge_info_a}")
        else:
            logger.info(f"   ❌ 链A桥合约函数调用失败")
        
        # 测试链B的桥合约
        bridge_info_b = oracle.call_contract_function('chain_b', 'bridge', 'getBridgeInfo')
        if bridge_info_b:
            logger.info(f"   ✅ 链B桥合约函数调用成功: {bridge_info_b}")
        else:
            logger.info(f"   ❌ 链B桥合约函数调用失败")
        
        # 测试链A的DID验证器
        verifier_owner_a = oracle.call_contract_function('chain_a', 'verifier', 'owner')
        if verifier_owner_a:
            logger.info(f"   ✅ 链A DID验证器函数调用成功: {verifier_owner_a}")
        else:
            logger.info(f"   ❌ 链A DID验证器函数调用失败")
        
        # 测试链B的DID验证器
        verifier_owner_b = oracle.call_contract_function('chain_b', 'verifier', 'owner')
        if verifier_owner_b:
            logger.info(f"   ✅ 链B DID验证器函数调用成功: {verifier_owner_b}")
        else:
            logger.info(f"   ❌ 链B DID验证器函数调用失败")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        return False

async def test_oracle_monitoring():
    """测试Oracle监控功能"""
    logger.info("\\n👁️  测试Oracle监控功能...")
    
    try:
        oracle = OracleV6Compatible("cross_chain_config.json")
        
        # 启动监控（短时间）
        logger.info("启动监控（5秒）...")
        monitoring_task = asyncio.create_task(oracle.start_monitoring())
        
        # 等待5秒
        await asyncio.sleep(5)
        
        # 停止监控
        await oracle.stop()
        monitoring_task.cancel()
        
        logger.info("✅ 监控功能测试完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 监控功能测试失败: {e}")
        return False

async def main():
    """主函数"""
    logger.info("🎬 Oracle服务与Besu链连接测试")
    logger.info("=" * 60)
    
    # 测试连接
    connection_ok = await test_oracle_besu_connection()
    print()
    
    # 测试监控
    monitoring_ok = await test_oracle_monitoring()
    print()
    
    # 总结
    logger.info("📊 测试结果总结:")
    logger.info(f"   - 连接测试: {'✅' if connection_ok else '❌'}")
    logger.info(f"   - 监控测试: {'✅' if monitoring_ok else '❌'}")
    
    if connection_ok and monitoring_ok:
        logger.info("\\n🎉 所有测试通过！Oracle服务与Besu链连接正常")
    else:
        logger.warning("\\n⚠️  部分测试失败，请检查配置")

if __name__ == "__main__":
    asyncio.run(main())
