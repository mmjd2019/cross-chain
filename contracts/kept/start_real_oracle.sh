#!/bin/bash

# 启动真实事件监控Oracle服务

echo "🚀 启动真实事件监控Oracle服务..."
echo "=================================="

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 检查依赖
echo "🔍 检查依赖..."
python3 -c "import web3, aiohttp, eth_account" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ 缺少必要的Python依赖"
    echo "请运行: pip install web3 aiohttp eth-account"
    exit 1
fi

# 检查配置文件
if [ ! -f "cross_chain_config.json" ]; then
    echo "❌ 配置文件 cross_chain_config.json 不存在"
    exit 1
fi

if [ ! -f "cross_chain_vc_config.json" ]; then
    echo "❌ VC配置文件 cross_chain_vc_config.json 不存在"
    exit 1
fi

# 检查合约ABI文件
if [ ! -f "CrossChainBridge.json" ]; then
    echo "❌ 合约ABI文件 CrossChainBridge.json 不存在"
    exit 1
fi

if [ ! -f "CrossChainDIDVerifier.json" ]; then
    echo "❌ 合约ABI文件 CrossChainDIDVerifier.json 不存在"
    exit 1
fi

# 检查Besu链连接
echo "🔍 检查Besu链连接..."
curl -s -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  http://localhost:8545 > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ Besu链A连接失败"
    exit 1
fi

curl -s -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  http://localhost:8555 > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ Besu链B连接失败"
    exit 1
fi

echo "✅ Besu链连接正常"

# 检查ACA-Py服务
echo "🔍 检查ACA-Py服务..."
curl -s http://192.168.230.178:8080/status > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ ACA-Py发行者服务连接失败"
    exit 1
fi

curl -s http://192.168.230.178:8081/status > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ ACA-Py持有者服务连接失败"
    exit 1
fi

echo "✅ ACA-Py服务连接正常"

# 创建日志目录
mkdir -p logs

# 启动Oracle服务
echo "🚀 启动真实事件监控Oracle服务..."
echo "📝 日志文件: real_oracle.log"
echo "⏹️  按 Ctrl+C 停止服务"
echo "=================================="

python3 real_event_monitoring_oracle.py
