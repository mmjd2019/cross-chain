#!/bin/bash
# VC发行Oracle服务启动脚本 (HTTP模式)

cd /home/manifold/cursor/cross-chain-new/VcIssureOracle

# 设置环境变量
export FLASK_APP=vc_issuance_oracle.py
export FLASK_ENV=production
export PYTHONPATH=/home/manifold/cursor/cross-chain-new/VcIssureOracle

# 检查依赖
echo "检查Python依赖..."
python3 -c "import flask, flask_cors, aiohttp, web3" 2>/dev/null || {
    echo "缺少依赖，正在安装..."
    pip3 install flask flask-cors aiohttp web3 requests
}

# 创建日志目录
mkdir -p logs

# 显示配置
echo "=========================================="
echo "VC发行Oracle服务启动 (HTTP模式)"
echo "=========================================="
echo "配置文件: vc_issuance_config.json"
echo "Issuer endpoint: http://localhost:8000"
echo "Holder endpoint: http://localhost:8001"
echo "日志目录: ./logs"
echo "=========================================="

# 启动服务
python3 vc_issuance_oracle.py
