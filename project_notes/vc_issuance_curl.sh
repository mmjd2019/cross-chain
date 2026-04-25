#!/bin/bash
# =============================================================================
# VC Issuance Curl Script - 手工 VC 发行脚本
# =============================================================================
# 使用 ACA-Py HTTP API 通过 curl 命令发行可验证凭证 (VC)
#
# 依赖: curl, jq
# 用法: ./vc_issuance_curl.sh [issuer_id] [exporter_name] [product_name]
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# 配置参数
# -----------------------------------------------------------------------------
ISSUER_ADMIN_URL="http://localhost:8080"   # Issuer ACA-Py 管理端点
HOLDER_ADMIN_URL="http://localhost:8081"   # Holder ACA-Py 管理端点

# 连接 ID (必须是 active 状态的连接)
CONNECTION_ID="d3c2f557-0a1f-40f2-b707-57dabf91f401"

# Credential Definition ID
CRED_DEF_ID="DPvobytTtKvmyeRTJZYjsg:3:CL:762:InspectionReport_V8"

# VC 属性 (可通过命令行参数覆盖)
TIMESTAMP=$(date +%s)
EXPORTER_NAME="${1:-Curl 测试出口商}"
CONTRACT_NAME="${2:-TEST-$TIMESTAMP}"
PRODUCT_NAME="${3:-测试产品}"
PRODUCT_QUANTITY="100"
PRODUCT_BATCH="TEST-BATCH-001"
INSPECTION_PASSED="true"
DATE=$(date +%Y-%m-%d)

# -----------------------------------------------------------------------------
# 颜色输出
# -----------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# -----------------------------------------------------------------------------
# 检查依赖
# -----------------------------------------------------------------------------
check_dependencies() {
    if ! command -v curl &> /dev/null; then
        log_error "curl 未安装，请先安装 curl"
        exit 1
    fi

    if ! command -v jq &> /dev/null; then
        log_error "jq 未安装，请先安装 jq"
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# 检查 ACA-Py 服务状态
# -----------------------------------------------------------------------------
check_acapy_status() {
    log_info "检查 ACA-Py 服务状态..."

    if ! curl -s "$ISSUER_ADMIN_URL/connections" > /dev/null 2>&1; then
        log_error "无法连接到 Issuer ACA-Py 服务 ($ISSUER_ADMIN_URL)"
        exit 1
    fi

    if ! curl -s "$HOLDER_ADMIN_URL/connections" > /dev/null 2>&1; then
        log_error "无法连接到 Holder ACA-Py 服务 ($HOLDER_ADMIN_URL)"
        exit 1
    fi

    log_success "ACA-Py 服务运行正常"
}

# -----------------------------------------------------------------------------
# 检查连接状态
# -----------------------------------------------------------------------------
check_connection() {
    log_info "检查连接状态: $CONNECTION_ID"

    CONN_STATE=$(curl -s "$ISSUER_ADMIN_URL/connections/$CONNECTION_ID" | jq -r '.state')

    if [ "$CONN_STATE" != "active" ]; then
        log_error "连接状态不是 active (当前状态: $CONN_STATE)"
        log_info "可用的 active 连接:"
        curl -s "$ISSUER_ADMIN_URL/connections" | jq -r '.[] | select(.state == "active") | "  - \(.connection_id) (\(.alias // "no-alias"))"'
        exit 1
    fi

    log_success "连接状态正常 (active)"
}

# -----------------------------------------------------------------------------
# 发送 VC Offer
# -----------------------------------------------------------------------------
send_vc_offer() {
    log_info "发送 VC Offer..."

    OFFER_RESPONSE=$(curl -s -X POST "$ISSUER_ADMIN_URL/issue-credential-2.0/send-offer" \
        -H "Content-Type: application/json" \
        -d "{
            \"connection_id\": \"$CONNECTION_ID\",
            \"comment\": \"Curl VC 发行脚本 - $TIMESTAMP\",
            \"credential_preview\": {
                \"@type\": \"issue-credential/2.0/credential-preview\",
                \"attributes\": [
                    {\"name\": \"exporter\", \"value\": \"$EXPORTER_NAME\"},
                    {\"name\": \"contractName\", \"value\": \"$CONTRACT_NAME\"},
                    {\"name\": \"productName\", \"value\": \"$PRODUCT_NAME\"},
                    {\"name\": \"productQuantity\", \"value\": \"$PRODUCT_QUANTITY\"},
                    {\"name\": \"productBatch\", \"value\": \"$PRODUCT_BATCH\"},
                    {\"name\": \"inspectionPassed\", \"value\": \"$INSPECTION_PASSED\"},
                    {\"name\": \"Date\", \"value\": \"$DATE\"}
                ]
            },
            \"filter\": {
                \"indy\": {
                    \"cred_def_id\": \"$CRED_DEF_ID\"
                }
            }
        }")

    ISSUER_CRED_EX_ID=$(echo "$OFFER_RESPONSE" | jq -r '.cred_ex_id')
    THREAD_ID=$(echo "$OFFER_RESPONSE" | jq -r '.thread_id')
    OFFER_STATE=$(echo "$OFFER_RESPONSE" | jq -r '.state')

    if [ "$OFFER_STATE" == "offer-sent" ]; then
        log_success "VC Offer 发送成功"
        log_info "  Issuer cred_ex_id: $ISSUER_CRED_EX_ID"
        log_info "  Thread ID: $THREAD_ID"
    else
        log_error "VC Offer 发送失败 (状态: $OFFER_STATE)"
        log_error "响应: $OFFER_RESPONSE"
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# 等待 Holder 响应
# -----------------------------------------------------------------------------
wait_holder_response() {
    log_info "等待 Holder 响应 (最多等待 30 秒)..."

    for i in {1..6}; do
        sleep 5

        HOLDER_STATE=$(curl -s "$HOLDER_ADMIN_URL/issue-credential-2.0/records" | \
            jq -r ".results[] | select(.cred_ex_record.thread_id == \"$THREAD_ID\") | .cred_ex_record.state")

        if [ "$HOLDER_STATE" == "credential-received" ]; then
            log_success "Holder 已响应 (状态: credential-received)"
            return 0
        elif [ "$HOLDER_STATE" == "abandoned" ]; then
            log_error "凭证交换被废弃"
            return 1
        fi

        log_info "  等待中... ($i/6) 当前状态: ${HOLDER_STATE:-unknown}"
    done

    log_error "Holder 响应超时"
    return 1
}

# -----------------------------------------------------------------------------
# 获取 Holder 端 cred_ex_id
# -----------------------------------------------------------------------------
get_holder_cred_ex_id() {
    HOLDER_CRED_EX_ID=$(curl -s "$HOLDER_ADMIN_URL/issue-credential-2.0/records" | \
        jq -r ".results[] | select(.cred_ex_record.thread_id == \"$THREAD_ID\") | .cred_ex_record.cred_ex_id")

    if [ -n "$HOLDER_CRED_EX_ID" ] && [ "$HOLDER_CRED_EX_ID" != "null" ]; then
        log_info "Holder cred_ex_id: $HOLDER_CRED_EX_ID"
        return 0
    else
        log_error "无法获取 Holder cred_ex_id"
        return 1
    fi
}

# -----------------------------------------------------------------------------
# 调用 Holder 端 store 端点
# -----------------------------------------------------------------------------
store_credential() {
    log_info "调用 Holder 端 store 端点..."

    STORE_RESPONSE=$(curl -s -X POST "$HOLDER_ADMIN_URL/issue-credential-2.0/records/$HOLDER_CRED_EX_ID/store" \
        -H "Content-Type: application/json" \
        -d '{}')

    STORE_STATE=$(echo "$STORE_RESPONSE" | jq -r '.cred_ex_record.state')

    if [ "$STORE_STATE" == "done" ]; then
        log_success "凭证存储成功 (状态: done)"
    else
        log_warning "凭证存储状态异常: $STORE_STATE"
    fi
}

# -----------------------------------------------------------------------------
# 验证 VC 存储
# -----------------------------------------------------------------------------
verify_vc_storage() {
    log_info "验证 VC 存储..."
    sleep 2  # 等待存储完成

    VC_FOUND=$(curl -s "$HOLDER_ADMIN_URL/credentials" | \
        jq -r ".results[] | select(.attrs.contractName == \"$CONTRACT_NAME\") | .attrs.contractName")

    if [ "$VC_FOUND" == "$CONTRACT_NAME" ]; then
        log_success "VC 已成功存储到 Holder 钱包"

        # 显示 VC 详情
        echo ""
        log_info "VC 详情:"
        curl -s "$HOLDER_ADMIN_URL/credentials" | \
            jq ".results[] | select(.attrs.contractName == \"$CONTRACT_NAME\") | .attrs"

        return 0
    else
        log_error "VC 未找到 (contractName: $CONTRACT_NAME)"
        return 1
    fi
}

# -----------------------------------------------------------------------------
# 显示当前 VC 数量
# -----------------------------------------------------------------------------
show_vc_count() {
    VC_COUNT=$(curl -s "$HOLDER_ADMIN_URL/credentials" | jq '.results | length')
    log_info "Holder 端 VC 总数: $VC_COUNT"
}

# -----------------------------------------------------------------------------
# 主流程
# -----------------------------------------------------------------------------
main() {
    echo ""
    echo "======================================================================"
    echo "         VC Issuance Curl Script - 手工 VC 发行脚本"
    echo "======================================================================"
    echo ""
    log_info "VC 属性:"
    echo "  - Exporter:       $EXPORTER_NAME"
    echo "  - Contract Name:  $CONTRACT_NAME"
    echo "  - Product Name:   $PRODUCT_NAME"
    echo "  - Product Batch:  $PRODUCT_BATCH"
    echo "  - Date:           $DATE"
    echo ""

    check_dependencies
    check_acapy_status
    check_connection
    show_vc_count

    echo ""
    log_info "=== 开始 VC 发行流程 ==="

    send_vc_offer
    wait_holder_response || exit 1
    get_holder_cred_ex_id || exit 1
    store_credential
    verify_vc_storage || exit 1

    echo ""
    show_vc_count

    echo ""
    log_success "=== VC 发行流程完成 ==="
    echo ""
}

# 显示使用帮助
show_help() {
    echo "用法: $0 [exporter_name] [contract_name] [product_name]"
    echo ""
    echo "参数:"
    echo "  exporter_name   - 出口商名称 (默认：Curl 测试出口商)"
    echo "  contract_name   - 合同名称 (默认：TEST-<timestamp>)"
    echo "  product_name    - 产品名称 (默认：测试产品)"
    echo ""
    echo "示例:"
    echo "  $0                                    # 使用默认参数"
    echo "  $0 \"我的公司\"                         # 自定义出口商"
    echo "  $0 \"我的公司\" \"CONTRACT-001\"           # 自定义出口商和合同"
    echo "  $0 \"我的公司\" \"CONTRACT-001\" \"产品 A\"   # 全部自定义"
    echo ""
}

# 处理命令行参数
if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    show_help
    exit 0
fi

# 运行主流程
main "$@"
