#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试配置文件加载
"""

import json
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_config_loading():
    """测试配置文件加载"""
    logger.info("🧪 测试配置文件加载...")
    
    # 测试 cross_chain_config.json
    try:
        with open('cross_chain_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        logger.info("✅ cross_chain_config.json 加载成功")
        
        # 显示配置信息
        logger.info("📋 配置信息:")
        logger.info(f"   - Oracle DID: {config['oracle']['oracle_did']}")
        logger.info(f"   - Oracle地址: {config['oracle']['oracle_address']}")
        logger.info(f"   - 链数量: {len(config['chains'])}")
        
        for i, chain in enumerate(config['chains']):
            logger.info(f"   - 链{i+1}: {chain['name']} ({chain['chain_id']})")
            logger.info(f"     RPC: {chain['rpc_url']}")
            logger.info(f"     桥合约: {chain.get('bridge_address', '未配置')}")
            logger.info(f"     验证器: {chain.get('verifier_address', '未配置')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ cross_chain_config.json 加载失败: {e}")
        return False

def test_oracle_config():
    """测试oracle_config.json"""
    try:
        with open('oracle_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        logger.info("✅ oracle_config.json 加载成功")
        return True
        
    except Exception as e:
        logger.error(f"❌ oracle_config.json 加载失败: {e}")
        return False

def main():
    """主函数"""
    logger.info("🔍 配置文件测试")
    logger.info("=" * 50)
    
    # 测试两个配置文件
    cross_chain_ok = test_config_loading()
    print()
    oracle_ok = test_oracle_config()
    
    print()
    logger.info("📊 测试结果:")
    logger.info(f"   - cross_chain_config.json: {'✅' if cross_chain_ok else '❌'}")
    logger.info(f"   - oracle_config.json: {'✅' if oracle_ok else '❌'}")
    
    if cross_chain_ok:
        logger.info("🎯 推荐使用 cross_chain_config.json 作为Oracle服务配置")
    else:
        logger.warning("⚠️  配置文件有问题，请检查")

if __name__ == "__main__":
    main()
