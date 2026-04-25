#!/bin/bash
# 停止所有ACA-Py容器

echo "停止 ACA-Py 容器..."

# 停止 Issuer ACA-Py
if docker ps --filter "name=issuer-acapy" --format "{{.Names}}" | grep -q "issuer-acapy"; then
    echo "停止 issuer-acapy..."
    docker stop issuer-acapy
    echo "✅ issuer-acapy 已停止"
else
    echo "⚠️  issuer-acapy 未运行"
fi

# 停止 Holder ACA-Py
if docker ps --filter "name=holder-acapy" --format "{{.Names}}" | grep -q "holder-acapy"; then
    echo "停止 holder-acapy..."
    docker stop holder-acapy
    echo "✅ holder-acapy 已停止"
else
    echo "⚠️  holder-acapy 未运行"
fi

# 停止 Verifier ACA-Py (如果需要)
if docker ps --filter "name=verifier-acapy" --format "{{.Names}}" | grep -q "verifier-acapy"; then
    echo "停止 verifier-acapy..."
    docker stop verifier-acapy
    echo "✅ verifier-acapy 已停止"
else
    echo "⚠️  verifier-acapy 未运行"
fi

echo ""
echo "=== 当前ACA-Py容器状态 ==="
docker ps -a --filter "name=acapy" --format "table {{.Names}}\t{{.Status}}"
