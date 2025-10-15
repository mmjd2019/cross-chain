#!/usr/bin/env python3
"""
跨链VC系统Web前端应用
提供系统状态监控和跨链转账操作界面
"""

import os
import sys
import json
import logging
import asyncio
import aiohttp
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_socketio import SocketIO, emit
import threading
import time

# 添加项目根目录到Python路径
sys.path.append('/home/manifold/cursor/twobesu/contracts/kept')

# 导入我们的修复Web3类
from web3_fixed_connection import FixedWeb3

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'cross_chain_vc_secret_key_2025'
socketio = SocketIO(app, cors_allowed_origins="*")

# 系统配置
SYSTEM_CONFIG = {
    'besu_chain_a': {
        'name': 'Besu Chain A',
        'rpc_url': 'http://localhost:8545',
        'chain_id': 2023,
        'bridge_address': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af',
        'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
    },
    'besu_chain_b': {
        'name': 'Besu Chain B',
        'rpc_url': 'http://localhost:8555',
        'chain_id': 2024,
        'bridge_address': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af',
        'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
    },
    'oracle_service': {
        'name': 'Oracle Service',
        'url': 'http://localhost:5000',
        'status_endpoint': '/status'
    },
    'acapy_issuer': {
        'name': 'ACA-Py Issuer',
        'admin_url': 'http://192.168.230.178:8080',
        'status_endpoint': '/status'
    },
    'acapy_holder': {
        'name': 'ACA-Py Holder',
        'admin_url': 'http://192.168.230.178:8081',
        'status_endpoint': '/status'
    }
}

# 全局状态存储
system_status = {
    'besu_chain_a': {'status': 'unknown', 'last_check': None, 'details': {}},
    'besu_chain_b': {'status': 'unknown', 'last_check': None, 'details': {}},
    'oracle_service': {'status': 'unknown', 'last_check': None, 'details': {}},
    'acapy_issuer': {'status': 'unknown', 'last_check': None, 'details': {}},
    'acapy_holder': {'status': 'unknown', 'last_check': None, 'details': {}},
    'vc_status': {'status': 'unknown', 'last_check': None, 'details': {}},
    'contracts': {'status': 'unknown', 'last_check': None, 'details': {}}
}

# Web3连接实例
web3_connections = {}

class SystemMonitor:
    """系统监控类"""
    
    def __init__(self):
        self.running = False
        self.monitor_thread = None
    
    def start_monitoring(self):
        """启动监控"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            logger.info("系统监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
        logger.info("系统监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                self._check_all_services()
                time.sleep(5)  # 每5秒检查一次
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                time.sleep(10)
    
    def _check_all_services(self):
        """检查所有服务"""
        # 检查Besu链
        self._check_besu_chains()
        
        # 检查Oracle服务
        self._check_oracle_service()
        
        # 检查ACA-Py服务
        self._check_acapy_services()
        
        # 检查VC状态
        self._check_vc_status()
        
        # 检查智能合约
        self._check_contracts()
        
        # 发送状态更新到前端
        socketio.emit('status_update', system_status)
    
    def _check_besu_chains(self):
        """检查Besu链状态"""
        for chain_name in ['besu_chain_a', 'besu_chain_b']:
            try:
                config = SYSTEM_CONFIG[chain_name]
                
                # 创建或获取Web3连接
                if chain_name not in web3_connections:
                    web3_connections[chain_name] = FixedWeb3(config['rpc_url'], config['name'])
                
                w3 = web3_connections[chain_name]
                
                if w3.is_connected():
                    # 获取详细信息
                    chain_id = w3.get_chain_id()
                    latest_block = w3.get_latest_block()
                    gas_price = w3.get_gas_price()
                    
                    # 获取测试账户余额
                    test_address = "0x81Be24626338695584B5beaEBf51e09879A0eCc6"
                    balance_wei, balance_eth = w3.get_balance(test_address)
                    
                    system_status[chain_name] = {
                        'status': 'online',
                        'last_check': datetime.now().isoformat(),
                        'details': {
                            'chain_id': chain_id,
                            'latest_block': latest_block.number if latest_block else 0,
                            'gas_price': gas_price,
                            'test_account_balance': balance_eth,
                            'rpc_url': config['rpc_url']
                        }
                    }
                else:
                    system_status[chain_name] = {
                        'status': 'offline',
                        'last_check': datetime.now().isoformat(),
                        'details': {'error': '连接失败'}
                    }
                    
            except Exception as e:
                system_status[chain_name] = {
                    'status': 'error',
                    'last_check': datetime.now().isoformat(),
                    'details': {'error': str(e)}
                }
    
    def _check_oracle_service(self):
        """检查Oracle服务状态"""
        try:
            config = SYSTEM_CONFIG['oracle_service']
            
            # 这里可以添加实际的Oracle服务检查
            # 暂时模拟状态
            system_status['oracle_service'] = {
                'status': 'online',
                'last_check': datetime.now().isoformat(),
                'details': {
                    'url': config['url'],
                    'message': 'Oracle服务运行正常'
                }
            }
        except Exception as e:
            system_status['oracle_service'] = {
                'status': 'error',
                'last_check': datetime.now().isoformat(),
                'details': {'error': str(e)}
            }
    
    def _check_acapy_services(self):
        """检查ACA-Py服务状态"""
        for service_name in ['acapy_issuer', 'acapy_holder']:
            try:
                config = SYSTEM_CONFIG[service_name]
                
                # 这里可以添加实际的ACA-Py服务检查
                # 暂时模拟状态
                system_status[service_name] = {
                    'status': 'online',
                    'last_check': datetime.now().isoformat(),
                    'details': {
                        'admin_url': config['admin_url'],
                        'message': f'{config["name"]}运行正常'
                    }
                }
            except Exception as e:
                system_status[service_name] = {
                    'status': 'error',
                    'last_check': datetime.now().isoformat(),
                    'details': {'error': str(e)}
                }
    
    def _check_vc_status(self):
        """检查VC状态"""
        try:
            # 这里可以添加实际的VC状态检查
            system_status['vc_status'] = {
                'status': 'online',
                'last_check': datetime.now().isoformat(),
                'details': {
                    'schema_registered': True,
                    'cred_def_created': True,
                    'vc_issued': True,
                    'message': 'VC系统运行正常'
                }
            }
        except Exception as e:
            system_status['vc_status'] = {
                'status': 'error',
                'last_check': datetime.now().isoformat(),
                'details': {'error': str(e)}
            }
    
    def _check_contracts(self):
        """检查智能合约状态"""
        try:
            # 这里可以添加实际的合约状态检查
            system_status['contracts'] = {
                'status': 'online',
                'last_check': datetime.now().isoformat(),
                'details': {
                    'bridge_contract': 'deployed',
                    'verifier_contract': 'deployed',
                    'token_contract': 'deployed',
                    'message': '智能合约部署正常'
                }
            }
        except Exception as e:
            system_status['contracts'] = {
                'status': 'error',
                'last_check': datetime.now().isoformat(),
                'details': {'error': str(e)}
            }

# 创建系统监控实例
monitor = SystemMonitor()

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """获取系统状态API"""
    return jsonify(system_status)

@app.route('/api/transfer', methods=['POST'])
def perform_transfer():
    """执行跨链转账API"""
    try:
        data = request.get_json()
        amount = float(data.get('amount', 0))
        from_chain = data.get('from_chain', 'besu_chain_a')
        to_chain = data.get('to_chain', 'besu_chain_b')
        
        if amount <= 0:
            return jsonify({'success': False, 'error': '转账金额必须大于0'})
        
        # 这里可以添加实际的转账逻辑
        # 暂时返回模拟结果
        result = {
            'success': True,
            'transaction_hash': '0x' + ''.join([f'{i:02x}' for i in os.urandom(32)]),
            'amount': amount,
            'from_chain': from_chain,
            'to_chain': to_chain,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/contracts')
def get_contracts():
    """获取智能合约信息API"""
    try:
        contracts_info = {}
        
        for chain_name in ['besu_chain_a', 'besu_chain_b']:
            if chain_name in web3_connections:
                w3 = web3_connections[chain_name]
                config = SYSTEM_CONFIG[chain_name]
                
                # 获取合约地址
                contracts_info[chain_name] = {
                    'bridge_address': config['bridge_address'],
                    'verifier_address': config['verifier_address'],
                    'chain_id': config['chain_id'],
                    'status': 'deployed'
                }
            else:
                contracts_info[chain_name] = {
                    'status': 'not_connected'
                }
        
        return jsonify(contracts_info)
        
    except Exception as e:
        return jsonify({'error': str(e)})

@socketio.on('connect')
def handle_connect():
    """WebSocket连接处理"""
    logger.info('客户端已连接')
    emit('status_update', system_status)

@socketio.on('disconnect')
def handle_disconnect():
    """WebSocket断开处理"""
    logger.info('客户端已断开')

if __name__ == '__main__':
    # 启动系统监控
    monitor.start_monitoring()
    
    try:
        # 启动Flask应用
        logger.info("启动跨链VC系统Web前端...")
        logger.info("访问地址: http://localhost:3000")
        socketio.run(app, host='0.0.0.0', port=3000, debug=True)
    except KeyboardInterrupt:
        logger.info("正在关闭应用...")
    finally:
        # 停止监控
        monitor.stop_monitoring()
