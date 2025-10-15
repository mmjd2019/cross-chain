# 跨链VC设置使用说明

## 概述

本工具用于建立跨链交易的可验证凭证（VC）系统，包括Schema注册、凭证定义创建和VC生成功能。

## 文件结构

```
contracts/kept/
├── cross_chain_schema_register.py    # 跨链Schema注册脚本
├── cross_chain_vc_generator.py       # 跨链VC生成器
├── setup_cross_chain_vc.py          # 跨链VC完整设置脚本
├── start_cross_chain_vc.sh          # 启动脚本
├── cross_chain_vc_config.json       # 配置文件
└── 跨链VC设置使用说明.md            # 本文件
```

## 前置条件

### 1. 启动VON Network
```bash
docker run -it --rm \
  --name von-network \
  -p 9000:9000 \
  -p 9001:9001 \
  -p 9002:9002 \
  -p 9003:9003 \
  -p 9700-9709:9700-9709 \
  bcgovimages/von-network:1.6.8 \
  bash -c "
    generate_indy_pool_transactions --nodes 4 --clients 5 --nodeNum 1 2 3 4 --ips '192.168.1.3,192.168.1.3,192.168.1.3,192.168.1.3' --network genesis
    /opt/indy/ledger/start_ledger.sh Node1 0.0.0.0 9701 0.0.0.0 9702
  "
```

### 2. 启动发行者ACA-Py
```bash
docker run -it --rm \
  --name aca-py-issuer \
  -p 8000:8000 -p 8080:8080 \
  -v $(pwd)/aca-py-wallet:/home/indy/.indy_client/wallet \
  bcgovimages/aries-cloudagent:py36-1.16-0_0.6.0 \
  start \
  --wallet-type indy \
  --wallet-storage-type default \
  --seed 000000000000000000000000000Agent \
  --wallet-key welldone \
  --wallet-name myWallet \
  --genesis-url http://192.168.1.3/genesis \
  --inbound-transport http 0.0.0.0 8000 \
  --outbound-transport http \
  --endpoint http://192.168.1.3:8000 \
  --admin 0.0.0.0 8080 \
  --admin-insecure-mode \
  --auto-provision
```

### 3. 启动持有者ACA-Py
```bash
docker run -it --rm \
  --name aca-py-holder \
  -p 8001:8000 -p 8081:8080 \
  -v $(pwd)/aca-py-wallet-holder:/home/indy/.indy_client/wallet \
  bcgovimages/aries-cloudagent:py36-1.16-0_0.6.0 \
  start \
  --wallet-type indy \
  --wallet-storage-type default \
  --seed 000000000000000000000000000Holder \
  --wallet-key welldone \
  --wallet-name myWallet \
  --genesis-url http://192.168.1.3/genesis \
  --inbound-transport http 0.0.0.0 8000 \
  --outbound-transport http \
  --endpoint http://192.168.1.3:8001 \
  --admin 0.0.0.0 8080 \
  --admin-insecure-mode \
  --auto-provision
```

## 使用方法

### 方法1：使用启动脚本（推荐）

```bash
cd /home/manifold/cursor/twobesu/contracts/kept
./start_cross_chain_vc.sh
```

### 方法2：直接运行Python脚本

```bash
cd /home/manifold/cursor/twobesu/contracts/kept
python3 setup_cross_chain_vc.py
```

### 方法3：分步执行

#### 1. 注册Schema
```bash
python3 cross_chain_schema_register.py
```

#### 2. 生成VC
```bash
python3 cross_chain_vc_generator.py
```

## 配置说明

### cross_chain_vc_config.json

```json
{
  "acapy_services": {
    "issuer": {
      "admin_url": "http://localhost:8000",
      "endpoint": "http://localhost:8000",
      "port": 8000,
      "admin_port": 8080
    },
    "holder": {
      "admin_url": "http://localhost:8001", 
      "endpoint": "http://localhost:8001",
      "port": 8001,
      "admin_port": 8081
    }
  },
  "genesis": {
    "url": "http://localhost/genesis",
    "network_name": "von-network"
  },
  "schema": {
    "name": "CrossChainLockCredential",
    "version": "1.0",
    "attributes": [
      "sourceChain",
      "targetChain",
      "amount", 
      "tokenAddress",
      "lockId",
      "transactionHash",
      "expiry",
      "userAddress"
    ]
  }
}
```

## 输出结果

成功运行后，将生成以下文件：

- `cross_chain_vc_setup_results.json` - 包含所有生成的ID和配置信息

### 结果文件内容示例

```json
{
  "success": true,
  "issuer_did": "DPvobytTtKvmyeRTJZYjsg",
  "schema_id": "DPvobytTtKvmyeRTJZYjsg:2:CrossChainLockCredential:1.0",
  "cred_def_id": "DPvobytTtKvmyeRTJZYjsg:3:CL:10:cross-chain-lock",
  "connection_id": "12345678-1234-1234-1234-123456789012",
  "test_vc_id": "87654321-4321-4321-4321-210987654321"
}
```

## 跨链VC属性说明

生成的跨链VC包含以下属性：

| 属性名 | 说明 | 示例值 |
|--------|------|--------|
| sourceChain | 源链标识 | "chain_a" |
| targetChain | 目标链标识 | "chain_b" |
| amount | 跨链金额 | "100" |
| tokenAddress | 代币合约地址 | "0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af" |
| lockId | 锁定ID | "lock_123456" |
| transactionHash | 交易哈希 | "0xabcdef1234567890" |
| expiry | 过期时间 | "2024-01-01T12:00:00Z" |
| userAddress | 用户地址 | "0x1234567890123456789012345678901234567890" |

## 集成到Oracle服务

生成的结果可以集成到Oracle服务中：

```python
# 在Oracle服务中使用
from setup_cross_chain_vc import CrossChainVCSetup

# 加载配置
with open('cross_chain_vc_setup_results.json', 'r') as f:
    vc_config = json.load(f)

# 创建VC生成器
vc_generator = CrossChainVCSetup(
    issuer_admin_url="http://localhost:8000",
    holder_admin_url="http://localhost:8001"
)

# 生成跨链VC
cross_chain_data = {
    "source_chain": "chain_a",
    "target_chain": "chain_b",
    "amount": "100",
    "token_address": "0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af",
    "lock_id": "lock_123456",
    "transaction_hash": "0xabcdef1234567890",
    "expiry": "2024-01-01T12:00:00Z",
    "user_address": "0x1234567890123456789012345678901234567890"
}

result = vc_generator.generate_cross_chain_vc(
    vc_config["cred_def_id"],
    cross_chain_data
)
```

## 故障排除

### 常见问题

1. **连接失败**
   - 检查ACA-Py服务是否正在运行
   - 检查端口配置是否正确
   - 检查网络连接

2. **Schema注册失败**
   - 检查VON Network是否运行
   - 检查Genesis URL是否正确
   - 检查钱包是否已创建

3. **VC生成失败**
   - 检查连接是否已建立
   - 检查凭证定义ID是否正确
   - 检查属性数据格式

### 日志查看

```bash
# 查看详细日志
tail -f oracle_v6.log

# 查看特定错误
grep "ERROR" oracle_v6.log
```

## 下一步

1. 将生成的Schema ID和凭证定义ID集成到Oracle服务
2. 实现跨链交易的完整工作流程
3. 添加VC验证和撤销功能
4. 优化性能和错误处理
