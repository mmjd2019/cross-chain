#!/bin/bash
# -*- coding: utf-8 -*-
"""
跨链VC设置启动脚本
一键完成跨链Schema注册、凭证定义创建和VC生成
"""

echo "🔐 跨链VC设置启动脚本"
echo "=============================================="
echo

# 检查Python环境
echo "🔍 检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3未安装"
    exit 1
fi
echo "✅ Python3已安装"

# 检查依赖
echo "🔍 检查依赖..."
python3 -c "import requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ requests模块未安装，正在安装..."
    pip3 install requests
fi
echo "✅ 依赖检查完成"

# 读取配置文件获取IP地址
if [ -f "cross_chain_vc_config.json" ]; then
    SERVER_IP=$(python3 -c "import json; print(json.load(open('cross_chain_vc_config.json'))['server_ip'])" 2>/dev/null)
    if [ -z "$SERVER_IP" ]; then
        SERVER_IP="192.168.230.178"
    fi
else
    SERVER_IP="192.168.230.178"
fi

echo "🔍 使用服务器IP: $SERVER_IP"

# 检查ACA-Py服务
echo "🔍 检查ACA-Py服务..."
echo "  检查发行者服务 (端口8000)..."
curl -s http://$SERVER_IP:8000/status > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ 发行者服务运行正常"
else
    echo "❌ 发行者服务未运行，请先启动ACA-Py"
    echo "   启动命令示例:"
    echo "   docker run -d --network host --name issuer-acapy \\"
    echo "     -e RUST_BACKTRACE=1 -p 8080:8080 -p 8000:8000 \\"
    echo "     -v \$(pwd)/aca-py-wallet-issuer:/home/indy/.indy_client/wallet \\"
    echo "     bcgovimages/aries-cloudagent:py36-1.16-0_0.6.0 \\"
    echo "     start --wallet-type indy --wallet-storage-type default \\"
    echo "     --seed 000000000000000000000000000Agent \\"
    echo "     --wallet-key welldone --wallet-name issuerWallet \\"
    echo "     --genesis-url http://$SERVER_IP/genesis \\"
    echo "     --inbound-transport http 0.0.0.0 8000 \\"
    echo "     --outbound-transport http --endpoint http://$SERVER_IP:8000 \\"
    echo "     --admin 0.0.0.0 8080 --admin-insecure-mode \\"
    echo "     --auto-provision --auto-accept-invites \\"
    echo "     --auto-accept-requests --label Issuer.Agent"
    exit 1
fi

echo "  检查持有者服务 (端口8001)..."
curl -s http://$SERVER_IP:8001/status > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ 持有者服务运行正常"
else
    echo "❌ 持有者服务未运行，请先启动第二个ACA-Py实例"
    echo "   启动命令示例:"
    echo "   docker run -d --network host --name holder-acapy \\"
    echo "     -e RUST_BACKTRACE=1 -p 8081:8081 -p 8001:8001 \\"
    echo "     -v \$(pwd)/aca-py-wallet-holder:/home/indy/.indy_client/wallet \\"
    echo "     bcgovimages/aries-cloudagent:py36-1.16-0_0.6.0 \\"
    echo "     start --wallet-type indy --wallet-storage-type default \\"
    echo "     --seed 000000000000000000000000001Agent \\"
    echo "     --wallet-key welldone --wallet-name holderWallet \\"
    echo "     --genesis-url http://$SERVER_IP/genesis \\"
    echo "     --inbound-transport http 0.0.0.0 8001 \\"
    echo "     --outbound-transport http --endpoint http://$SERVER_IP:8001 \\"
    echo "     --admin 0.0.0.0 8081 --admin-insecure-mode \\"
    echo "     --auto-provision --auto-accept-invites \\"
    echo "     --auto-accept-requests --label Holder.Agent"
    exit 1
fi

echo
echo "🚀 开始跨链VC设置..."
echo "=============================================="

# 运行跨链VC设置
python3 setup_cross_chain_vc.py

# 检查结果
if [ $? -eq 0 ]; then
    echo
    echo "✅ 跨链VC设置完成！"
    echo "=============================================="
    echo "📋 生成的文件:"
    echo "   - cross_chain_vc_setup_results.json (设置结果)"
    echo
    echo "🔧 下一步操作:"
    echo "   1. 查看设置结果文件"
    echo "   2. 使用生成的Schema ID和凭证定义ID"
    echo "   3. 集成到Oracle服务中"
    echo
else
    echo
    echo "❌ 跨链VC设置失败！"
    echo "请检查错误信息并重试"
    exit 1
fi
