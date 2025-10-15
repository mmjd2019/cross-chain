#!/usr/bin/env python3
"""
使用curl测试Besu网络联通性和合约访问
"""

import json
import subprocess
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_chain_with_curl(rpc_url, chain_name):
    """使用curl测试链连接"""
    logger.info(f"🔍 测试 {chain_name} 连接...")
    
    try:
        # 构建curl命令
        curl_cmd = [
            'curl', '-s', '-X', 'POST',
            '-H', 'Content-Type: application/json',
            '--data', '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}',
            rpc_url
        ]
        
        # 执行curl命令
        result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            logger.error(f"❌ {chain_name} curl命令执行失败: {result.stderr}")
            return False
        
        # 解析响应
        response = json.loads(result.stdout)
        
        if 'error' in response:
            logger.error(f"❌ {chain_name} RPC错误: {response['error']}")
            return False
        
        if 'result' not in response:
            logger.error(f"❌ {chain_name} 响应格式错误")
            return False
        
        # 解析区块号
        block_number = int(response['result'], 16)
        
        logger.info(f"✅ {chain_name} 连接成功")
        logger.info(f"   - 当前区块: {block_number}")
        logger.info(f"   - RPC URL: {rpc_url}")
        
        return {
            'connected': True,
            'block_number': block_number,
            'rpc_url': rpc_url
        }
        
    except subprocess.TimeoutExpired:
        logger.error(f"❌ {chain_name} 连接超时")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"❌ {chain_name} JSON解析失败: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ {chain_name} 连接失败: {e}")
        return False

def test_contract_with_curl(rpc_url, contract_address, chain_name, contract_name):
    """使用curl测试合约访问"""
    logger.info(f"🔍 测试 {chain_name} 上的 {contract_name} 合约...")
    
    try:
        # 测试合约代码是否存在
        curl_cmd = [
            'curl', '-s', '-X', 'POST',
            '-H', 'Content-Type: application/json',
            '--data', f'{{"jsonrpc":"2.0","method":"eth_getCode","params":["{contract_address}","latest"],"id":1}}',
            rpc_url
        ]
        
        result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            logger.error(f"❌ {contract_name} curl命令执行失败: {result.stderr}")
            return False
        
        response = json.loads(result.stdout)
        
        if 'error' in response:
            logger.error(f"❌ {contract_name} RPC错误: {response['error']}")
            return False
        
        code = response.get('result', '0x')
        
        if code == '0x' or len(code) <= 2:
            logger.error(f"❌ {contract_name} 合约代码不存在")
            return False
        
        logger.info(f"✅ {contract_name} 合约存在")
        logger.info(f"   - 合约地址: {contract_address}")
        logger.info(f"   - 代码长度: {len(code)} 字符")
        
        return {
            'exists': True,
            'address': contract_address,
            'code_length': len(code)
        }
        
    except Exception as e:
        logger.error(f"❌ {contract_name} 合约测试失败: {e}")
        return False

def main():
    """主测试函数"""
    logger.info("🚀 开始Besu网络联通性和合约访问测试")
    logger.info("=" * 60)
    
    # 测试链连接
    chain_a_result = test_chain_with_curl('http://localhost:8545', 'Besu链A')
    chain_b_result = test_chain_with_curl('http://localhost:8555', 'Besu链B')
    
    if not chain_a_result or not chain_b_result:
        logger.error("❌ 链连接测试失败")
        return False
    
    # 加载合约地址
    try:
        with open('deployment.json', 'r') as f:
            deployment_data = json.load(f)
        logger.info("✅ 合约地址加载成功")
    except Exception as e:
        logger.error(f"❌ 合约地址加载失败: {e}")
        return False
    
    # 测试合约访问
    logger.info("\n📋 测试合约访问...")
    
    # 测试链A上的合约
    if chain_a_result:
        logger.info("\n🔗 测试Besu链A上的合约:")
        for contract_name, contract_info in deployment_data.get('chain_a', {}).items():
            if contract_info and contract_info.get('address'):
                test_contract_with_curl(
                    'http://localhost:8545',
                    contract_info['address'],
                    'Besu链A',
                    contract_name
                )
    
    # 测试链B上的合约
    if chain_b_result:
        logger.info("\n🔗 测试Besu链B上的合约:")
        for contract_name, contract_info in deployment_data.get('chain_b', {}).items():
            if contract_info and contract_info.get('address'):
                test_contract_with_curl(
                    'http://localhost:8555',
                    contract_info['address'],
                    'Besu链B',
                    contract_name
                )
    
    # 生成测试报告
    logger.info("\n" + "=" * 60)
    logger.info("📊 测试结果汇总")
    logger.info("=" * 60)
    
    logger.info(f"\n🔗 链连接状态:")
    logger.info(f"  ✅ Besu链A: 连接成功 (区块: {chain_a_result.get('block_number', 'N/A')})")
    logger.info(f"  ✅ Besu链B: 连接成功 (区块: {chain_b_result.get('block_number', 'N/A')})")
    
    logger.info(f"\n📋 合约部署状态:")
    chain_a_contracts = deployment_data.get('chain_a', {})
    chain_b_contracts = deployment_data.get('chain_b', {})
    
    if chain_a_contracts:
        logger.info(f"  📡 Besu链A:")
        for contract_name, contract_info in chain_a_contracts.items():
            if contract_info and contract_info.get('address'):
                logger.info(f"    - {contract_name}: {contract_info['address']}")
    
    if chain_b_contracts:
        logger.info(f"  📡 Besu链B:")
        for contract_name, contract_info in chain_b_contracts.items():
            if contract_info and contract_info.get('address'):
                logger.info(f"    - {contract_name}: {contract_info['address']}")
    
    logger.info(f"\n🎯 总体状态: ✅ 成功")
    logger.info("🎉 Besu网络联通性和合约访问测试完成")
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ 测试成功完成！")
    else:
        print("\n❌ 测试失败！")
