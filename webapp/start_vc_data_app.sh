#!/bin/bash

# VC数据展示应用启动脚本

echo "启动VC数据展示应用..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3"
    exit 1
fi

# 检查依赖
echo "检查依赖..."
python3 -c "import flask, flask_socketio" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "安装依赖..."
    pip3 install -r requirements.txt
fi

# 启动应用
echo "启动应用..."
echo "访问地址: http://localhost:3000"
echo "VC数据页面: http://localhost:3000/vc-data"
echo "按 Ctrl+C 停止应用"

python3 enhanced_app.py
