#!/usr/bin/env python3
"""
Web3.py深度诊断脚本
深入分析Web3.py连接失败的具体原因
"""

import json
import subprocess
import logging
import requests
from web3 import Web3
from web3.middleware import geth_poa_middleware
import urllib3

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_direct_http_requests():
    """测试直接HTTP请求"""
    logger.info("🌐 测试直接HTTP请求...")
    
    chains = {
        'chain_a': 'http://localhost:8545',
        'chain_b': 'http://localhost:8555'
    }
    
    for chain_name, url in chains.items():
        logger.info(f"  测试 {chain_name} ({url})...")
        
        # 测试GET请求
        try:
            response = requests.get(url, timeout=5)
            logger.info(f"    GET请求状态: {response.status_code}")
            logger.info(f"    Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        except Exception as e:
            logger.error(f"    GET请求失败: {e}")
        
        # 测试POST请求
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_blockNumber",
                "params": [],
                "id": 1
            }
            response = requests.post(url, json=payload, timeout=5)
            logger.info(f"    POST请求状态: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    block_number = int(data['result'], 16)
                    logger.info(f"    ✅ 成功获取区块号: {block_number}")
                else:
                    logger.error(f"    ❌ 响应格式错误: {data}")
            else:
                logger.error(f"    ❌ POST请求失败: {response.text}")
        except Exception as e:
            logger.error(f"    POST请求失败: {e}")

def test_web3_connection_with_debug():
    """测试Web3.py连接并调试"""
    logger.info("🔍 测试Web3.py连接并调试...")
    
    chains = {
        'chain_a': 'http://localhost:8545',
        'chain_b': 'http://localhost:8555'
    }
    
    for chain_name, url in chains.items():
        logger.info(f"  调试 {chain_name} ({url})...")
        
        try:
            # 创建Web3实例
            w3 = Web3(Web3.HTTPProvider(url))
            
            # 启用调试模式
            logger.info(f"    Web3实例创建成功")
            
            # 测试连接
            is_connected = w3.is_connected()
            logger.info(f"    连接状态: {is_connected}")
            
            if not is_connected:
                # 尝试获取更多调试信息
                try:
                    # 测试底层HTTPProvider
                    provider = w3.provider
                    logger.info(f"    Provider类型: {type(provider)}")
                    
                    # 尝试直接调用provider
                    response = provider.make_request('eth_blockNumber', [])
                    logger.info(f"    Provider响应: {response}")
                    
                except Exception as e:
                    logger.error(f"    Provider调试失败: {e}")
            
        except Exception as e:
            logger.error(f"    Web3.py连接失败: {e}")
            logger.error(f"    错误类型: {type(e)}")

def test_web3_with_different_configs():
    """测试Web3.py不同配置"""
    logger.info("⚙️ 测试Web3.py不同配置...")
    
    url = 'http://localhost:8545'
    
    # 配置1: 基本配置
    logger.info("  配置1: 基本配置")
    try:
        w3 = Web3(Web3.HTTPProvider(url))
        is_connected = w3.is_connected()
        logger.info(f"    连接状态: {is_connected}")
    except Exception as e:
        logger.error(f"    失败: {e}")
    
    # 配置2: 添加超时
    logger.info("  配置2: 添加超时")
    try:
        w3 = Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 10}))
        is_connected = w3.is_connected()
        logger.info(f"    连接状态: {is_connected}")
    except Exception as e:
        logger.error(f"    失败: {e}")
    
    # 配置3: 添加PoA middleware
    logger.info("  配置3: 添加PoA middleware")
    try:
        w3 = Web3(Web3.HTTPProvider(url))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        is_connected = w3.is_connected()
        logger.info(f"    连接状态: {is_connected}")
    except Exception as e:
        logger.error(f"    失败: {e}")
    
    # 配置4: 禁用SSL验证
    logger.info("  配置4: 禁用SSL验证")
    try:
        w3 = Web3(Web3.HTTPProvider(url, request_kwargs={'verify': False}))
        is_connected = w3.is_connected()
        logger.info(f"    连接状态: {is_connected}")
    except Exception as e:
        logger.error(f"    失败: {e}")
    
    # 配置5: 自定义headers
    logger.info("  配置5: 自定义headers")
    try:
        w3 = Web3(Web3.HTTPProvider(url, request_kwargs={
            'headers': {'Content-Type': 'application/json'}
        }))
        is_connected = w3.is_connected()
        logger.info(f"    连接状态: {is_connected}")
    except Exception as e:
        logger.error(f"    失败: {e}")

def test_web3_version_compatibility():
    """测试Web3.py版本兼容性"""
    logger.info("🔄 测试Web3.py版本兼容性...")
    
    try:
        import web3
        version = web3.__version__
        logger.info(f"  Web3.py版本: {version}")
        
        # 检查关键模块
        modules = ['web3', 'web3.providers', 'web3.providers.HTTPProvider', 'web3.middleware']
        for module in modules:
            try:
                __import__(module)
                logger.info(f"    ✅ {module} 可用")
            except ImportError as e:
                logger.error(f"    ❌ {module} 不可用: {e}")
        
        # 检查HTTPProvider的具体实现
        from web3.providers import HTTPProvider
        logger.info(f"    HTTPProvider类: {HTTPProvider}")
        
        # 测试HTTPProvider实例化
        try:
            provider = HTTPProvider('http://localhost:8545')
            logger.info(f"    ✅ HTTPProvider实例化成功")
            
            # 测试provider的make_request方法
            try:
                response = provider.make_request('eth_blockNumber', [])
                logger.info(f"    ✅ Provider make_request成功: {response}")
            except Exception as e:
                logger.error(f"    ❌ Provider make_request失败: {e}")
                
        except Exception as e:
            logger.error(f"    ❌ HTTPProvider实例化失败: {e}")
            
    except Exception as e:
        logger.error(f"  Web3.py版本检查失败: {e}")

def test_network_connectivity():
    """测试网络连接性"""
    logger.info("🌍 测试网络连接性...")
    
    # 测试本地连接
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 8545))
        sock.close()
        logger.info(f"  本地8545端口连接: {'✅ 成功' if result == 0 else '❌ 失败'}")
    except Exception as e:
        logger.error(f"  本地8545端口连接测试失败: {e}")
    
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 8555))
        sock.close()
        logger.info(f"  本地8555端口连接: {'✅ 成功' if result == 0 else '❌ 失败'}")
    except Exception as e:
        logger.error(f"  本地8555端口连接测试失败: {e}")

def test_urllib3_compatibility():
    """测试urllib3兼容性"""
    logger.info("🔧 测试urllib3兼容性...")
    
    try:
        import urllib3
        logger.info(f"  urllib3版本: {urllib3.__version__}")
        
        # 测试urllib3直接请求
        http = urllib3.PoolManager()
        response = http.request('POST', 'http://localhost:8545', 
                              headers={'Content-Type': 'application/json'},
                              body=json.dumps({
                                  "jsonrpc": "2.0",
                                  "method": "eth_blockNumber",
                                  "params": [],
                                  "id": 1
                              }))
        logger.info(f"  urllib3请求状态: {response.status}")
        if response.status == 200:
            data = json.loads(response.data.decode('utf-8'))
            if 'result' in data:
                block_number = int(data['result'], 16)
                logger.info(f"  ✅ urllib3成功获取区块号: {block_number}")
            else:
                logger.error(f"  ❌ urllib3响应格式错误: {data}")
        else:
            logger.error(f"  ❌ urllib3请求失败: {response.data}")
            
    except Exception as e:
        logger.error(f"  urllib3测试失败: {e}")

def main():
    """主函数"""
    logger.info("🚀 开始Web3.py深度诊断")
    logger.info("=" * 70)
    
    # 1. 测试直接HTTP请求
    test_direct_http_requests()
    
    # 2. 测试网络连接性
    test_network_connectivity()
    
    # 3. 测试urllib3兼容性
    test_urllib3_compatibility()
    
    # 4. 测试Web3.py版本兼容性
    test_web3_version_compatibility()
    
    # 5. 测试Web3.py连接并调试
    test_web3_connection_with_debug()
    
    # 6. 测试Web3.py不同配置
    test_web3_with_different_configs()
    
    logger.info("\n" + "=" * 70)
    logger.info("📊 Web3.py深度诊断完成")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
