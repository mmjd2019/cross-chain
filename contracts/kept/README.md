# 智能合约开发指南

## 📋 概述

这个目录包含了基于DID的外部签名服务的智能合约开发环境，包括：

- **DIDVerifier.sol** - DID身份验证合约
- **AssetManager.sol** - 资产管理合约
- 完整的编译、部署和测试工具

## 🚀 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
python setup_environment.py
```

### 2. 编译合约

```bash
python compile_contracts.py
```

### 3. 部署合约

```bash
python deploy_contracts.py
```

### 4. 测试合约

```bash
python test_contracts.py
```

## 📁 文件结构

```
contracts/
├── DIDVerifier.sol          # DID验证合约
├── AssetManager.sol         # 资产管理合约
├── config.py               # 配置文件
├── compile_contracts.py    # 编译脚本
├── deploy_contracts.py     # 部署脚本
├── test_contracts.py       # 测试脚本
├── setup_environment.py    # 环境设置工具
├── requirements.txt        # Python依赖
├── env_example.txt         # 环境变量示例
├── build/                  # 编译输出目录
│   ├── *.json             # 编译结果
│   └── deployment.json    # 部署结果
└── abi/                   # ABI文件目录
    ├── DIDVerifier.abi    # DID验证合约ABI
    └── AssetManager.abi   # 资产管理合约ABI
```

## ⚙️ 配置说明

### 必需的环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `BESU_RPC_URL` | Besu节点RPC地址 | `http://192.168.1.224:8545` |
| `CHAIN_ID` | 网络链ID | `2023` |
| `DEPLOYER_PRIVATE_KEY` | 部署账户私钥 | `0x...` |

### 可选的环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `GAS_LIMIT` | Gas限制 | `2000000` |
| `GAS_PRICE` | Gas价格 | `0` (免费) |
| `DEBUG` | 调试模式 | `False` |

## 🔧 合约功能

### DIDVerifier合约

- **功能**: 管理用户身份验证状态
- **主要方法**:
  - `verifyIdentity(address, did)` - 验证用户身份
  - `revokeVerification(address)` - 撤销身份验证
  - `isVerified(address)` - 查询验证状态
  - `setOracle(address)` - 设置Oracle地址

### AssetManager合约

- **功能**: 管理用户资产，需要身份验证
- **主要方法**:
  - `deposit()` - 存款（需要身份验证）
  - `withdraw(amount)` - 提取（需要身份验证）
  - `transfer(to, amount)` - 转账（双方都需要身份验证）
  - `balances(address)` - 查询余额

## 🧪 测试说明

测试脚本会执行以下测试：

1. **DIDVerifier测试**:
   - 设置Oracle
   - 验证用户身份
   - 检查验证状态

2. **AssetManager测试**:
   - 存款操作
   - 提取操作
   - 余额查询

## 📝 部署流程

1. **编译合约** - 生成字节码和ABI
2. **部署DIDVerifier** - 先部署验证合约
3. **部署AssetManager** - 使用DIDVerifier地址作为构造函数参数
4. **验证部署** - 检查合约代码是否正确部署

## 🔍 故障排除

### 常见问题

1. **网络连接失败**
   - 检查Besu节点是否运行
   - 验证RPC地址是否正确

2. **私钥错误**
   - 确保私钥格式正确（64位十六进制）
   - 检查私钥是否有0x前缀

3. **Gas不足**
   - 检查账户余额
   - 调整Gas限制

4. **合约部署失败**
   - 检查网络状态
   - 验证构造函数参数

### 调试技巧

- 启用DEBUG模式查看详细日志
- 检查交易收据确认部署状态
- 使用区块浏览器验证合约地址

## 📚 相关文档

- [Solidity文档](https://docs.soliditylang.org/)
- [Web3.py文档](https://web3py.readthedocs.io/)
- [Besu文档](https://besu.hyperledger.org/)

