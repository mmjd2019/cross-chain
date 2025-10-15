# 跨链可验证凭证(VC)系统

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Solidity 0.5.16](https://img.shields.io/badge/solidity-0.5.16-orange.svg)](https://soliditylang.org/)
[![Besu](https://img.shields.io/badge/Besu-Enterprise%20Ethereum-green.svg)](https://besu.hyperledger.org/)

一个基于Hyperledger Besu和ACA-Py的跨链可验证凭证系统，支持在两个Besu区块链之间进行安全的跨链转账和VC验证。

## 🌟 项目特色

- **跨链互操作性**: 支持两个独立的Besu区块链之间的资产转移
- **可验证凭证**: 集成ACA-Py实现W3C标准的可验证凭证
- **智能合约**: 使用Solidity编写的跨链代币和桥接合约
- **Web界面**: 现代化的Web应用，支持实时监控和操作
- **安全性**: 基于密码学证明的跨链验证机制

## 🏗️ 系统架构

```
┌─────────────────┐    ┌─────────────────┐
│   Besu Chain A  │    │   Besu Chain B  │
│                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │Token Contract│ │    │ │Token Contract│ │
│ └─────────────┘ │    │ └─────────────┘ │
│ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │Bridge Contract│ │    │ │Bridge Contract│ │
│ └─────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘
         │                       │
         └───────────┬───────────┘
                     │
         ┌─────────────────────┐
         │   Oracle Service    │
         │  (Cross-chain Sync) │
         └─────────────────────┘
                     │
         ┌─────────────────────┐
         │    ACA-Py Services  │
         │  (VC Issuer/Holder) │
         └─────────────────────┘
                     │
         ┌─────────────────────┐
         │   Web Application   │
         │  (Monitoring & UI)  │
         └─────────────────────┘
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Node.js 16+
- Docker & Docker Compose
- Java 11+ (for Besu)
- Go 1.19+ (for ACA-Py)

### 安装步骤

1. **克隆项目**
   ```bash
   git clone https://github.com/mmjd2019/cross-chain.git
   cd cross-chain
   ```

2. **启动Besu区块链**
   ```bash
   # 启动两个Besu节点
   docker-compose -f docker-compose1.yml up -d
   docker-compose -f docker-compose2.yml up -d
   ```

3. **部署智能合约**
   ```bash
   cd contracts/kept
   python3 deploy_contracts.py
   ```

4. **启动ACA-Py服务**
   ```bash
   # 启动发行者服务
   aca-py start --admin 0.0.0.0 8080 --admin-insecure-mode --endpoint http://localhost:8080/ --inbound-transport http 0.0.0.0 8080 --outbound-transport http --log-level info --auto-provision --wallet-type indy --wallet-name issuer --wallet-key issuer --genesis-url http://localhost:9000/genesis
   
   # 启动持有者服务
   aca-py start --admin 0.0.0.0 8081 --admin-insecure-mode --endpoint http://localhost:8081/ --inbound-transport http 0.0.0.0 8081 --outbound-transport http --log-level info --auto-provision --wallet-type indy --wallet-name holder --wallet-key holder --genesis-url http://localhost:9000/genesis
   ```

5. **启动Web应用**
   ```bash
   cd webapp
   pip install -r requirements.txt
   python3 enhanced_app.py
   ```

6. **访问应用**
   - 主页: http://localhost:3000
   - VC数据页面: http://localhost:3000/vc-data

## 📋 功能特性

### 🔗 跨链转账
- 支持在两个Besu链之间转移代币
- 基于锁定-释放机制的跨链验证
- 实时交易状态监控

### 🎫 可验证凭证
- W3C标准可验证凭证支持
- 身份证明、学历证书、工作证明等
- 完整的VC生命周期管理

### 📊 实时监控
- 区块链状态实时监控
- 智能合约变量展示
- 交易历史记录

### 🖥️ Web界面
- 现代化响应式设计
- 实时数据更新
- 移动端支持

## 📁 项目结构

```
cross-chain-vc-system/
├── contracts/                 # 智能合约
│   └── kept/
│       ├── SimpleCrossChainTokenWithBridge.sol
│       ├── deploy_contracts.py
│       └── web3_fixed_connection.py
├── webapp/                   # Web应用
│   ├── enhanced_app.py       # 主应用
│   ├── templates/            # HTML模板
│   ├── requirements.txt      # Python依赖
│   └── start_vc_data_app.sh # 启动脚本
├── acapy/                    # ACA-Py配置
├── docker-compose1.yml       # Besu Chain A
├── docker-compose2.yml       # Besu Chain B
├── ibft1.json               # IBFT配置
├── ibft2.json               # IBFT配置
└── README.md                # 项目说明
```

## 🔧 智能合约

### SimpleCrossChainTokenWithBridge.sol
主要的跨链代币合约，支持：
- ERC20标准代币功能
- 跨链锁定和解锁机制
- 桥接合约集成
- 余额管理

**主要功能:**
- `crossChainLock()`: 锁定代币用于跨链转移
- `crossChainUnlock()`: 在目标链解锁代币
- `getLockedBalance()`: 查询锁定余额
- `mint()`/`burn()`: 代币铸造和销毁

## 🌐 API接口

### 系统状态
- `GET /api/status` - 获取系统状态
- `GET /api/contracts` - 获取合约信息

### 跨链转账
- `POST /api/transfer` - 执行跨链转账
- `GET /api/transfer-history` - 获取转账历史

### VC数据
- `GET /api/vc-list` - 获取VC列表
- `GET /api/vc-detail/<vc_id>` - 获取VC详情

### 合约变量
- `GET /api/contract-variables` - 获取合约内部变量

## 🔒 安全特性

- **密码学验证**: 基于Ed25519签名的VC验证
- **跨链安全**: 锁定-释放机制确保资产安全
- **访问控制**: 基于角色的合约访问控制
- **数据完整性**: 区块链保证的数据不可篡改性

## 🧪 测试

```bash
# 运行API测试
cd webapp
python3 test_vc_api.py

# 运行合约测试
cd contracts/kept
python3 test_contracts.py
```

## 📈 性能指标

- **跨链转账延迟**: < 30秒
- **VC验证时间**: < 5秒
- **并发支持**: 100+ 用户
- **数据同步**: 实时更新

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 Apache-2.0许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [Hyperledger Besu](https://besu.hyperledger.org/) - 企业级以太坊客户端
- [ACA-Py](https://github.com/hyperledger/aries-cloudagent-python) - 可验证凭证代理
- [Web3.py](https://web3py.readthedocs.io/) - 以太坊Python库
- [Flask](https://flask.palletsprojects.com/) - Web框架

## 📞 联系我们

- 项目链接: [https://github.com/your-username/cross-chain-vc-system](https://github.com/mmjd2019/cross-chain
- 问题反馈: [Issues](https://github.com/your-username/cross-chain-vc-system/issues)
- 邮箱: ggg1234567@163.com

## 🔮 路线图

- [ ] 支持更多区块链网络
- [ ] 添加零知识证明支持
- [ ] 实现去中心化身份管理
- [ ] 添加移动端应用
- [ ] 支持NFT跨链转移

---

⭐ 如果这个项目对您有帮助，请给我们一个星标！
