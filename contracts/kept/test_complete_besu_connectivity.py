#!/usr/bin/env python3
"""
完整的Besu网络联通性和合约访问测试
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
        curl_cmd = [
            'curl', '-s', '-X', 'POST',
            '-H', 'Content-Type: application/json',
            '--data', '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}',
            rpc_url
        ]
        
        result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            logger.error(f"❌ {chain_name} curl命令执行失败: {result.stderr}")
            return False
        
        response = json.loads(result.stdout)
        
        if 'error' in response:
            logger.error(f"❌ {chain_name} RPC错误: {response['error']}")
            return False
        
        block_number = int(response['result'], 16)
        
        logger.info(f"✅ {chain_name} 连接成功")
        logger.info(f"   - 当前区块: {block_number}")
        logger.info(f"   - RPC URL: {rpc_url}")
        
        return {
            'connected': True,
            'block_number': block_number,
            'rpc_url': rpc_url
        }
        
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

def test_contract_function_call(rpc_url, contract_address, chain_name, contract_name):
    """测试合约函数调用"""
    logger.info(f"🔍 测试 {chain_name} 上的 {contract_name} 函数调用...")
    
    try:
        # 测试owner函数调用
        curl_cmd = [
            'curl', '-s', '-X', 'POST',
            '-H', 'Content-Type: application/json',
            '--data', f'{{"jsonrpc":"2.0","method":"eth_call","params":[{{"to":"{contract_address}","data":"0x8da5cb5b"}},"latest"],"id":1}}',
            rpc_url
        ]
        
        result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            logger.warning(f"⚠️  {contract_name} 函数调用失败: {result.stderr}")
            return False
        
        response = json.loads(result.stdout)
        
        if 'error' in response:
            logger.warning(f"⚠️  {contract_name} 函数调用RPC错误: {response['error']}")
            return False
        
        result_data = response.get('result', '0x')
        
        if result_data != '0x':
            logger.info(f"✅ {contract_name} 函数调用成功")
            logger.info(f"   - 返回数据: {result_data}")
            return True
        else:
            logger.warning(f"⚠️  {contract_name} 函数调用返回空数据")
            return False
        
    except Exception as e:
        logger.warning(f"⚠️  {contract_name} 函数调用测试失败: {e}")
        return False

def main():
    """主测试函数"""
    logger.info("🚀 开始Besu网络联通性和合约访问综合测试")
    logger.info("=" * 70)
    
    # 测试链连接
    chain_a_result = test_chain_with_curl('http://localhost:8545', 'Besu链A')
    chain_b_result = test_chain_with_curl('http://localhost:8555', 'Besu链B')
    
    if not chain_a_result or not chain_b_result:
        logger.error("❌ 链连接测试失败")
        return False
    
    # 加载合约地址
    try:
        with open('final_bridge_deployment_results.json', 'r') as f:
            deployment_data = json.load(f)
        logger.info("✅ 合约地址加载成功")
    except Exception as e:
        logger.error(f"❌ 合约地址加载失败: {e}")
        return False
    
    # 测试合约访问
    logger.info("\n📋 测试合约访问...")
    
    test_results = {
        'chain_a': {'contracts': {}},
        'chain_b': {'contracts': {}}
    }
    
    # 测试链A上的合约
    if chain_a_result:
        logger.info("\n🔗 测试Besu链A上的合约:")
        chain_a_data = deployment_data.get('chain_a', {})
        
        # 测试验证器合约
        verifier_address = chain_a_data.get('verifier')
        if verifier_address:
            contract_result = test_contract_with_curl(
                'http://localhost:8545',
                verifier_address,
                'Besu链A',
                'DIDVerifier'
            )
            test_results['chain_a']['contracts']['DIDVerifier'] = contract_result
            
            if contract_result and contract_result.get('exists'):
                test_contract_function_call(
                    'http://localhost:8545',
                    verifier_address,
                    'Besu链A',
                    'DIDVerifier'
                )
        
        # 测试跨链桥合约
        bridge_address = chain_a_data.get('contracts', {}).get('cross_chain_bridge')
        if bridge_address:
            contract_result = test_contract_with_curl(
                'http://localhost:8545',
                bridge_address,
                'Besu链A',
                'CrossChainBridge'
            )
            test_results['chain_a']['contracts']['CrossChainBridge'] = contract_result
            
            if contract_result and contract_result.get('exists'):
                test_contract_function_call(
                    'http://localhost:8545',
                    bridge_address,
                    'Besu链A',
                    'CrossChainBridge'
                )
    
    # 测试链B上的合约
    if chain_b_result:
        logger.info("\n🔗 测试Besu链B上的合约:")
        chain_b_data = deployment_data.get('chain_b', {})
        
        # 测试验证器合约
        verifier_address = chain_b_data.get('verifier')
        if verifier_address:
            contract_result = test_contract_with_curl(
                'http://localhost:8555',
                verifier_address,
                'Besu链B',
                'DIDVerifier'
            )
            test_results['chain_b']['contracts']['DIDVerifier'] = contract_result
            
            if contract_result and contract_result.get('exists'):
                test_contract_function_call(
                    'http://localhost:8555',
                    verifier_address,
                    'Besu链B',
                    'DIDVerifier'
                )
        
        # 测试跨链桥合约
        bridge_address = chain_b_data.get('contracts', {}).get('cross_chain_bridge')
        if bridge_address:
            contract_result = test_contract_with_curl(
                'http://localhost:8555',
                bridge_address,
                'Besu链B',
                'CrossChainBridge'
            )
            test_results['chain_b']['contracts']['CrossChainBridge'] = contract_result
            
            if contract_result and contract_result.get('exists'):
                test_contract_function_call(
                    'http://localhost:8555',
                    bridge_address,
                    'Besu链B',
                    'CrossChainBridge'
                )
    
    # 生成测试报告
    logger.info("\n" + "=" * 70)
    logger.info("📊 测试结果汇总")
    logger.info("=" * 70)
    
    logger.info(f"\n🔗 链连接状态:")
    logger.info(f"  ✅ Besu链A: 连接成功 (区块: {chain_a_result.get('block_number', 'N/A')})")
    logger.info(f"  ✅ Besu链B: 连接成功 (区块: {chain_b_result.get('block_number', 'N/A')})")
    
    logger.info(f"\n📋 合约部署和访问状态:")
    
    # 链A合约状态
    logger.info(f"  📡 Besu链A:")
    chain_a_contracts = test_results['chain_a']['contracts']
    for contract_name, contract_result in chain_a_contracts.items():
        if contract_result and contract_result.get('exists'):
            logger.info(f"    ✅ {contract_name}: 存在 ({contract_result['address']})")
        else:
            logger.info(f"    ❌ {contract_name}: 不存在或无法访问")
    
    # 链B合约状态
    logger.info(f"  📡 Besu链B:")
    chain_b_contracts = test_results['chain_b']['contracts']
    for contract_name, contract_result in chain_b_contracts.items():
        if contract_result and contract_result.get('exists'):
            logger.info(f"    ✅ {contract_name}: 存在 ({contract_result['address']})")
        else:
            logger.info(f"    ❌ {contract_name}: 不存在或无法访问")
    
    # 统计信息
    total_contracts = len(chain_a_contracts) + len(chain_b_contracts)
    working_contracts = sum(1 for contracts in [chain_a_contracts, chain_b_contracts] 
                          for result in contracts.values() 
                          if result and result.get('exists'))
    
    logger.info(f"\n📈 统计信息:")
    logger.info(f"  - 总合约数: {total_contracts}")
    logger.info(f"  - 可访问合约数: {working_contracts}")
    logger.info(f"  - 成功率: {(working_contracts/total_contracts*100):.1f}%" if total_contracts > 0 else "  - 成功率: N/A")
    
    logger.info(f"\n🎯 总体状态: {'✅ 成功' if working_contracts > 0 else '❌ 失败'}")
    logger.info("🎉 Besu网络联通性和合约访问测试完成")
    
    # 保存详细结果
    with open('besu_connectivity_detailed_results.json', 'w') as f:
        json.dump({
            'chain_a': chain_a_result,
            'chain_b': chain_b_result,
            'contracts': test_results,
            'summary': {
                'total_contracts': total_contracts,
                'working_contracts': working_contracts,
                'success_rate': working_contracts/total_contracts*100 if total_contracts > 0 else 0
            }
        }, f, indent=2, default=str)
    
    logger.info("📄 详细结果已保存到: besu_connectivity_detailed_results.json")
    
    return working_contracts > 0

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ 测试成功完成！")
    else:
        print("\n❌ 测试失败！")
