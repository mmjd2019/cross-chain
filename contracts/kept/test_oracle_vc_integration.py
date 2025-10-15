#!/usr/bin/env python3
"""
测试Oracle服务的VC集成功能
"""

import asyncio
import json
import logging
from enhanced_oracle_with_vc import EnhancedOracleWithVC

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_oracle_vc_integration():
    """测试Oracle VC集成功能"""
    logger.info("开始测试Oracle VC集成功能")
    
    try:
        # 初始化Oracle服务
        oracle = EnhancedOracleWithVC()
        logger.info("Oracle服务初始化成功")
        
        # 测试连接状态
        await oracle.check_connection_status()
        
        # 测试生成跨链VC数据
        test_event_data = {
            'user': '0x1234567890123456789012345678901234567890',
            'amount': '1000000000000000000',  # 1 ETH
            'token': '0x0000000000000000000000000000000000000000',
            'lockId': 'test_lock_123456',
            'txHash': '0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890'
        }
        
        vc_data = await oracle.generate_cross_chain_vc("chain_a", test_event_data)
        logger.info(f"生成的VC数据: {json.dumps(vc_data, indent=2, ensure_ascii=False)}")
        
        # 测试颁发VC
        vc_result = await oracle.issue_cross_chain_vc(vc_data)
        if vc_result:
            logger.info(f"VC颁发成功: {vc_result}")
        else:
            logger.error("VC颁发失败")
        
        # 测试VC状态查询
        vc_status = await oracle.get_vc_status(test_event_data['lockId'])
        if vc_status:
            logger.info(f"VC状态: {vc_status}")
        else:
            logger.info("未找到VC状态")
        
        # 测试跨链证明验证
        verification_result = await oracle.verify_cross_chain_proof(vc_data)
        logger.info(f"跨链证明验证结果: {verification_result}")
        
        logger.info("Oracle VC集成功能测试完成")
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        raise

async def test_connection_management():
    """测试连接管理功能"""
    logger.info("开始测试连接管理功能")
    
    try:
        oracle = EnhancedOracleWithVC()
        
        # 测试获取或创建连接
        connection_id = await oracle.get_or_create_connection()
        if connection_id:
            logger.info(f"连接管理成功: {connection_id}")
        else:
            logger.error("连接管理失败")
        
        # 测试连接状态检查
        await oracle.check_connection_status()
        
        logger.info("连接管理功能测试完成")
        
    except Exception as e:
        logger.error(f"连接管理测试过程中出错: {e}")
        raise

async def test_vc_workflow():
    """测试完整的VC工作流程"""
    logger.info("开始测试完整VC工作流程")
    
    try:
        oracle = EnhancedOracleWithVC()
        
        # 模拟资产锁定事件
        event_data = {
            'user': '0x1234567890123456789012345678901234567890',
            'amount': '2000000000000000000',  # 2 ETH
            'token': '0x0000000000000000000000000000000000000000',
            'lockId': 'workflow_test_lock_789',
            'txHash': '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef'
        }
        
        # 处理资产锁定事件
        await oracle.handle_asset_locked_event("chain_a", event_data)
        
        # 等待一下让异步操作完成
        await asyncio.sleep(5)
        
        # 检查VC状态
        vc_status = await oracle.get_vc_status(event_data['lockId'])
        if vc_status:
            logger.info(f"工作流程测试成功，VC状态: {vc_status}")
        else:
            logger.info("工作流程测试完成，但未找到VC状态")
        
        logger.info("完整VC工作流程测试完成")
        
    except Exception as e:
        logger.error(f"VC工作流程测试过程中出错: {e}")
        raise

async def main():
    """主测试函数"""
    logger.info("=" * 50)
    logger.info("开始Oracle VC集成功能全面测试")
    logger.info("=" * 50)
    
    try:
        # 测试1: 基础集成功能
        logger.info("\n1. 测试基础集成功能")
        await test_oracle_vc_integration()
        
        # 测试2: 连接管理功能
        logger.info("\n2. 测试连接管理功能")
        await test_connection_management()
        
        # 测试3: 完整工作流程
        logger.info("\n3. 测试完整VC工作流程")
        await test_vc_workflow()
        
        logger.info("\n" + "=" * 50)
        logger.info("所有测试完成！")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    if success:
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 测试失败！")
        sys.exit(1)
