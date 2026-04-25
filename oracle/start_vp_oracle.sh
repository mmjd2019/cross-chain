#!/bin/bash
# VP验证Oracle服务启动脚本

cd /home/manifold/cursor/cross-chain-new/oracle

# 设置环境变量
export FLASK_APP=flask_app.py
export FLASK_ENV=production
export PYTHONPATH=/home/manifold/cursor/cross-chain-new/oracle

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
echo "VP验证Oracle服务启动"
echo "=========================================="
echo "配置文件: vp_oracle_config.json"
echo "日志目录: ./logs"
echo "=========================================="

# 启动服务
python3 flask_app.py
