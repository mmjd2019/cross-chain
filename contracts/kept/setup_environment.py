# -*- coding: utf-8 -*-
"""
环境设置脚本 - 帮助用户配置必要的环境变量
"""
import os
import json
from pathlib import Path

def create_env_file():
    """创建.env文件"""
    env_file = Path(".env")
    
    if env_file.exists():
        print("⚠️  .env文件已存在，是否要覆盖？(y/N): ", end="")
        if input().lower() != 'y':
            print("取消创建.env文件")
            return
    
    print("\n=== 智能合约开发环境配置 ===")
    print("请提供以下信息来配置您的开发环境：\n")
    
    # 网络配置
    print("1. Besu网络配置")
    besu_rpc = input("Besu RPC地址 (默认: http://192.168.1.224:8545): ").strip()
    if not besu_rpc:
        besu_rpc = "http://192.168.1.224:8545"
    
    chain_id = input("链ID (默认: 2023): ").strip()
    if not chain_id:
        chain_id = "2023"
    
    # 账户配置
    print("\n2. 部署账户配置")
    print("⚠️  请确保您有足够的ETH来支付Gas费")
    private_key = input("部署账户私钥 (0x开头): ").strip()
    
    if not private_key.startswith('0x'):
        private_key = '0x' + private_key
    
    # 验证私钥格式
    if len(private_key) != 66:
        print("❌ 私钥格式错误，应该是64位十六进制字符")
        return
    
    # 从私钥推导地址
    try:
        from web3 import Web3
        account = Web3().eth.account.from_key(private_key)
        address = account.address
        print(f"✅ 从私钥推导的地址: {address}")
    except Exception as e:
        print(f"❌ 私钥无效: {e}")
        return
    
    # Gas配置
    print("\n3. Gas配置")
    gas_limit = input("Gas限制 (默认: 2000000): ").strip()
    if not gas_limit:
        gas_limit = "2000000"
    
    gas_price = input("Gas价格 (默认: 0，Besu测试网免费): ").strip()
    if not gas_price:
        gas_price = "0"
    
    # 创建.env文件
    env_content = f"""# 智能合约开发环境变量
# 自动生成于 {os.popen('date').read().strip()}

# Besu网络配置
BESU_RPC_URL={besu_rpc}
CHAIN_ID={chain_id}

# 部署账户配置
DEPLOYER_PRIVATE_KEY={private_key}
DEPLOYER_ADDRESS={address}

# Gas配置
GAS_LIMIT={gas_limit}
GAS_PRICE={gas_price}

# 调试模式
DEBUG=False
"""
    
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print(f"\n✅ 环境配置文件已创建: {env_file.absolute()}")
    print("\n=== 配置摘要 ===")
    print(f"Besu RPC: {besu_rpc}")
    print(f"链ID: {chain_id}")
    print(f"部署地址: {address}")
    print(f"Gas限制: {gas_limit}")
    print(f"Gas价格: {gas_price}")
    
    # 测试网络连接
    print("\n=== 测试网络连接 ===")
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(besu_rpc))
        if w3.is_connected():
            print("✅ 网络连接成功")
            
            # 检查账户余额
            balance = w3.eth.get_balance(address)
            balance_eth = w3.from_wei(balance, 'ether')
            print(f"✅ 账户余额: {balance_eth} ETH")
            
            if balance == 0:
                print("⚠️  警告: 账户余额为0，可能无法部署合约")
        else:
            print("❌ 网络连接失败")
    except Exception as e:
        print(f"❌ 网络测试失败: {e}")

def main():
    """主函数"""
    print("🔧 智能合约开发环境设置工具")
    print("=" * 50)
    
    try:
        create_env_file()
        print("\n🎉 环境设置完成！")
        print("\n下一步:")
        print("1. 运行 'python compile_contracts.py' 编译合约")
        print("2. 运行 'python deploy_contracts.py' 部署合约")
        print("3. 运行 'python test_contracts.py' 测试合约")
        
    except KeyboardInterrupt:
        print("\n\n❌ 用户取消设置")
    except Exception as e:
        print(f"\n❌ 设置过程中出错: {e}")

if __name__ == "__main__":
    main()
