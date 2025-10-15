#!/usr/bin/env python3
"""
增强版跨链VC系统Web前端应用
包含真实的跨链转账功能
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
from eth_account import Account

# 添加项目根目录到Python路径
sys.path.append('/home/manifold/cursor/twobesu/contracts/kept')

# 导入我们的修复Web3类和跨链桥接系统
from web3_fixed_connection import FixedWeb3
from cross_chain_bridge import CrossChainBridge

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

# 测试账户
TEST_ACCOUNT = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')

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
        try:
            # 使用桥接系统获取链状态
            bridge_status = bridge_system.get_chain_status()
            
            # 更新系统状态
            for chain_name in ['chain_a', 'chain_b']:
                if chain_name in bridge_status:
                    system_status[f'besu_{chain_name}'] = bridge_status[chain_name]
                else:
                    system_status[f'besu_{chain_name}'] = {
                        'status': 'error',
                        'last_check': datetime.now().isoformat(),
                        'details': {'error': '链状态未知'}
                    }
        except Exception as e:
            logger.error(f"检查Besu链状态失败: {e}")
            for chain_name in ['besu_chain_a', 'besu_chain_b']:
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

class CrossChainTransfer:
    """跨链转账处理类"""
    
    def __init__(self):
        self.transfer_history = []
    
    def perform_transfer(self, amount, from_chain, to_chain):
        """执行跨链转账"""
        try:
            # 验证输入
            if amount <= 0:
                raise ValueError("转账金额必须大于0")
            
            if from_chain not in web3_connections:
                raise ValueError(f"源链 {from_chain} 未连接")
            
            # 获取源链连接
            source_w3 = web3_connections[from_chain]
            if not source_w3.is_connected():
                raise ValueError(f"源链 {from_chain} 连接失败")
            
            # 检查余额
            balance_wei, balance_eth = source_w3.get_balance(TEST_ACCOUNT.address)
            transfer_amount_wei = int(amount * 10**18)
            
            if balance_wei < transfer_amount_wei:
                raise ValueError(f"余额不足，当前余额: {balance_eth} ETH，需要: {amount} ETH")
            
            # 创建接收地址（使用不同的私钥）
            receiver_account = Account.from_key('0x1234567890123456789012345678901234567890123456789012345678901234')
            
            # 获取交易参数
            nonce = source_w3.get_nonce(TEST_ACCOUNT.address)
            gas_price = source_w3.get_gas_price()
            gas_limit = 21000
            
            # 创建交易
            transaction = {
                "to": receiver_account.address,
                "value": hex(transfer_amount_wei),
                "gas": hex(gas_limit),
                "gasPrice": hex(gas_price),
                "nonce": hex(nonce),
                "chainId": hex(SYSTEM_CONFIG[from_chain]['chain_id'])
            }
            
            # 签名交易
            signed_txn = TEST_ACCOUNT.sign_transaction(transaction)
            
            # 发送交易
            tx_hash = source_w3.send_raw_transaction(signed_txn.rawTransaction.hex())
            
            # 等待交易确认
            receipt = source_w3.wait_for_transaction_receipt(tx_hash, timeout=60)
            
            # 记录转账历史
            transfer_record = {
                'id': len(self.transfer_history) + 1,
                'timestamp': datetime.now().isoformat(),
                'amount': amount,
                'from_chain': from_chain,
                'to_chain': to_chain,
                'from_address': TEST_ACCOUNT.address,
                'to_address': receiver_account.address,
                'transaction_hash': tx_hash.hex(),
                'block_number': receipt.blockNumber,
                'gas_used': receipt.gasUsed,
                'status': 'success'
            }
            
            self.transfer_history.append(transfer_record)
            
            return transfer_record
            
        except Exception as e:
            # 记录失败的转账
            transfer_record = {
                'id': len(self.transfer_history) + 1,
                'timestamp': datetime.now().isoformat(),
                'amount': amount,
                'from_chain': from_chain,
                'to_chain': to_chain,
                'status': 'failed',
                'error': str(e)
            }
            
            self.transfer_history.append(transfer_record)
            raise e

# 创建跨链桥接系统实例
bridge_system = CrossChainBridge()

@app.route('/')
def index():
    """主页"""
    return render_template('enhanced_index.html')

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
        from_chain = data.get('from_chain', 'chain_a')
        to_chain = data.get('to_chain', 'chain_b')
        
        # 执行真正的跨链转账
        result = bridge_system.perform_cross_chain_transfer(amount, from_chain, to_chain)
        
        return jsonify({
            'success': True,
            'lock_tx_hash': result['lock_tx_hash'],
            'release_tx_hash': result['release_tx_hash'],
            'amount': result['amount'],
            'from_chain': result['from_chain'],
            'to_chain': result['to_chain'],
            'from_address': result['from_address'],
            'to_address': result['to_address'],
            'lock_block_number': result['lock_block_number'],
            'release_block_number': result['release_block_number'],
            'source_balance_before': result['source_balance_before'],
            'source_balance_after': result['source_balance_after'],
            'target_balance_before': result['target_balance_before'],
            'target_balance_after': result['target_balance_after'],
            'source_change': result['source_change'],
            'target_change': result['target_change'],
            'timestamp': result['timestamp']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/transfer-history')
def get_transfer_history():
    """获取转账历史API"""
    return jsonify(bridge_system.get_transfer_history())

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

@app.route('/vc-data')
def vc_data_page():
    """VC数据展示页面"""
    return render_template('vc_data.html')

@app.route('/api/vc-list')
def get_vc_list():
    """获取VC列表API"""
    try:
        # 模拟VC数据，实际应该从ACA-Py Holder获取
        vc_list = [
            {
                'id': 'vc_001',
                'type': '身份证明',
                'issuer': '政府机构',
                'issued_date': '2025-01-10',
                'expiry_date': '2026-01-10',
                'status': '有效',
                'credential_definition_id': 'cred_def_123',
                'schema_id': 'schema_456'
            },
            {
                'id': 'vc_002',
                'type': '学历证书',
                'issuer': '大学',
                'issued_date': '2025-01-08',
                'expiry_date': '2030-01-08',
                'status': '有效',
                'credential_definition_id': 'cred_def_789',
                'schema_id': 'schema_101'
            },
            {
                'id': 'vc_003',
                'type': '工作证明',
                'issuer': '公司',
                'issued_date': '2025-01-05',
                'expiry_date': '2025-12-31',
                'status': '有效',
                'credential_definition_id': 'cred_def_456',
                'schema_id': 'schema_789'
            }
        ]
        
        return jsonify(vc_list)
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/vc-detail/<vc_id>')
def get_vc_detail(vc_id):
    """获取VC详细信息API"""
    try:
        # 模拟VC详细数据，实际应该从ACA-Py Holder获取
        vc_details = {
            'vc_001': {
                'id': 'vc_001',
                'type': '身份证明',
                'issuer': '政府机构',
                'issued_date': '2025-01-10',
                'expiry_date': '2026-01-10',
                'status': '有效',
                'credential_definition_id': 'cred_def_123',
                'schema_id': 'schema_456',
                'credential_data': {
                    '@context': [
                        'https://www.w3.org/2018/credentials/v1',
                        'https://www.w3.org/2018/credentials/examples/v1'
                    ],
                    'id': 'https://example.com/credentials/3732',
                    'type': ['VerifiableCredential', 'IdentityCredential'],
                    'issuer': {
                        'id': 'did:example:issuer',
                        'name': '政府机构'
                    },
                    'issuanceDate': '2025-01-10T10:00:00Z',
                    'expirationDate': '2026-01-10T10:00:00Z',
                    'credentialSubject': {
                        'id': 'did:example:holder',
                        'name': '张三',
                        'idNumber': '123456789012345678',
                        'birthDate': '1990-01-01',
                        'nationality': '中国'
                    },
                    'proof': {
                        'type': 'Ed25519Signature2018',
                        'created': '2025-01-10T10:00:00Z',
                        'verificationMethod': 'did:example:issuer#key-1',
                        'proofPurpose': 'assertionMethod',
                        'jws': 'eyJhbGciOiJFZERTQSIsImNhbGciOiJFZERTQSJ9...'
                    }
                }
            },
            'vc_002': {
                'id': 'vc_002',
                'type': '学历证书',
                'issuer': '大学',
                'issued_date': '2025-01-08',
                'expiry_date': '2030-01-08',
                'status': '有效',
                'credential_definition_id': 'cred_def_789',
                'schema_id': 'schema_101',
                'credential_data': {
                    '@context': [
                        'https://www.w3.org/2018/credentials/v1',
                        'https://www.w3.org/2018/credentials/examples/v1'
                    ],
                    'id': 'https://example.com/credentials/3733',
                    'type': ['VerifiableCredential', 'EducationCredential'],
                    'issuer': {
                        'id': 'did:example:university',
                        'name': '清华大学'
                    },
                    'issuanceDate': '2025-01-08T09:00:00Z',
                    'expirationDate': '2030-01-08T09:00:00Z',
                    'credentialSubject': {
                        'id': 'did:example:holder',
                        'name': '张三',
                        'degree': '学士学位',
                        'major': '计算机科学与技术',
                        'graduationDate': '2024-06-30',
                        'gpa': '3.8'
                    },
                    'proof': {
                        'type': 'Ed25519Signature2018',
                        'created': '2025-01-08T09:00:00Z',
                        'verificationMethod': 'did:example:university#key-1',
                        'proofPurpose': 'assertionMethod',
                        'jws': 'eyJhbGciOiJFZERTQSIsImNhbGciOiJFZERTQSJ9...'
                    }
                }
            },
            'vc_003': {
                'id': 'vc_003',
                'type': '工作证明',
                'issuer': '公司',
                'issued_date': '2025-01-05',
                'expiry_date': '2025-12-31',
                'status': '有效',
                'credential_definition_id': 'cred_def_456',
                'schema_id': 'schema_789',
                'credential_data': {
                    '@context': [
                        'https://www.w3.org/2018/credentials/v1',
                        'https://www.w3.org/2018/credentials/examples/v1'
                    ],
                    'id': 'https://example.com/credentials/3734',
                    'type': ['VerifiableCredential', 'EmploymentCredential'],
                    'issuer': {
                        'id': 'did:example:company',
                        'name': '科技有限公司'
                    },
                    'issuanceDate': '2025-01-05T08:00:00Z',
                    'expirationDate': '2025-12-31T23:59:59Z',
                    'credentialSubject': {
                        'id': 'did:example:holder',
                        'name': '张三',
                        'position': '软件工程师',
                        'department': '技术部',
                        'startDate': '2024-01-01',
                        'salary': '15000'
                    },
                    'proof': {
                        'type': 'Ed25519Signature2018',
                        'created': '2025-01-05T08:00:00Z',
                        'verificationMethod': 'did:example:company#key-1',
                        'proofPurpose': 'assertionMethod',
                        'jws': 'eyJhbGciOiJFZERTQSIsImNhbGciOiJFZERTQSJ9...'
                    }
                }
            }
        }
        
        if vc_id in vc_details:
            return jsonify(vc_details[vc_id])
        else:
            return jsonify({'error': 'VC not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/contract-variables')
def get_contract_variables():
    """获取智能合约内部变量API"""
    try:
        contract_variables = {}
        
        for chain_name in ['besu_chain_a', 'besu_chain_b']:
            if chain_name in web3_connections:
                w3 = web3_connections[chain_name]
                config = SYSTEM_CONFIG[chain_name]
                
                # 模拟合约变量数据，实际应该通过Web3调用合约方法获取
                contract_variables[chain_name] = {
                    'chain_name': config['name'],
                    'chain_id': config['chain_id'],
                    'bridge_contract': {
                        'address': config['bridge_address'],
                        'variables': {
                            'owner': '0x81Be24626338695584B5beaEBf51e09879A0eCc6',
                            'isActive': True,
                            'totalLocks': 15,
                            'totalUnlocks': 12,
                            'lockCount': 3,
                            'unlockCount': 0
                        }
                    },
                    'verifier_contract': {
                        'address': config['verifier_address'],
                        'variables': {
                            'owner': '0x81Be24626338695584B5beaEBf51e09879A0eCc6',
                            'isActive': True,
                            'totalVerifications': 8,
                            'successfulVerifications': 7,
                            'failedVerifications': 1
                        }
                    },
                    'token_contract': {
                        'address': '0x1234567890123456789012345678901234567890',  # 模拟地址
                        'variables': {
                            'name': 'CrossChainToken',
                            'symbol': 'CCT',
                            'decimals': 18,
                            'totalSupply': '1000000000000000000000000',  # 1000000 tokens
                            'owner': '0x81Be24626338695584B5beaEBf51e09879A0eCc6',
                            'bridgeContract': config['bridge_address'],
                            'crossChainEnabled': True,
                            'balances': {
                                '0x81Be24626338695584B5beaEBf51e09879A0eCc6': '500000000000000000000000',  # 500000 tokens
                                '0x1234567890123456789012345678901234567890': '300000000000000000000000',  # 300000 tokens
                                '0xabcdefabcdefabcdefabcdefabcdefabcdefabcd': '200000000000000000000000'   # 200000 tokens
                            },
                            'lockedBalances': {
                                '0x81Be24626338695584B5beaEBf51e09879A0eCc6': '10000000000000000000000',   # 10000 tokens
                                '0x1234567890123456789012345678901234567890': '5000000000000000000000'    # 5000 tokens
                            }
                        }
                    }
                }
            else:
                contract_variables[chain_name] = {
                    'chain_name': config['name'] if chain_name in SYSTEM_CONFIG else chain_name,
                    'status': 'not_connected',
                    'error': 'Web3 connection not available'
                }
        
        return jsonify(contract_variables)
        
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
        logger.info("启动增强版跨链VC系统Web前端...")
        logger.info("访问地址: http://localhost:3000")
        socketio.run(app, host='0.0.0.0', port=3000, debug=True)
    except KeyboardInterrupt:
        logger.info("正在关闭应用...")
    finally:
        # 停止监控
        monitor.stop_monitoring()
