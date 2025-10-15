#!/bin/bash
# 跨链系统启动脚本

echo "🌐 跨链系统启动脚本"
echo "===================="

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到Python3，请先安装Python3"
    exit 1
fi

# 检查solc编译器
if ! command -v solc &> /dev/null; then
    echo "❌ 未找到solc编译器，请先安装Solidity编译器"
    echo "安装方法："
    echo "  Ubuntu/Debian: sudo apt install solc"
    echo "  macOS: brew install solidity"
    exit 1
fi

# 检查Besu链是否运行
echo "🔍 检查Besu链状态..."
if curl -s -X POST -H "Content-Type: application/json" \
   --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
   http://localhost:8545 > /dev/null; then
    echo "✅ Besu链A (端口8545) 正在运行"
else
    echo "❌ Besu链A (端口8545) 未运行，请先启动链A"
    echo "启动命令: docker-compose -f docker-compose1.yml up -d"
    exit 1
fi

if curl -s -X POST -H "Content-Type: application/json" \
   --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
   http://localhost:8555 > /dev/null; then
    echo "✅ Besu链B (端口8555) 正在运行"
else
    echo "❌ Besu链B (端口8555) 未运行，请先启动链B"
    echo "启动命令: docker-compose -f docker-compose2.yml up -d"
    exit 1
fi

echo ""
echo "🚀 开始部署跨链系统..."

# 1. 编译合约
echo "1️⃣ 编译智能合约..."
python3 compile_crosschain_contracts.py
if [ $? -ne 0 ]; then
    echo "❌ 合约编译失败"
    exit 1
fi

# 2. 部署系统
echo ""
echo "2️⃣ 部署跨链系统..."
python3 deploy_crosschain_system.py
if [ $? -ne 0 ]; then
    echo "❌ 系统部署失败"
    exit 1
fi

# 3. 运行测试
echo ""
echo "3️⃣ 运行系统测试..."
python3 test_crosschain_system.py
if [ $? -ne 0 ]; then
    echo "⚠️  测试过程中出现警告，请检查日志"
fi

echo ""
echo "🎉 跨链系统部署完成！"
echo ""
echo "📋 部署结果已保存到: cross_chain_deployment.json"
echo "📖 详细说明请查看: README_CrossChain.md"
echo ""
echo "🔧 下一步操作："
echo "1. 配置Oracle服务以支持跨链VC颁发"
echo "2. 验证用户身份"
echo "3. 开始进行跨链交易测试"
echo ""
echo "💡 提示："
echo "- 使用 test_crosschain_system.py 进行功能测试"
echo "- 查看 cross_chain_deployment.json 获取合约地址"
echo "- 参考 README_CrossChain.md 了解详细使用方法"
