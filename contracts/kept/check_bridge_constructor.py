#!/usr/bin/env python3
"""
检查桥接合约构造函数参数
查看桥接合约的构造函数参数和状态
"""

import json
from web3_fixed_connection import FixedWeb3

def check_bridge_constructor():
    """检查桥接合约构造函数参数"""
    print("🔍 检查桥接合约构造函数参数...")
    
    # 链A配置
    w3 = FixedWeb3('http://localhost:8545', 'Besu Chain A')
    bridge_address = '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af'
    
    # 加载桥接合约ABI
    with open('CrossChainBridge.json', 'r') as f:
        bridge_abi = json.load(f)['abi']
    
    bridge_contract = w3.w3.eth.contract(
        address=w3.w3.to_checksum_address(bridge_address),
        abi=bridge_abi
    )
    
    print(f"🔍 桥接合约地址: {bridge_address}")
    
    try:
        # 获取所有者
        owner = bridge_contract.functions.owner().call()
        print(f"🔍 所有者: {owner}")
        
        # 获取桥接操作员
        bridge_operator = bridge_contract.functions.bridgeOperator().call()
        print(f"🔍 桥接操作员: {bridge_operator}")
        
        # 获取链ID
        chain_id = bridge_contract.functions.chainId().call()
        print(f"🔍 链ID: {chain_id}")
        
        # 获取链类型
        chain_type = bridge_contract.functions.chainType().call()
        print(f"🔍 链类型: {chain_type}")
        
        # 获取验证器地址
        verifier = bridge_contract.functions.verifier().call()
        print(f"🔍 验证器地址: {verifier}")
        
        # 检查是否有支持的代币
        print("\n🔍 检查支持的代币...")
        # 这里我们需要知道代币地址才能检查
        
        # 检查链支持
        print("\n🔍 检查链支持...")
        try:
            is_chain_supported = bridge_contract.functions.isChainSupported("chain_b").call()
            print(f"🔍 链B是否支持: {is_chain_supported}")
        except Exception as e:
            print(f"❌ 检查链支持失败: {e}")
        
        # 检查代币支持
        print("\n🔍 检查代币支持...")
        token_address = '0x14D83c34ba0E1caC363039699d495e733B8A1182'
        try:
            is_token_supported = bridge_contract.functions.isTokenSupported(
                w3.w3.to_checksum_address(token_address)
            ).call()
            print(f"🔍 代币 {token_address} 是否支持: {is_token_supported}")
        except Exception as e:
            print(f"❌ 检查代币支持失败: {e}")
        
        # 检查代币信息
        print("\n🔍 检查代币信息...")
        try:
            token_info = bridge_contract.functions.getTokenInfo(
                w3.w3.to_checksum_address(token_address)
            ).call()
            print(f"🔍 代币信息: {token_info}")
        except Exception as e:
            print(f"❌ 检查代币信息失败: {e}")
        
    except Exception as e:
        print(f"❌ 检查桥接合约失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_bridge_constructor()

