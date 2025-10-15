#!/usr/bin/env python3
"""
Web3.py连接诊断脚本
检查Web3.py版本兼容性和连接问题
"""

import json
import subprocess
import logging
from web3 import Web3
from web3.middleware import geth_poa_middleware
import requests

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_web3_version():
    """检查Web3.py版本"""
    try:
        import web3
        version = web3.__version__
        logger.info(f"Web3.py版本: {version}")
        
        # 检查主要版本
        major_version = int(version.split('.')[0])
        if major_version >= 6:
            logger.info("✅ 使用Web3.py v6+ (最新版本)")
        elif major_version == 5:
            logger.info("⚠️ 使用Web3.py v5 (较旧版本)")
        else:
            logger.warning("❌ 使用Web3.py v4或更早版本 (可能不兼容)")
        
        return version, major_version
    except Exception as e:
        logger.error(f"无法获取Web3.py版本: {e}")
        return None, None

def check_besu_connectivity():
    """检查Besu连接性"""
    chains = {
        'chain_a': 'http://localhost:8545',
        'chain_b': 'http://localhost:8555'
    }
    
    results = {}
    
    for chain_name, url in chains.items():
        logger.info(f"🔍 检查 {chain_name} 连接性...")
        
        # 1. 使用requests检查HTTP连接
        try:
            response = requests.get(url, timeout=5)
            logger.info(f"  HTTP状态码: {response.status_code}")
        except Exception as e:
            logger.error(f"  HTTP连接失败: {e}")
            results[chain_name] = {'http': False, 'error': str(e)}
            continue
        
        # 2. 使用curl检查RPC
        try:
            curl_cmd = [
                'curl', '-s', '-X', 'POST',
                '-H', 'Content-Type: application/json',
                '--data', '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}',
                url
            ]
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                response = json.loads(result.stdout)
                if 'result' in response:
                    block_number = int(response['result'], 16)
                    logger.info(f"  ✅ RPC连接成功，当前区块: {block_number}")
                    results[chain_name] = {'http': True, 'rpc': True, 'block_number': block_number}
                else:
                    logger.error(f"  ❌ RPC响应错误: {response}")
                    results[chain_name] = {'http': True, 'rpc': False, 'error': response}
            else:
                logger.error(f"  ❌ curl命令失败: {result.stderr}")
                results[chain_name] = {'http': True, 'rpc': False, 'error': result.stderr}
        except Exception as e:
            logger.error(f"  ❌ RPC检查失败: {e}")
            results[chain_name] = {'http': True, 'rpc': False, 'error': str(e)}
    
    return results

def test_web3_connection():
    """测试Web3.py连接"""
    chains = {
        'chain_a': 'http://localhost:8545',
        'chain_b': 'http://localhost:8555'
    }
    
    results = {}
    
    for chain_name, url in chains.items():
        logger.info(f"🔗 测试Web3.py连接 {chain_name}...")
        
        try:
            # 创建Web3实例
            w3 = Web3(Web3.HTTPProvider(url))
            
            # 测试基本连接
            is_connected = w3.is_connected()
            logger.info(f"  连接状态: {is_connected}")
            
            if is_connected:
                # 获取链ID
                try:
                    chain_id = w3.eth.chain_id
                    logger.info(f"  链ID: {chain_id}")
                except Exception as e:
                    logger.error(f"  获取链ID失败: {e}")
                    chain_id = None
                
                # 获取最新区块
                try:
                    latest_block = w3.eth.get_block('latest')
                    block_number = latest_block.number
                    logger.info(f"  最新区块: {block_number}")
                except Exception as e:
                    logger.error(f"  获取最新区块失败: {e}")
                    block_number = None
                
                # 获取gas价格
                try:
                    gas_price = w3.eth.gas_price
                    logger.info(f"  Gas价格: {gas_price}")
                except Exception as e:
                    logger.error(f"  获取Gas价格失败: {e}")
                    gas_price = None
                
                results[chain_name] = {
                    'connected': True,
                    'chain_id': chain_id,
                    'block_number': block_number,
                    'gas_price': gas_price
                }
            else:
                results[chain_name] = {'connected': False, 'error': '连接失败'}
                
        except Exception as e:
            logger.error(f"  Web3.py连接失败: {e}")
            results[chain_name] = {'connected': False, 'error': str(e)}
    
    return results

def test_web3_with_middleware():
    """测试Web3.py with middleware"""
    logger.info("🔧 测试Web3.py with PoA middleware...")
    
    try:
        w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
        
        # 添加PoA middleware (Besu使用PoA共识)
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        is_connected = w3.is_connected()
        logger.info(f"  添加middleware后连接状态: {is_connected}")
        
        if is_connected:
            chain_id = w3.eth.chain_id
            logger.info(f"  链ID: {chain_id}")
            
            # 测试获取账户余额
            test_address = "0x81Be24626338695584B5beaEBf51e09879A0eCc6"
            balance = w3.eth.get_balance(test_address)
            logger.info(f"  测试账户余额: {balance / 10**18} ETH")
            
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"  Web3.py with middleware失败: {e}")
        return False

def test_web3_v5_compatibility():
    """测试Web3.py v5兼容性"""
    logger.info("🔄 测试Web3.py v5兼容性...")
    
    try:
        w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
        
        # 使用v5风格的API
        is_connected = w3.isConnected()
        logger.info(f"  v5风格连接状态: {is_connected}")
        
        if is_connected:
            # 使用v5风格的API
            chain_id = w3.eth.chainId
            logger.info(f"  v5风格链ID: {chain_id}")
            
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"  Web3.py v5兼容性测试失败: {e}")
        return False

def check_docker_containers():
    """检查Docker容器状态"""
    logger.info("🐳 检查Docker容器状态...")
    
    try:
        result = subprocess.run(['docker', 'ps'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            besu_containers = [line for line in lines if 'besu' in line.lower()]
            
            logger.info(f"  找到 {len(besu_containers)} 个Besu容器:")
            for container in besu_containers:
                logger.info(f"    {container}")
            
            return len(besu_containers) > 0
        else:
            logger.error(f"  Docker命令失败: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"  检查Docker容器失败: {e}")
        return False

def main():
    """主函数"""
    logger.info("🚀 开始Web3.py连接诊断")
    logger.info("=" * 70)
    
    # 1. 检查Web3.py版本
    version, major_version = check_web3_version()
    
    # 2. 检查Docker容器
    docker_ok = check_docker_containers()
    
    # 3. 检查Besu连接性
    besu_results = check_besu_connectivity()
    
    # 4. 测试Web3.py连接
    web3_results = test_web3_connection()
    
    # 5. 测试Web3.py with middleware
    middleware_ok = test_web3_with_middleware()
    
    # 6. 测试Web3.py v5兼容性
    v5_ok = test_web3_v5_compatibility()
    
    # 生成诊断报告
    logger.info("\n" + "=" * 70)
    logger.info("📊 Web3.py连接诊断报告")
    logger.info("=" * 70)
    
    logger.info(f"Web3.py版本: {version}")
    logger.info(f"Docker容器状态: {'✅ 正常' if docker_ok else '❌ 异常'}")
    
    for chain_name, result in besu_results.items():
        logger.info(f"\n{chain_name}:")
        logger.info(f"  HTTP连接: {'✅ 成功' if result.get('http') else '❌ 失败'}")
        logger.info(f"  RPC连接: {'✅ 成功' if result.get('rpc') else '❌ 失败'}")
        if 'block_number' in result:
            logger.info(f"  当前区块: {result['block_number']}")
        if 'error' in result:
            logger.info(f"  错误: {result['error']}")
    
    for chain_name, result in web3_results.items():
        logger.info(f"\nWeb3.py {chain_name}:")
        logger.info(f"  连接状态: {'✅ 成功' if result.get('connected') else '❌ 失败'}")
        if 'chain_id' in result:
            logger.info(f"  链ID: {result['chain_id']}")
        if 'block_number' in result:
            logger.info(f"  区块号: {result['block_number']}")
        if 'error' in result:
            logger.info(f"  错误: {result['error']}")
    
    logger.info(f"\nPoA Middleware: {'✅ 有效' if middleware_ok else '❌ 无效'}")
    logger.info(f"v5兼容性: {'✅ 有效' if v5_ok else '❌ 无效'}")
    
    # 保存诊断结果
    diagnosis_results = {
        'web3_version': version,
        'web3_major_version': major_version,
        'docker_status': docker_ok,
        'besu_connectivity': besu_results,
        'web3_connection': web3_results,
        'middleware_working': middleware_ok,
        'v5_compatibility': v5_ok
    }
    
    with open('web3_diagnosis_results.json', 'w') as f:
        json.dump(diagnosis_results, f, indent=2, default=str)
    
    logger.info(f"\n📄 详细诊断结果已保存到: web3_diagnosis_results.json")

if __name__ == "__main__":
    main()
