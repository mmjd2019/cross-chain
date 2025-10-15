# -*- coding: utf-8 -*-
"""
智能合约配置文件
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class ContractConfig:
    # Besu网络配置
    BESU_RPC_URL = os.getenv("BESU_RPC_URL", "http://localhost:8545")
    CHAIN_ID = int(os.getenv("CHAIN_ID", "2023"))
    
    # 部署账户配置
    DEPLOYER_PRIVATE_KEY = os.getenv("DEPLOYER_PRIVATE_KEY")
    DEPLOYER_ADDRESS = os.getenv("DEPLOYER_ADDRESS")
    
    # Gas配置
    GAS_LIMIT = int(os.getenv("GAS_LIMIT", "2000000"))
    GAS_PRICE = int(os.getenv("GAS_PRICE", "0"))  # Besu测试网免费
    
    # 合约配置
    CONTRACTS_DIR = "contracts"
    BUILD_DIR = "build"
    ABI_DIR = "abi"
    
    # 网络配置
    NETWORK_CONFIG = {
        "name": "Besu IBFT",
        "rpc_url": BESU_RPC_URL,
        "chain_id": CHAIN_ID,
        "gas_price": GAS_PRICE
    }
