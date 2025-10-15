#!/bin/bash

# 跨链Oracle服务启动脚本

echo "🚀 启动跨链Oracle服务"
echo "================================"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 检查必要的Python包
echo "📦 检查Python依赖..."
python3 -c "import web3, requests, asyncio" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ 缺少必要的Python包，请安装: pip3 install web3 requests"
    exit 1
fi

# 检查配置文件
if [ ! -f "cross_chain_config.json" ]; then
    echo "❌ 配置文件 cross_chain_config.json 不存在"
    exit 1
fi

# 检查合约ABI文件
if [ ! -f "CrossChainBridgeSimple.json" ] || [ ! -f "CrossChainDIDVerifier.json" ]; then
    echo "❌ 合约ABI文件不存在，请先编译合约"
    exit 1
fi

# 检查Besu链连接
echo "🔗 检查Besu链连接..."
python3 -c "
from web3 import Web3
import sys

# 检查链A
w3_a = Web3(Web3.HTTPProvider('http://localhost:8545'))
if not w3_a.is_connected():
    print('❌ 无法连接到Besu链A (端口8545)')
    sys.exit(1)
else:
    print('✅ Besu链A连接正常')

# 检查链B
w3_b = Web3(Web3.HTTPProvider('http://localhost:8555'))
if not w3_b.is_connected():
    print('❌ 无法连接到Besu链B (端口8555)')
    sys.exit(1)
else:
    print('✅ Besu链B连接正常')
"

if [ $? -ne 0 ]; then
    echo "❌ Besu链连接检查失败"
    exit 1
fi

# 检查ACA-Py连接
echo "🔗 检查ACA-Py连接..."
python3 -c "
import requests
import sys

try:
    response = requests.get('http://localhost:8001/status', timeout=5)
    if response.status_code == 200:
        print('✅ ACA-Py连接正常')
    else:
        print('⚠️  ACA-Py连接异常，但将继续启动')
except:
    print('⚠️  无法连接到ACA-Py，但将继续启动')
"

# 创建日志目录
mkdir -p logs

# 启动Oracle服务
echo "🚀 启动Oracle服务..."
echo "================================"

# 选择启动模式
if [ "$1" = "enhanced" ]; then
    echo "启动增强版Oracle服务..."
    python3 enhanced_oracle.py
elif [ "$1" = "v6" ]; then
    echo "启动Web3.py v6兼容版Oracle服务..."
    python3 oracle_v6_compatible.py
else
    echo "启动Web3.py v6兼容版Oracle服务（默认）..."
    python3 oracle_v6_compatible.py
fi
