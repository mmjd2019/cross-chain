#!/bin/bash

# 启动集成了VC功能的增强版Oracle服务

echo "🚀 启动增强版跨链Oracle服务 (集成VC功能)"
echo "================================================"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 检查必要的Python包
echo "📦 检查Python依赖包..."
python3 -c "import aiohttp, web3, eth_account" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ 缺少必要的Python包，请安装: pip install aiohttp web3 eth-account"
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

# 检查ACA-Py服务状态
echo "🔍 检查ACA-Py服务状态..."
if ! curl -s http://192.168.230.178:8080/status > /dev/null 2>&1; then
    echo "⚠️  发行者ACA-Py服务未运行 (端口8080)"
    echo "   请确保ACA-Py服务正在运行"
fi

if ! curl -s http://192.168.230.178:8081/status > /dev/null 2>&1; then
    echo "⚠️  持有者ACA-Py服务未运行 (端口8081)"
    echo "   请确保ACA-Py服务正在运行"
fi

# 检查Besu链连接
echo "🔗 检查Besu链连接..."
if ! curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' http://localhost:8545 > /dev/null 2>&1; then
    echo "⚠️  Besu链A (端口8545) 连接失败"
fi

if ! curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' http://localhost:8555 > /dev/null 2>&1; then
    echo "⚠️  Besu链B (端口8555) 连接失败"
fi

echo ""
echo "✅ 环境检查完成"
echo ""

# 选择运行模式
echo "请选择运行模式:"
echo "1) 启动Oracle服务"
echo "2) 运行测试"
echo "3) 运行测试并启动服务"
echo ""
read -p "请输入选择 (1-3): " choice

case $choice in
    1)
        echo "🚀 启动Oracle服务..."
        python3 enhanced_oracle_with_vc.py
        ;;
    2)
        echo "🧪 运行测试..."
        python3 test_oracle_vc_integration.py
        ;;
    3)
        echo "🧪 运行测试..."
        python3 test_oracle_vc_integration.py
        if [ $? -eq 0 ]; then
            echo ""
            echo "✅ 测试通过，启动Oracle服务..."
            python3 enhanced_oracle_with_vc.py
        else
            echo "❌ 测试失败，请检查配置"
            exit 1
        fi
        ;;
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac
