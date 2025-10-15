#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web3.py v6兼容的跨链Oracle服务
"""

import asyncio
import json
import logging
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from web3 import Web3
from eth_account import Account
import threading
from queue import Queue

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('oracle_v6.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class OracleV6Compatible:
    """Web3.py v6兼容的Oracle服务"""
    
    def __init__(self, config_file: str = "cross_chain_config.json"):
        """初始化Oracle服务"""
        self.config = self.load_config(config_file)
        self.chains: Dict[str, Web3] = {}
        self.contracts: Dict[str, Dict] = {}
        self.event_queue = Queue()
        self.running = False
        self.connections: Dict[str, str] = {}
        
        # 初始化各链连接
        self.setup_chains()
        
        # 初始化ACA-Py连接
        self.setup_acapy()
        
        logger.info("Web3.py v6兼容Oracle服务初始化完成")
    
    def load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"配置文件加载成功: {config_file}")
            return config
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            return self.get_default_config()
    
    def get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "oracle": {
                "admin_url": "http://localhost:8001",
                "oracle_did": "DPvobytTtKvmyeRTJZYjsg",
                "oracle_address": "0x81be24626338695584b5beaebf51e09879a0ecc6",
                "oracle_private_key": "0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a"
            },
            "chains": [
                {
                    "name": "Besu Chain A",
                    "rpc_url": "http://localhost:8545",
                    "chain_id": "chain_a",
                    "bridge_address": "0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af",
                    "verifier_address": "0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf"
                },
                {
                    "name": "Besu Chain B",
                    "rpc_url": "http://localhost:8555",
                    "chain_id": "chain_b",
                    "bridge_address": "0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af",
                    "verifier_address": "0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf"
                }
            ]
        }
    
    def setup_chains(self):
        """初始化多链连接"""
        logger.info("初始化多链连接...")
        
        for chain_config in self.config['chains']:
            chain_id = chain_config['chain_id']
            try:
                # 创建Web3连接
                w3 = Web3(Web3.HTTPProvider(chain_config['rpc_url']))
                
                # 使用手动RPC调用测试连接
                if self.test_chain_connection(chain_config['rpc_url']):
                    self.chains[chain_id] = w3
                    logger.info(f"成功连接到链 {chain_id}")
                    
                    # 加载合约ABI
                    self.load_contract_abis(chain_id, chain_config)
                else:
                    logger.error(f"无法连接到链 {chain_id}: {chain_config['rpc_url']}")
                
            except Exception as e:
                logger.error(f"初始化链 {chain_id} 失败: {e}")
    
    def test_chain_connection(self, rpc_url: str) -> bool:
        """测试链连接"""
        try:
            response = requests.post(rpc_url, 
                                   json={'jsonrpc': '2.0', 'method': 'eth_blockNumber', 'params': [], 'id': 1},
                                   timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    block_number = int(data['result'], 16)
                    logger.info(f"链连接测试成功，最新区块: {block_number}")
                    return True
            return False
        except Exception as e:
            logger.error(f"链连接测试失败: {e}")
            return False
    
    def load_contract_abis(self, chain_id: str, chain_config: Dict):
        """加载合约ABI"""
        try:
            # 加载桥合约ABI
            with open('CrossChainBridgeSimple.json', 'r') as f:
                bridge_abi = json.load(f)['abi']
            
            # 加载DID验证器ABI
            with open('CrossChainDIDVerifier.json', 'r') as f:
                verifier_abi = json.load(f)['abi']
            
            # 创建合约实例
            bridge_contract = self.chains[chain_id].eth.contract(
                address=Web3.to_checksum_address(chain_config['bridge_address']),
                abi=bridge_abi
            )
            
            verifier_contract = self.chains[chain_id].eth.contract(
                address=Web3.to_checksum_address(chain_config['verifier_address']),
                abi=verifier_abi
            )
            
            self.contracts[chain_id] = {
                'bridge': bridge_contract,
                'verifier': verifier_contract
            }
            
            logger.info(f"链 {chain_id} 合约ABI加载成功")
            
        except Exception as e:
            logger.error(f"加载链 {chain_id} 合约ABI失败: {e}")
    
    def setup_acapy(self):
        """初始化ACA-Py连接"""
        self.acapy_url = self.config['oracle']['admin_url']
        self.oracle_did = self.config['oracle']['oracle_did']
        
        # 测试ACA-Py连接
        try:
            response = requests.get(f"{self.acapy_url}/status", timeout=10)
            if response.status_code == 200:
                logger.info("ACA-Py连接成功")
                self.acapy_connected = True
            else:
                logger.warning(f"ACA-Py连接异常: {response.status_code}")
                self.acapy_connected = False
        except Exception as e:
            logger.error(f"ACA-Py连接失败: {e}")
            self.acapy_connected = False
    
    def call_contract_function(self, chain_id: str, contract_name: str, function_name: str, args: List = None):
        """调用合约函数"""
        try:
            if chain_id not in self.contracts:
                logger.error(f"链 {chain_id} 未配置")
                return None
            
            contract = self.contracts[chain_id][contract_name]
            function = getattr(contract.functions, function_name)
            
            if args:
                result = function(*args).call()
            else:
                result = function().call()
            
            return result
            
        except Exception as e:
            logger.error(f"调用合约函数失败: {e}")
            return None
    
    def get_chain_status(self, chain_id: str) -> Dict:
        """获取链状态"""
        try:
            if chain_id not in self.chains:
                return {"connected": False, "error": "链未配置"}
            
            # 使用手动RPC调用获取状态
            rpc_url = None
            for chain_config in self.config['chains']:
                if chain_config['chain_id'] == chain_id:
                    rpc_url = chain_config['rpc_url']
                    break
            
            if not rpc_url:
                return {"connected": False, "error": "RPC URL未找到"}
            
            # 获取区块号
            response = requests.post(rpc_url, 
                                   json={'jsonrpc': '2.0', 'method': 'eth_blockNumber', 'params': [], 'id': 1},
                                   timeout=10)
            if response.status_code == 200:
                data = response.json()
                block_number = int(data['result'], 16)
                
                # 获取链ID
                response = requests.post(rpc_url, 
                                       json={'jsonrpc': '2.0', 'method': 'eth_chainId', 'params': [], 'id': 2},
                                       timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    chain_id_hex = int(data['result'], 16)
                    
                    return {
                        "connected": True,
                        "block_number": block_number,
                        "chain_id": chain_id_hex
                    }
            
            return {"connected": False, "error": "RPC调用失败"}
            
        except Exception as e:
            return {"connected": False, "error": str(e)}
    
    def get_status(self) -> Dict:
        """获取Oracle服务状态"""
        status = {
            "running": self.running,
            "chains_connected": len(self.chains),
            "acapy_connected": self.acapy_connected,
            "connections": len(self.connections),
            "timestamp": datetime.now().isoformat()
        }
        
        # 检查各链状态
        status["chains"] = {}
        for chain_id in self.config['chains']:
            chain_id_key = chain_id['chain_id']
            chain_status = self.get_chain_status(chain_id_key)
            status["chains"][chain_id_key] = chain_status
        
        return status
    
    async def start_monitoring(self):
        """开始监控跨链事件"""
        logger.info("开始监控跨链事件...")
        self.running = True
        
        # 启动事件监控任务
        tasks = []
        for chain_id in self.chains.keys():
            task = asyncio.create_task(self.monitor_chain_events(chain_id))
            tasks.append(task)
        
        # 启动事件处理任务
        process_task = asyncio.create_task(self.process_events())
        tasks.append(process_task)
        
        # 启动健康检查任务
        health_task = asyncio.create_task(self.health_check())
        tasks.append(health_task)
        
        # 等待所有任务
        await asyncio.gather(*tasks)
    
    async def monitor_chain_events(self, chain_id: str):
        """监控单链事件"""
        logger.info(f"开始监控链 {chain_id} 的事件...")
        
        last_block = 0
        
        while self.running:
            try:
                # 获取当前区块号
                chain_status = self.get_chain_status(chain_id)
                if not chain_status['connected']:
                    logger.warning(f"链 {chain_id} 连接异常")
                    await asyncio.sleep(10)
                    continue
                
                current_block = chain_status['block_number']
                
                if current_block > last_block:
                    # 处理新区块
                    await self.process_new_blocks(chain_id, last_block + 1, current_block)
                    last_block = current_block
                
                await asyncio.sleep(5)  # 每5秒检查一次
                
            except Exception as e:
                logger.error(f"监控链 {chain_id} 事件时出错: {e}")
                await asyncio.sleep(10)
    
    async def process_new_blocks(self, chain_id: str, from_block: int, to_block: int):
        """处理新区块中的事件"""
        try:
            logger.info(f"处理链 {chain_id} 新区块: {from_block} - {to_block}")
            
            # 这里可以添加事件处理逻辑
            # 由于Web3.py v6的兼容性问题，暂时使用简化的处理
            
        except Exception as e:
            logger.error(f"处理链 {chain_id} 新区块时出错: {e}")
    
    async def process_events(self):
        """处理事件队列"""
        while self.running:
            try:
                if not self.event_queue.empty():
                    event = self.event_queue.get()
                    await self.handle_event(event)
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"处理事件时出错: {e}")
                await asyncio.sleep(5)
    
    async def handle_event(self, event: Dict):
        """处理单个事件"""
        try:
            event_type = event.get('type')
            logger.info(f"处理事件: {event_type}")
        except Exception as e:
            logger.error(f"处理事件时出错: {e}")
    
    async def health_check(self):
        """健康检查"""
        while self.running:
            try:
                # 检查链连接
                for chain_id in self.config['chains']:
                    chain_id_key = chain_id['chain_id']
                    chain_status = self.get_chain_status(chain_id_key)
                    if not chain_status['connected']:
                        logger.warning(f"链 {chain_id_key} 连接异常")
                
                # 检查ACA-Py连接
                if self.acapy_connected:
                    try:
                        response = requests.get(f"{self.acapy_url}/status", timeout=5)
                        if response.status_code != 200:
                            logger.warning("ACA-Py连接异常")
                            self.acapy_connected = False
                    except:
                        logger.warning("ACA-Py连接丢失")
                        self.acapy_connected = False
                
                await asyncio.sleep(60)  # 每分钟检查一次
                
            except Exception as e:
                logger.error(f"健康检查时出错: {e}")
                await asyncio.sleep(60)
    
    async def stop(self):
        """停止Oracle服务"""
        logger.info("正在停止Oracle服务...")
        self.running = False

async def main():
    """主函数"""
    logger.info("启动Web3.py v6兼容Oracle服务...")
    
    # 创建Oracle实例
    oracle = OracleV6Compatible()
    
    # 显示状态
    status = oracle.get_status()
    logger.info(f"Oracle服务状态: {json.dumps(status, indent=2)}")
    
    try:
        # 开始监控
        await oracle.start_monitoring()
    except KeyboardInterrupt:
        logger.info("收到停止信号...")
    finally:
        await oracle.stop()
        logger.info("Oracle服务已停止")

if __name__ == "__main__":
    asyncio.run(main())
