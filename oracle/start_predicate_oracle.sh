#!/bin/bash
# VP谓词验证Oracle服务启动脚本
# 端口: 7003
# 功能: 提供基于零知识证明谓词的VC验证服务

set -e

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  VP谓词验证Oracle服务启动脚本${NC}"
echo -e "${BLUE}  端口: 7003${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3${NC}"
    exit 1
fi

# 检查配置文件
CONFIG_FILE="vp_predicate_config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}错误: 配置文件 $CONFIG_FILE 不存在${NC}"
    exit 1
fi
echo -e "${GREEN}配置文件: $CONFIG_FILE${NC}"

# 检查必要的Python文件
REQUIRED_FILES=(
    "predicate_flask_app.py"
    "vp_predicate_oracle_service.py"
    "predicate_proof_builder.py"
    "acapy_client.py"
    "connection_manager.py"
    "blockchain_client.py"
    "web3_fixed_connection.py"
)

echo -e "${YELLOW}检查依赖文件...${NC}"
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}错误: 缺少文件 $file${NC}"
        exit 1
    fi
    echo -e "  ${GREEN}✓${NC} $file"
done

# 检查Python依赖
echo ""
echo -e "${YELLOW}检查Python依赖...${NC}"
python3 -c "import flask" 2>/dev/null || {
    echo -e "${RED}错误: 缺少 flask 模块${NC}"
    echo "请运行: pip install flask flask-cors"
    exit 1
}
python3 -c "import aiohttp" 2>/dev/null || {
    echo -e "${RED}错误: 缺少 aiohttp 模块${NC}"
    echo "请运行: pip install aiohttp"
    exit 1
}
python3 -c "import web3" 2>/dev/null || {
    echo -e "${RED}错误: 缺少 web3 模块${NC}"
    echo "请运行: pip install web3"
    exit 1
}
echo -e "  ${GREEN}✓${NC} flask"
echo -e "  ${GREEN}✓${NC} aiohttp"
echo -e "  ${GREEN}✓${NC} web3"

# 解析参数
HOST="0.0.0.0"
PORT=7003
DEBUG=""
CONFIG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --debug)
            DEBUG="--debug"
            shift
            ;;
        --config)
            CONFIG="$2"
            shift 2
            ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --host HOST     服务器地址 (默认: 0.0.0.0)"
            echo "  --port PORT     服务器端口 (默认: 7003)"
            echo "  --config FILE   配置文件路径 (默认: vp_predicate_config.json)"
            echo "  --debug         启用调试模式"
            echo "  -h, --help      显示帮助信息"
            exit 0
            ;;
        *)
            echo -e "${RED}未知选项: $1${NC}"
            exit 1
            ;;
    esac
done

# 构建配置参数
if [ -z "$CONFIG" ]; then
    CONFIG="--config $CONFIG_FILE"
else
    CONFIG="--config $CONFIG"
fi

echo ""
echo -e "${BLUE}============================================================${NC}"
echo -e "${GREEN}启动VP谓词验证Oracle服务...${NC}"
echo -e "${BLUE}============================================================${NC}"
echo -e "  地址: ${YELLOW}http://${HOST}:${PORT}${NC}"
echo -e "  配置: ${YELLOW}${CONFIG}${NC}"
echo ""

# 启动服务
python3 predicate_flask_app.py $CONFIG --host "$HOST" --port "$PORT" $DEBUG
