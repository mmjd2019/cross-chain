# 基于DID的跨链交易系统

## 概述

本系统实现了基于DID（去中心化身份）的跨链交易管理，支持多个Besu业务网络间的安全资产转移。系统使用可验证凭证（VC）作为跨链证明，确保交易的安全性和可审计性。

## 系统架构

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Besu链A   │    │   Besu链B   │    │   Besu链C   │
│             │    │             │    │             │
│ 跨链桥合约  │    │ 跨链桥合约  │    │ 跨链桥合约  │
│ DID验证器   │    │ DID验证器   │    │ DID验证器   │
│ 资产管理器  │    │ 资产管理器  │    │ 资产管理器  │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │     跨链协调Oracle服务        │
          │  ┌─────────────────────────┐  │
          │  │     VC颁发服务          │  │
          │  └─────────────────────────┘  │
          └───────────────┬───────────────┘
                          │
          ┌───────────────┴───────────────┐
          │       共享身份层              │
          │   VON Network (Indy链)        │
          │   ACA-Py代理集群              │
          └───────────────────────────────┘
```

## 核心组件

### 1. CrossChainDIDVerifier.sol
增强版DID验证器，支持跨链功能：
- 基础身份验证
- 跨链证明记录和验证
- 多链支持管理
- 防重放攻击保护

### 2. CrossChainBridge.sol
跨链桥合约，处理资产锁定和解锁：
- 资产锁定（源链）
- 资产解锁（目标链）
- 代币支持管理
- 跨链统计

### 3. CrossChainToken.sol
支持跨链的ERC20代币：
- 标准ERC20功能
- 跨链锁定/解锁
- 铸造权限管理
- DID身份验证

### 4. AssetManager.sol
增强版资产管理器：
- 原生ETH管理
- ERC20代币管理
- 跨链转移功能
- 用户余额查询

## 快速开始

### 1. 环境准备

确保已安装以下工具：
- Python 3.8+
- solc (Solidity编译器)
- 两个运行的Besu链

### 2. 编译合约

```bash
cd contracts/kept
python3 compile_crosschain_contracts.py
```

### 3. 配置系统

编辑 `cross_chain_config.json` 文件，配置：
- 链连接信息
- 代币参数
- Oracle服务配置

### 4. 部署系统

```bash
python3 deploy_crosschain_system.py
```

### 5. 测试系统

```bash
python3 test_crosschain_system.py
```

## 使用流程

### 跨链资产转移流程

1. **用户身份验证**
   - 用户在源链上通过DID验证身份
   - 获得身份验证凭证

2. **发起跨链转移**
   - 用户调用AssetManager的`initiateCrossChainTransfer`函数
   - 系统锁定用户的代币资产

3. **生成跨链证明**
   - 桥合约发出AssetLocked事件
   - Oracle服务监听到事件，生成跨链VC

4. **在目标链上解锁**
   - 用户切换到目标链
   - 调用AssetManager的`completeCrossChainTransfer`函数
   - 系统验证跨链证明并解锁资产

### 代码示例

#### 发起跨链转移
```solidity
// 在源链上
AssetManager assetManager = AssetManager(assetManagerAddress);
assetManager.initiateCrossChainTransfer(
    tokenAddress,    // 代币地址
    100 * 10**18,   // 转移数量
    "chain_b"       // 目标链ID
);
```

#### 完成跨链转移
```solidity
// 在目标链上
AssetManager assetManager = AssetManager(assetManagerAddress);
assetManager.completeCrossChainTransfer(
    userDID,        // 用户DID
    tokenAddress,   // 代币地址
    100 * 10**18,   // 转移数量
    "chain_a",      // 源链ID
    sourceTxHash    // 源链交易哈希
);
```

## 配置说明

### 链配置
```json
{
  "name": "Besu Chain A",
  "rpc_url": "http://localhost:8545",
  "chain_id": "chain_a",
  "chain_type": 2,  // 0=source, 1=destination, 2=both
  "private_key": "0x...",
  "gas_price": 1000000000,
  "gas_limit": 3000000
}
```

### 代币配置
```json
{
  "name": "CrossChain Token A",
  "symbol": "CCTA",
  "decimals": 18,
  "initial_supply": 1000000
}
```

## 安全特性

1. **身份验证**
   - 所有操作都需要DID身份验证
   - 防止未授权访问

2. **防重放攻击**
   - 使用交易哈希作为唯一标识
   - 防止重复使用跨链证明

3. **时间限制**
   - 跨链证明设置有效期
   - 防止过期证明被滥用

4. **权限控制**
   - 严格的权限管理
   - 只有授权地址可以执行关键操作

## 监控和调试

### 查看部署结果
```bash
cat cross_chain_deployment.json
```

### 查看合约状态
```python
# 查询用户余额
balance = assetManager.getTokenBalance(userAddress, tokenAddress)

# 查询验证状态
isVerified = assetManager.isUserVerified(userAddress)

# 查询跨链证明
proof = verifier.getCrossChainProof(userDID)
```

## 故障排除

### 常见问题

1. **编译失败**
   - 检查solc版本兼容性
   - 确保所有依赖合约存在

2. **部署失败**
   - 检查链连接状态
   - 验证账户余额和权限

3. **跨链转移失败**
   - 确认用户身份已验证
   - 检查代币授权状态
   - 验证Oracle服务运行状态

### 调试命令

```bash
# 检查链连接
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  http://localhost:8545

# 查看合约事件
# 使用Web3.py或ethers.js监听事件
```

## 扩展功能

### 添加新链
1. 在配置文件中添加新链信息
2. 重新运行部署脚本
3. 更新Oracle服务配置

### 添加新代币
1. 部署新的代币合约
2. 在桥合约中添加代币支持
3. 在资产管理器中注册代币

### 自定义验证规则
1. 修改DIDVerifier合约
2. 添加自定义验证逻辑
3. 重新部署和测试

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 创建Pull Request

## 许可证

MIT License

## 联系方式

如有问题或建议，请通过以下方式联系：
- 创建Issue
- 发送邮件
- 加入讨论群

---

**注意**: 本系统目前处于开发阶段，请在生产环境使用前进行充分测试。
