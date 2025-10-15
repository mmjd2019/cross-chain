#!/usr/bin/env python3
"""
简化的Besu网络联通性和合约访问测试
"""

import json
import logging
from web3 import Web3

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_chain_connection(rpc_url, chain_name):
    """测试单链连接"""
    logger.info(f"🔍 测试 {chain_name} 连接...")
    
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        if not w3.is_connected():
            logger.error(f"❌ {chain_name} 连接失败")
            return False
        
        # 获取链信息
        block_number = w3.eth.block_number
        chain_id = w3.eth.chain_id
        gas_price = w3.eth.gas_price
        accounts = w3.eth.accounts
        
        logger.info(f"✅ {chain_name} 连接成功")
        logger.info(f"   - 当前区块: {block_number}")
        logger.info(f"   - 链ID: {chain_id}")
        logger.info(f"   - Gas价格: {w3.from_wei(gas_price, 'gwei')} Gwei")
        logger.info(f"   - 账户数量: {len(accounts)}")
        
        return {
            'connected': True,
            'block_number': block_number,
            'chain_id': chain_id,
            'gas_price': gas_price,
            'accounts_count': len(accounts)
        }
        
    except Exception as e:
        logger.error(f"❌ {chain_name} 连接失败: {e}")
        return False

def test_contract_access(w3, contract_address, abi_file, contract_name):
    """测试合约访问"""
    logger.info(f"🔍 测试 {contract_name} 合约访问...")
    
    try:
        # 加载ABI
        with open(abi_file, 'r') as f:
            abi = json.load(f)
        
        # 创建合约实例
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=abi
        )
        
        # 测试基本函数
        test_results = {}
        
        # 尝试调用owner函数
        try:
            if hasattr(contract.functions, 'owner'):
                owner = contract.functions.owner().call()
                test_results['owner'] = owner
                logger.info(f"   - 合约所有者: {owner}")
        except Exception as e:
            logger.warning(f"   - 无法获取owner: {e}")
        
        # 尝试调用chainId函数
        try:
            if hasattr(contract.functions, 'chainId'):
                chain_id = contract.functions.chainId().call()
                test_results['chain_id'] = chain_id
                logger.info(f"   - 合约链ID: {chain_id}")
        except Exception as e:
            logger.warning(f"   - 无法获取chainId: {e}")
        
        logger.info(f"✅ {contract_name} 合约访问成功")
        return {
            'accessible': True,
            'address': contract_address,
            'test_results': test_results
        }
        
    except Exception as e:
        logger.error(f"❌ {contract_name} 合约访问失败: {e}")
        return {
            'accessible': False,
            'address': contract_address,
            'error': str(e)
        }

def main():
    """主测试函数"""
    logger.info("🚀 开始Besu网络联通性和合约访问测试")
    logger.info("=" * 50)
    
    # 测试链连接
    chain_a_result = test_chain_connection('http://localhost:8545', 'Besu链A')
    chain_b_result = test_chain_connection('http://localhost:8555', 'Besu链B')
    
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
        w3_a = Web3(Web3.HTTPProvider('http://localhost:8545'))
        logger.info("\n🔗 测试Besu链A上的合约:")
        
        for contract_name, contract_info in deployment_data.get('chain_a', {}).items():
            if contract_info and contract_info.get('address'):
                abi_file = f"{contract_name}.json"
                contract_result = test_contract_access(
                    w3_a, contract_info['address'], abi_file, contract_name
                )
    
    # 测试链B上的合约
    if chain_b_result:
        w3_b = Web3(Web3.HTTPProvider('http://localhost:8555'))
        logger.info("\n🔗 测试Besu链B上的合约:")
        
        for contract_name, contract_info in deployment_data.get('chain_b', {}).items():
            if contract_info and contract_info.get('address'):
                abi_file = f"{contract_name}.json"
                contract_result = test_contract_access(
                    w3_b, contract_info['address'], abi_file, contract_name
                )
    
    logger.info("\n" + "=" * 50)
    logger.info("🎉 Besu网络联通性和合约访问测试完成")
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ 测试成功完成！")
    else:
        print("\n❌ 测试失败！")
