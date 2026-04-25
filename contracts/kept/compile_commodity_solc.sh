#!/bin/bash
# 大宗货物跨境交易智能合约编译脚本
# 使用命令行solc编译器（Solidity 0.5.16）

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build_commodity"

# 合约列表
CONTRACTS=(
    "DIDVerifier.sol"
    "ContractManager.sol"
    "InspectionReportVCManager.sol"
    "InsuranceContractVCManager.sol"
    "CertificateOfOriginVCManager.sol"
    "BillOfLadingVCManager.sol"
    "VCCrossChainBridge.sol"
    "VCVerifier.sol"
)

echo "============================================================"
echo "🔨 大宗货物跨境交易智能合约编译工具"
echo "============================================================"
echo

# 检查solc
echo "🔍 检查Solidity编译器..."
if ! command -v solc &> /dev/null; then
    echo -e "${RED}❌ 未找到solc编译器${NC}"
    echo "请安装: sudo apt install solc"
    exit 1
fi

SOLC_VERSION=$(solc --version | grep "Version:" | awk '{print $2}')
echo -e "${GREEN}✅ 找到solc版本: $SOLC_VERSION${NC}"
echo

# 创建build目录
echo "📁 创建编译输出目录..."
mkdir -p "$BUILD_DIR"
echo -e "${GREEN}✅ 编译输出目录: $BUILD_DIR${NC}"
echo

echo "============================================================"
echo "📋 开始编译合约..."
echo "============================================================"
echo

# 编译统计
SUCCESS_COUNT=0
FAILED_CONTRACTS=()

# 编译每个合约
for CONTRACT_FILE in "${CONTRACTS[@]}"; do
    CONTRACT_PATH="$SCRIPT_DIR/$CONTRACT_FILE"

    # 检查文件是否存在
    if [ ! -f "$CONTRACT_PATH" ]; then
        echo -e "${RED}❌ 合约文件不存在: $CONTRACT_FILE${NC}"
        FAILED_CONTRACTS+=("$CONTRACT_FILE")
        continue
    fi

    echo -e "${YELLOW}🔨 编译 $CONTRACT_FILE...${NC}"

    # 编译合约
    if solc --optimize --optimize-runs 1000 \
            --abi \
            --bin \
            --overwrite \
            --output-dir "$BUILD_DIR" \
            "$CONTRACT_PATH" > /dev/null 2>&1; then
        # 编译成功
        CONTRACT_NAME="${CONTRACT_FILE%.sol}"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))

        # 生成JSON文件
        python3 << EOF
import json
import sys
from datetime import datetime

contract_name = "$CONTRACT_NAME"
build_dir = "$BUILD_DIR"
script_dir = "$SCRIPT_DIR"

# 读取ABI
try:
    with open(f"{build_dir}/{contract_name}.abi", 'r') as f:
        abi = json.load(f)
except:
    print(f"  ⚠️  无法读取ABI文件")
    sys.exit(1)

# 读取字节码
try:
    with open(f"{build_dir}/{contract_name}.bin", 'r') as f:
        bytecode = f.read().strip()
except:
    print(f"  ⚠️  无法读取字节码文件")
    sys.exit(1)

# 生成JSON产物
artifact = {
    "contractName": contract_name,
    "abi": abi,
    "bytecode": f"0x{bytecode}",
    "deployedBytecode": f"0x{bytecode}",
    "compiler": {
        "name": "solc",
        "version": "$SOLC_VERSION"
    },
    "networks": {},
    "schemaVersion": "3.4.7",
    "updatedAt": datetime.now().isoformat()
}

# 保存JSON文件
with open(f"{script_dir}/{contract_name}.json", 'w', encoding='utf-8') as f:
    json.dump(artifact, f, indent=2, ensure_ascii=False)

print(f"  ✅ 生成 {contract_name}.json")
EOF

        echo -e "${GREEN}✅ $CONTRACT_FILE 编译成功${NC}"
        echo
    else
        # 编译失败
        echo -e "${RED}❌ $CONTRACT_FILE 编译失败${NC}"
        FAILED_CONTRACTS+=("$CONTRACT_FILE")
        echo
    fi
done

# 输出统计结果
echo "============================================================"
echo "📊 编译结果统计"
echo "============================================================"
echo "总计: ${#CONTRACTS[@]} 个合约"
echo -e "${GREEN}✅ 成功: $SUCCESS_COUNT 个${NC}"
if [ ${#FAILED_CONTRACTS[@]} -gt 0 ]; then
    echo -e "${RED}❌ 失败: ${#FAILED_CONTRACTS[@]} 个${NC}"
    echo
    echo "失败的合约:"
    for contract in "${FAILED_CONTRACTS[@]}"; do
        echo "  - $contract"
    done
fi
echo

if [ $SUCCESS_COUNT -eq ${#CONTRACTS[@]} ]; then
    echo -e "${GREEN}🎉 所有合约编译成功！${NC}"
    echo "📁 编译产物保存在: $BUILD_DIR"
    echo "📄 JSON产物保存在合约目录"
    exit 0
else
    echo -e "${RED}❌ 部分合约编译失败${NC}"
    exit 1
fi
