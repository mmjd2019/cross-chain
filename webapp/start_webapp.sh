#!/bin/bash
"""
跨链VC系统Web前端启动脚本
"""

echo "🚀 启动跨链VC系统Web前端..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 检查pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 未安装"
    exit 1
fi

# 进入webapp目录
cd /home/manifold/cursor/twobesu/webapp

# 安装依赖
echo "📦 安装Python依赖..."
pip3 install -r requirements.txt

# 检查端口3000是否被占用
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  端口3000已被占用，尝试使用端口3001..."
    # 修改app.py中的端口
    sed -i 's/port=3000/port=3001/g' app.py
    PORT=3001
else
    PORT=3000
fi

# 启动应用
echo "🌐 启动Web应用..."
echo "访问地址: http://localhost:$PORT"
echo "按 Ctrl+C 停止应用"

python3 app.py
