#!/bin/bash
# 启动所有3个ACA-Py容器 (HTTP模式)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=============================================="
echo "启动所有 ACA-Py 容器 (HTTP模式)"
echo "=============================================="

# 检查是否已有运行的容器
RUNNING=$(docker ps --filter "name=acapy" --format "{{.Names}}" | wc -l)
if [ "$RUNNING" -gt 0 ]; then
    echo "⚠️  检测到已有运行的ACA-Py容器:"
    docker ps --filter "name=acapy" --format "  - {{.Names}}: {{.Status}}"
    echo ""
    read -p "是否先停止现有容器? (y/n): " CONFIRM
    if [ "$CONFIRM" = "y" ] || [ "$CONFIRM" = "Y" ]; then
        echo "停止现有容器..."
        "$SCRIPT_DIR/stop_acapy.sh"
        sleep 2
    else
        echo "取消启动"
        exit 1
    fi
fi

echo ""
echo "1️⃣  启动 Issuer ACA-Py (Admin: 8080, Endpoint: 8000)"
echo "----------------------------------------------"
"$SCRIPT_DIR/run1_http.sh"
sleep 3

echo ""
echo "2️⃣  启动 Holder ACA-Py (Admin: 8081, Endpoint: 8001)"
echo "----------------------------------------------"
"$SCRIPT_DIR/run2_http.sh"
sleep 3

echo ""
echo "3️⃣  启动 Verifier ACA-Py (Admin: 8082, Endpoint: 8002)"
echo "----------------------------------------------"
"$SCRIPT_DIR/run3_http.sh"
sleep 5

echo ""
echo "=============================================="
echo "等待服务就绪..."
echo "=============================================="

# 等待服务就绪
for i in {1..30}; do
    ISSUER_OK=$(curl -s http://localhost:8080/status 2>/dev/null | grep -c "label")
    HOLDER_OK=$(curl -s http://localhost:8081/status 2>/dev/null | grep -c "label")
    VERIFIER_OK=$(curl -s http://localhost:8082/status 2>/dev/null | grep -c "label")

    if [ "$ISSUER_OK" -gt 0 ] && [ "$HOLDER_OK" -gt 0 ] && [ "$VERIFIER_OK" -gt 0 ]; then
        echo "✅ 所有服务已就绪!"
        break
    fi

    echo "等待中... ($i/30)"
    sleep 2
done

echo ""
echo "=============================================="
echo "ACA-Py 容器状态"
echo "=============================================="
docker ps --filter "name=acapy" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "=============================================="
echo "服务端点"
echo "=============================================="
echo "Issuer:   Admin=http://localhost:8080  Endpoint=http://192.168.1.27:8000"
echo "Holder:   Admin=http://localhost:8081  Endpoint=http://192.168.1.27:8001"
echo "Verifier: Admin=http://localhost:8082  Endpoint=http://192.168.1.27:8002"
