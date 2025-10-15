#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Oracle服务配置加载
不依赖链连接
"""

import asyncio
import json
import logging
from enhanced_oracle import EnhancedCrossChainOracle

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_oracle_config_loading():
    """测试Oracle服务配置加载"""
    logger.info("🧪 测试Oracle服务配置加载...")
    
    try:
        # 创建Oracle实例
        oracle = EnhancedCrossChainOracle("cross_chain_config.json")
        
        # 显示配置信息
        logger.info("✅ Oracle服务配置加载成功")
        logger.info("📋 配置详情:")
        
        # Oracle配置
        oracle_config = oracle.config['oracle']
        logger.info(f"   - Oracle DID: {oracle_config['oracle_did']}")
        logger.info(f"   - Oracle地址: {oracle_config['oracle_address']}")
        logger.info(f"   - ACA-Py URL: {oracle_config['admin_url']}")
        
        # 链配置
        logger.info(f"   - 配置链数量: {len(oracle.config['chains'])}")
        for i, chain in enumerate(oracle.config['chains']):
            logger.info(f"   - 链{i+1}: {chain['name']} ({chain['chain_id']})")
            logger.info(f"     RPC: {chain['rpc_url']}")
            logger.info(f"     桥合约: {chain.get('bridge_address', '未配置')}")
            logger.info(f"     验证器: {chain.get('verifier_address', '未配置')}")
            logger.info(f"     私钥: {chain.get('private_key', '未配置')[:10]}...")
            logger.info(f"     Gas价格: {chain.get('gas_price', '未配置')}")
        
        # 桥配置
        if 'bridge' in oracle.config:
            bridge_config = oracle.config['bridge']
            logger.info(f"   - 证明有效期: {bridge_config.get('proof_validity_period', '未配置')}秒")
            logger.info(f"   - 最大支持链数: {bridge_config.get('max_supported_chains', '未配置')}")
        
        # 代币配置
        if 'tokens' in oracle.config:
            logger.info(f"   - 配置代币数量: {len(oracle.config['tokens'])}")
            for i, token in enumerate(oracle.config['tokens']):
                logger.info(f"   - 代币{i+1}: {token['name']} ({token['symbol']})")
                logger.info(f"     精度: {token['decimals']}")
                logger.info(f"     初始供应: {token['initial_supply']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Oracle服务配置加载失败: {e}")
        return False

async def test_oracle_initialization():
    """测试Oracle服务初始化"""
    logger.info("🔧 测试Oracle服务初始化...")
    
    try:
        oracle = EnhancedCrossChainOracle("cross_chain_config.json")
        
        # 测试状态获取
        status = oracle.get_status()
        logger.info("✅ Oracle服务状态:")
        logger.info(f"   - 运行状态: {status['running']}")
        logger.info(f"   - 连接链数: {status['chains_connected']}")
        logger.info(f"   - ACA-Py连接: {status['acapy_connected']}")
        logger.info(f"   - 连接数: {status['connections']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Oracle服务初始化失败: {e}")
        return False

async def main():
    """主函数"""
    logger.info("🎬 Oracle服务配置测试")
    logger.info("=" * 60)
    
    # 测试配置加载
    config_ok = await test_oracle_config_loading()
    print()
    
    # 测试服务初始化
    init_ok = await test_oracle_initialization()
    print()
    
    # 总结
    logger.info("📊 测试结果:")
    logger.info(f"   - 配置加载: {'✅' if config_ok else '❌'}")
    logger.info(f"   - 服务初始化: {'✅' if init_ok else '❌'}")
    
    if config_ok and init_ok:
        logger.info("🎉 所有测试通过！Oracle服务配置正确")
    else:
        logger.warning("⚠️  部分测试失败，请检查配置")

if __name__ == "__main__":
    asyncio.run(main())
