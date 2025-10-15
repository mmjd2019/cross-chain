#!/usr/bin/env python3
"""
Web3.py连接修复脚本
尝试修复Web3.py v6的连接问题
"""

import json
import logging
from web3 import Web3
from web3.middleware import geth_poa_middleware

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_web3_connection_methods():
    """测试Web3.py不同的连接方法"""
    logger.info("🔍 测试Web3.py不同的连接方法...")
    
    url = 'http://localhost:8545'
    
    try:
        w3 = Web3(Web3.HTTPProvider(url))
        
        # 方法1: 使用is_connected()
        logger.info("  方法1: is_connected()")
        try:
            is_connected = w3.is_connected()
            logger.info(f"    结果: {is_connected}")
        except Exception as e:
            logger.error(f"    失败: {e}")
        
        # 方法2: 直接调用eth方法
        logger.info("  方法2: 直接调用eth方法")
        try:
            chain_id = w3.eth.chain_id
            logger.info(f"    链ID: {chain_id}")
        except Exception as e:
            logger.error(f"    失败: {e}")
        
        # 方法3: 获取最新区块
        logger.info("  方法3: 获取最新区块")
        try:
            latest_block = w3.eth.get_block('latest')
            logger.info(f"    最新区块: {latest_block.number}")
        except Exception as e:
            logger.error(f"    失败: {e}")
        
        # 方法4: 获取余额
        logger.info("  方法4: 获取余额")
        try:
            test_address = "0x81Be24626338695584B5beaEBf51e09879A0eCc6"
            balance = w3.eth.get_balance(test_address)
            logger.info(f"    余额: {balance / 10**18} ETH")
        except Exception as e:
            logger.error(f"    失败: {e}")
        
        # 方法5: 检查provider状态
        logger.info("  方法5: 检查provider状态")
        try:
            provider = w3.provider
            logger.info(f"    Provider类型: {type(provider)}")
            
            # 直接调用provider
            response = provider.make_request('eth_blockNumber', [])
            logger.info(f"    Provider响应: {response}")
            
        except Exception as e:
            logger.error(f"    失败: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"  Web3.py连接测试失败: {e}")
        return False

def test_web3_with_manual_connection_check():
    """手动检查连接状态"""
    logger.info("🔧 手动检查连接状态...")
    
    url = 'http://localhost:8545'
    
    try:
        w3 = Web3(Web3.HTTPProvider(url))
        
        # 手动实现连接检查
        def manual_is_connected(w3_instance):
            try:
                # 尝试获取链ID
                chain_id = w3_instance.eth.chain_id
                logger.info(f"    手动检查 - 链ID: {chain_id}")
                return True
            except Exception as e:
                logger.error(f"    手动检查失败: {e}")
                return False
        
        # 使用手动检查
        is_connected = manual_is_connected(w3)
        logger.info(f"  手动连接检查结果: {is_connected}")
        
        if is_connected:
            # 如果手动检查成功，尝试其他操作
            try:
                latest_block = w3.eth.get_block('latest')
                logger.info(f"  ✅ 成功获取最新区块: {latest_block.number}")
                
                # 获取gas价格
                gas_price = w3.eth.gas_price
                logger.info(f"  ✅ 成功获取gas价格: {gas_price}")
                
                return True
            except Exception as e:
                logger.error(f"  ❌ 后续操作失败: {e}")
                return False
        
        return False
        
    except Exception as e:
        logger.error(f"  手动连接检查失败: {e}")
        return False

def test_web3_v6_specific_issues():
    """测试Web3.py v6特定问题"""
    logger.info("🔍 测试Web3.py v6特定问题...")
    
    url = 'http://localhost:8545'
    
    try:
        w3 = Web3(Web3.HTTPProvider(url))
        
        # 检查Web3.py v6的特定属性
        logger.info("  检查Web3.py v6属性...")
        
        # 检查is_connected方法的实现
        try:
            import inspect
            is_connected_method = getattr(w3, 'is_connected', None)
            if is_connected_method:
                logger.info(f"    is_connected方法: {is_connected_method}")
                logger.info(f"    方法源码: {inspect.getsource(is_connected_method)}")
            else:
                logger.error("    is_connected方法不存在")
        except Exception as e:
            logger.error(f"    检查is_connected方法失败: {e}")
        
        # 尝试直接调用底层方法
        try:
            # 检查provider的is_connected方法
            provider = w3.provider
            if hasattr(provider, 'is_connected'):
                provider_connected = provider.is_connected()
                logger.info(f"    Provider is_connected: {provider_connected}")
            else:
                logger.info("    Provider没有is_connected方法")
        except Exception as e:
            logger.error(f"    检查Provider is_connected失败: {e}")
        
        # 尝试绕过is_connected直接使用
        logger.info("  绕过is_connected直接使用...")
        try:
            # 直接调用eth方法
            chain_id = w3.eth.chain_id
            logger.info(f"    ✅ 直接获取链ID成功: {chain_id}")
            
            # 获取账户余额
            test_address = "0x81Be24626338695584B5beaEBf51e09879A0eCc6"
            balance = w3.eth.get_balance(test_address)
            logger.info(f"    ✅ 直接获取余额成功: {balance / 10**18} ETH")
            
            return True
            
        except Exception as e:
            logger.error(f"    ❌ 直接使用失败: {e}")
            return False
        
    except Exception as e:
        logger.error(f"  Web3.py v6测试失败: {e}")
        return False

def create_working_web3_wrapper():
    """创建可工作的Web3包装器"""
    logger.info("🛠️ 创建可工作的Web3包装器...")
    
    class WorkingWeb3:
        def __init__(self, rpc_url):
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
            self.rpc_url = rpc_url
        
        def is_connected(self):
            """自定义连接检查"""
            try:
                # 尝试获取链ID来验证连接
                chain_id = self.w3.eth.chain_id
                return True
            except Exception:
                return False
        
        def get_chain_id(self):
            """获取链ID"""
            try:
                return self.w3.eth.chain_id
            except Exception as e:
                logger.error(f"获取链ID失败: {e}")
                return None
        
        def get_balance(self, address):
            """获取余额"""
            try:
                return self.w3.eth.get_balance(address)
            except Exception as e:
                logger.error(f"获取余额失败: {e}")
                return 0
        
        def get_latest_block(self):
            """获取最新区块"""
            try:
                return self.w3.eth.get_block('latest')
            except Exception as e:
                logger.error(f"获取最新区块失败: {e}")
                return None
        
        def get_gas_price(self):
            """获取gas价格"""
            try:
                return self.w3.eth.gas_price
            except Exception as e:
                logger.error(f"获取gas价格失败: {e}")
                return 0
        
        def send_raw_transaction(self, raw_tx):
            """发送原始交易"""
            try:
                return self.w3.eth.send_raw_transaction(raw_tx)
            except Exception as e:
                logger.error(f"发送原始交易失败: {e}")
                return None
    
    # 测试包装器
    logger.info("  测试Web3包装器...")
    
    try:
        w3_wrapper = WorkingWeb3('http://localhost:8545')
        
        # 测试连接
        is_connected = w3_wrapper.is_connected()
        logger.info(f"    包装器连接状态: {is_connected}")
        
        if is_connected:
            # 测试各种功能
            chain_id = w3_wrapper.get_chain_id()
            logger.info(f"    链ID: {chain_id}")
            
            balance = w3_wrapper.get_balance("0x81Be24626338695584B5beaEBf51e09879A0eCc6")
            logger.info(f"    余额: {balance / 10**18} ETH")
            
            latest_block = w3_wrapper.get_latest_block()
            if latest_block:
                logger.info(f"    最新区块: {latest_block.number}")
            
            gas_price = w3_wrapper.get_gas_price()
            logger.info(f"    Gas价格: {gas_price}")
            
            return True
        else:
            logger.error("    包装器连接失败")
            return False
            
    except Exception as e:
        logger.error(f"  包装器测试失败: {e}")
        return False

def main():
    """主函数"""
    logger.info("🚀 开始Web3.py连接修复")
    logger.info("=" * 70)
    
    # 1. 测试不同的连接方法
    test_web3_connection_methods()
    
    # 2. 手动检查连接状态
    test_web3_with_manual_connection_check()
    
    # 3. 测试Web3.py v6特定问题
    test_web3_v6_specific_issues()
    
    # 4. 创建可工作的Web3包装器
    create_working_web3_wrapper()
    
    logger.info("\n" + "=" * 70)
    logger.info("📊 Web3.py连接修复完成")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
