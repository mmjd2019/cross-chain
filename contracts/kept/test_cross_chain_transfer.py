#!/usr/bin/env python3
"""
测试真正的跨链转账功能
验证ETH在两条Besu链之间的真正转移
"""

import sys
import os
import json
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('/home/manifold/cursor/twobesu/contracts/kept')

from cross_chain_bridge import CrossChainBridge

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_cross_chain_transfer():
    """测试跨链转账功能"""
    logger.info("🚀 开始测试真正的跨链转账功能")
    logger.info("=" * 80)
    
    try:
        # 创建跨链桥接系统
        bridge = CrossChainBridge()
        
        # 获取链状态
        logger.info("📊 检查链状态...")
        status = bridge.get_chain_status()
        
        for chain_name, chain_status in status.items():
            logger.info(f"  {chain_name}: {chain_status['status']}")
            if chain_status['status'] == 'online':
                details = chain_status['details']
                logger.info(f"    余额: {details['test_account_balance']} ETH")
                logger.info(f"    链ID: {details['chain_id']}")
                logger.info(f"    最新区块: {details['latest_block']}")
        
        # 检查是否可以进行跨链转账
        chain_a_online = status.get('chain_a', {}).get('status') == 'online'
        chain_b_online = status.get('chain_b', {}).get('status') == 'online'
        
        if not chain_a_online or not chain_b_online:
            logger.error("❌ 链状态不正常，无法进行跨链转账测试")
            return False
        
        logger.info("✅ 所有链状态正常，可以开始跨链转账测试")
        
        # 记录转账前状态
        logger.info("\n📋 转账前状态:")
        chain_a_balance = bridge.get_chain_balance('chain_a', bridge.test_account.address)
        chain_b_balance = bridge.get_chain_balance('chain_b', bridge.test_account.address)
        
        logger.info(f"  链A余额: {chain_a_balance[1]} ETH")
        logger.info(f"  链B余额: {chain_b_balance[1]} ETH")
        
        # 执行跨链转账测试
        logger.info("\n💰 执行跨链转账测试...")
        transfer_amount = 0.1  # 0.1 ETH
        
        result = bridge.perform_cross_chain_transfer(
            amount=transfer_amount,
            from_chain='chain_a',
            to_chain='chain_b'
        )
        
        if result['status'] == 'success':
            logger.info("✅ 跨链转账测试成功!")
            logger.info(f"  锁定交易: {result['lock_tx_hash']}")
            logger.info(f"  释放交易: {result['release_tx_hash']}")
            logger.info(f"  源链变化: {result['source_change']} ETH")
            logger.info(f"  目标链变化: {result['target_change']} ETH")
            
            # 验证转账结果
            logger.info("\n🔍 验证转账结果:")
            chain_a_balance_after = bridge.get_chain_balance('chain_a', bridge.test_account.address)
            chain_b_balance_after = bridge.get_chain_balance('chain_b', bridge.test_account.address)
            
            logger.info(f"  链A余额变化: {chain_a_balance[1]} -> {chain_a_balance_after[1]} ETH")
            logger.info(f"  链B余额变化: {chain_b_balance[1]} -> {chain_b_balance_after[1]} ETH")
            
            # 计算实际变化
            actual_chain_a_change = chain_a_balance[1] - chain_a_balance_after[1]
            actual_chain_b_change = chain_b_balance_after[1] - chain_b_balance[1]
            
            logger.info(f"  实际链A减少: {actual_chain_a_change} ETH")
            logger.info(f"  实际链B增加: {actual_chain_b_change} ETH")
            
            # 验证跨链转账是否成功
            if abs(actual_chain_a_change - transfer_amount) < 0.001 and abs(actual_chain_b_change - transfer_amount) < 0.001:
                logger.info("🎉 跨链转账验证成功! ETH确实在两条链之间发生了转移")
                return True
            else:
                logger.error("❌ 跨链转账验证失败! 余额变化不符合预期")
                return False
        else:
            logger.error("❌ 跨链转账测试失败")
            return False
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        return False

def test_reverse_transfer():
    """测试反向跨链转账"""
    logger.info("\n🔄 测试反向跨链转账...")
    logger.info("=" * 80)
    
    try:
        bridge = CrossChainBridge()
        
        # 从链B转回链A
        transfer_amount = 0.05  # 0.05 ETH
        
        result = bridge.perform_cross_chain_transfer(
            amount=transfer_amount,
            from_chain='chain_b',
            to_chain='chain_a'
        )
        
        if result['status'] == 'success':
            logger.info("✅ 反向跨链转账成功!")
            logger.info(f"  锁定交易: {result['lock_tx_hash']}")
            logger.info(f"  释放交易: {result['release_tx_hash']}")
            logger.info(f"  源链变化: {result['source_change']} ETH")
            logger.info(f"  目标链变化: {result['target_change']} ETH")
            return True
        else:
            logger.error("❌ 反向跨链转账失败")
            return False
        
    except Exception as e:
        logger.error(f"❌ 反向转账测试失败: {e}")
        return False

def generate_test_report():
    """生成测试报告"""
    logger.info("\n📊 生成测试报告...")
    
    try:
        bridge = CrossChainBridge()
        history = bridge.get_transfer_history()
        
        report = {
            'test_time': datetime.now().isoformat(),
            'test_type': '真正的跨链转账测试',
            'total_transfers': len(history),
            'successful_transfers': len([h for h in history if h['status'] == 'success']),
            'failed_transfers': len([h for h in history if h['status'] == 'failed']),
            'transfer_details': history
        }
        
        # 保存报告
        report_file = f"cross_chain_transfer_test_report_{int(datetime.now().timestamp())}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ 测试报告已保存: {report_file}")
        
        # 打印摘要
        logger.info(f"\n📋 测试摘要:")
        logger.info(f"  总转账次数: {report['total_transfers']}")
        logger.info(f"  成功次数: {report['successful_transfers']}")
        logger.info(f"  失败次数: {report['failed_transfers']}")
        
        return report
        
    except Exception as e:
        logger.error(f"❌ 生成报告失败: {e}")
        return None

def main():
    """主函数"""
    logger.info("🚀 开始真正的跨链转账功能测试")
    logger.info("=" * 80)
    
    success_count = 0
    total_tests = 2
    
    # 测试1: 正向跨链转账
    logger.info("\n🧪 测试1: 正向跨链转账 (链A -> 链B)")
    if test_cross_chain_transfer():
        success_count += 1
        logger.info("✅ 测试1通过")
    else:
        logger.error("❌ 测试1失败")
    
    # 测试2: 反向跨链转账
    logger.info("\n🧪 测试2: 反向跨链转账 (链B -> 链A)")
    if test_reverse_transfer():
        success_count += 1
        logger.info("✅ 测试2通过")
    else:
        logger.error("❌ 测试2失败")
    
    # 生成测试报告
    generate_test_report()
    
    # 总结
    logger.info("\n" + "=" * 80)
    logger.info("📊 测试总结")
    logger.info("=" * 80)
    logger.info(f"总测试数: {total_tests}")
    logger.info(f"成功数: {success_count}")
    logger.info(f"失败数: {total_tests - success_count}")
    logger.info(f"成功率: {success_count/total_tests*100:.1f}%")
    
    if success_count == total_tests:
        logger.info("🎉 所有测试通过! 真正的跨链转账功能正常工作!")
    else:
        logger.error("❌ 部分测试失败，需要检查问题")
    
    return success_count == total_tests

if __name__ == "__main__":
    main()
