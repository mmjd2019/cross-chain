#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨链Oracle服务演示脚本
展示Oracle服务的基本功能
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from web3 import Web3

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DemoOracle:
    """演示版Oracle服务"""
    
    def __init__(self):
        self.chains = {}
        self.contracts = {}
        self.running = False
        self.setup_demo_environment()
    
    def setup_demo_environment(self):
        """设置演示环境"""
        logger.info("🚀 初始化演示Oracle服务...")
        
        # 连接测试链
        try:
            self.chains['chain_a'] = Web3(Web3.HTTPProvider('http://localhost:8545'))
            self.chains['chain_b'] = Web3(Web3.HTTPProvider('http://localhost:8555'))
            
            if self.chains['chain_a'].is_connected():
                logger.info("✅ 链A连接成功")
            else:
                logger.warning("⚠️  链A连接失败")
            
            if self.chains['chain_b'].is_connected():
                logger.info("✅ 链B连接成功")
            else:
                logger.warning("⚠️  链B连接失败")
                
        except Exception as e:
            logger.error(f"❌ 链连接失败: {e}")
    
    def load_contracts(self):
        """加载合约"""
        try:
            # 加载桥合约ABI
            with open('CrossChainBridgeSimple.json', 'r') as f:
                bridge_abi = json.load(f)['abi']
            
            # 加载DID验证器ABI
            with open('CrossChainDIDVerifier.json', 'r') as f:
                verifier_abi = json.load(f)['abi']
            
            # 链A合约
            self.contracts['chain_a'] = {
                'bridge': self.chains['chain_a'].eth.contract(
                    address=Web3.to_checksum_address('0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af'),
                    abi=bridge_abi
                ),
                'verifier': self.chains['chain_a'].eth.contract(
                    address=Web3.to_checksum_address('0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'),
                    abi=verifier_abi
                )
            }
            
            # 链B合约
            self.contracts['chain_b'] = {
                'bridge': self.chains['chain_b'].eth.contract(
                    address=Web3.to_checksum_address('0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af'),
                    abi=bridge_abi
                ),
                'verifier': self.chains['chain_b'].eth.contract(
                    address=Web3.to_checksum_address('0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'),
                    abi=verifier_abi
                )
            }
            
            logger.info("✅ 合约加载成功")
            
        except Exception as e:
            logger.error(f"❌ 合约加载失败: {e}")
    
    def show_chain_status(self):
        """显示链状态"""
        logger.info("📊 链状态信息:")
        logger.info("=" * 50)
        
        for chain_id, w3 in self.chains.items():
            try:
                if w3.is_connected():
                    block_number = w3.eth.block_number
                    chain_id_hex = w3.eth.chain_id
                    logger.info(f"🔗 {chain_id}:")
                    logger.info(f"   - 连接状态: ✅ 正常")
                    logger.info(f"   - 最新区块: {block_number}")
                    logger.info(f"   - 链ID: {chain_id_hex}")
                else:
                    logger.info(f"🔗 {chain_id}: ❌ 连接失败")
            except Exception as e:
                logger.info(f"🔗 {chain_id}: ❌ 错误 - {e}")
    
    def show_contract_info(self):
        """显示合约信息"""
        logger.info("📋 合约信息:")
        logger.info("=" * 50)
        
        for chain_id, contracts in self.contracts.items():
            try:
                # 桥合约信息
                bridge_info = contracts['bridge'].functions.getBridgeInfo().call()
                logger.info(f"🌉 {chain_id} 桥合约:")
                logger.info(f"   - 地址: {contracts['bridge'].address}")
                logger.info(f"   - 链ID: {bridge_info[2]}")
                logger.info(f"   - 链类型: {bridge_info[3]}")
                logger.info(f"   - 锁定次数: {bridge_info[4]}")
                logger.info(f"   - 解锁次数: {bridge_info[5]}")
                
                # DID验证器信息
                logger.info(f"🔐 {chain_id} DID验证器:")
                logger.info(f"   - 地址: {contracts['verifier'].address}")
                
            except Exception as e:
                logger.error(f"❌ 获取 {chain_id} 合约信息失败: {e}")
    
    def simulate_cross_chain_workflow(self):
        """模拟跨链工作流程"""
        logger.info("🎭 模拟跨链工作流程:")
        logger.info("=" * 50)
        
        # 步骤1: 用户在链A上锁定资产
        logger.info("1️⃣ 用户在链A上锁定资产...")
        logger.info("   - 用户地址: 0x1234567890123456789012345678901234567890")
        logger.info("   - 锁定金额: 100 ETH")
        logger.info("   - 目标链: chain_b")
        logger.info("   - 状态: ✅ 模拟完成")
        
        # 步骤2: Oracle检测到锁定事件
        logger.info("2️⃣ Oracle检测到锁定事件...")
        logger.info("   - 事件类型: AssetLocked")
        logger.info("   - 交易哈希: 0xabcdef1234567890...")
        logger.info("   - 状态: ✅ 模拟完成")
        
        # 步骤3: 生成跨链证明
        logger.info("3️⃣ 生成跨链证明...")
        logger.info("   - 源链: chain_a")
        logger.info("   - 目标链: chain_b")
        logger.info("   - 证明ID: proof_123456")
        logger.info("   - 状态: ✅ 模拟完成")
        
        # 步骤4: 颁发可验证凭证
        logger.info("4️⃣ 颁发可验证凭证...")
        logger.info("   - 用户DID: did:indy:testnet:user123")
        logger.info("   - 凭证类型: CrossChainLockCredential")
        logger.info("   - 有效期: 24小时")
        logger.info("   - 状态: ✅ 模拟完成")
        
        # 步骤5: 在目标链上记录证明
        logger.info("5️⃣ 在目标链上记录证明...")
        logger.info("   - 目标链: chain_b")
        logger.info("   - 证明记录: 已记录")
        logger.info("   - 状态: ✅ 模拟完成")
        
        # 步骤6: 用户在链B上解锁资产
        logger.info("6️⃣ 用户在链B上解锁资产...")
        logger.info("   - 用户地址: 0x1234567890123456789012345678901234567890")
        logger.info("   - 解锁金额: 100 ETH")
        logger.info("   - 状态: ✅ 模拟完成")
        
        logger.info("🎉 跨链工作流程模拟完成！")
    
    def show_oracle_capabilities(self):
        """显示Oracle服务能力"""
        logger.info("🔧 Oracle服务能力:")
        logger.info("=" * 50)
        
        capabilities = [
            "✅ 多链事件监控",
            "✅ 跨链证明生成",
            "✅ 可验证凭证颁发",
            "✅ 目标链证明记录",
            "✅ 防重放攻击保护",
            "✅ 自动重连机制",
            "✅ 健康状态监控",
            "✅ 异步事件处理",
            "✅ 错误重试机制",
            "✅ 详细日志记录"
        ]
        
        for capability in capabilities:
            logger.info(f"   {capability}")
    
    def run_demo(self):
        """运行演示"""
        logger.info("🎬 开始Oracle服务演示")
        logger.info("=" * 60)
        
        # 显示链状态
        self.show_chain_status()
        print()
        
        # 加载合约
        self.load_contracts()
        print()
        
        # 显示合约信息
        self.show_contract_info()
        print()
        
        # 显示Oracle能力
        self.show_oracle_capabilities()
        print()
        
        # 模拟跨链工作流程
        self.simulate_cross_chain_workflow()
        print()
        
        logger.info("🎯 演示完成！Oracle服务已准备就绪。")

def main():
    """主函数"""
    demo = DemoOracle()
    demo.run_demo()

if __name__ == "__main__":
    main()
