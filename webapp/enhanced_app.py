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
import subprocess
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_socketio import SocketIO, emit
import threading
import time
from eth_account import Account

# 添加项目根目录到Python路径
sys.path.insert(0, '/home/manifold/cursor/cross-chain-new/contracts/kept')
sys.path.insert(0, '/home/manifold/cursor/cross-chain-new/oracle')

# 导入我们的修复Web3类和跨链桥接系统
from web3_fixed_connection import FixedWeb3
# from cross_chain_bridge import CrossChainBridge  # 模块不存在，暂时注释

# 导入 VC 跨链传输服务模块
from vc_transfer_api import vc_crosschain_service

# 导入 VC 跨链传输 API 路由 Blueprint
from vc_transfer_routes import vc_transfer_bp


# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'cross_chain_vc_secret_key_2025'
socketio = SocketIO(app, cors_allowed_origins="*")

# 注册 VC 跨链传输 Blueprint
app.register_blueprint(vc_transfer_bp)

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
    'vc_issuance_oracle': {'status': 'unknown', 'last_check': None, 'details': {}},
    'vp_oracle': {'status': 'unknown', 'last_check': None, 'details': {}},
    'vc_transfer_oracle': {'status': 'unknown', 'last_check': None, 'details': {}},
    'acapy_issuer': {'status': 'unknown', 'last_check': None, 'details': {}},
    'acapy_holder': {'status': 'unknown', 'last_check': None, 'details': {}},
    'acapy_verifier': {'status': 'unknown', 'last_check': None, 'details': {}}
}

# Web3连接实例
web3_connections = {}

# 测试账户
TEST_ACCOUNT = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')

class SystemMonitor:
    """系统监控类 - 真实健康检查"""

    def __init__(self):
        self.running = False
        self.monitor_thread = None

    def start_monitoring(self):
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            logger.info("系统监控已启动")

    def stop_monitoring(self):
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
        logger.info("系统监控已停止")

    def _monitor_loop(self):
        while self.running:
            try:
                self._check_all_services()
                time.sleep(10)
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                time.sleep(15)

    def _check_all_services(self):
        self._check_besu('besu_chain_a', 'http://localhost:8545')
        self._check_besu('besu_chain_b', 'http://localhost:8555')
        self._check_http('vc_issuance_oracle', 'http://localhost:6000/health', timeout=3)
        self._check_http('vp_oracle', 'http://localhost:7003/api/health', timeout=3)
        self._check_vc_transfer_oracle()
        self._check_acapy('acapy_issuer', 'http://localhost:8080')
        self._check_acapy('acapy_holder', 'http://localhost:8081')
        self._check_acapy('acapy_verifier', 'http://localhost:8082')
        socketio.emit('status_update', system_status)

    def _check_besu(self, key, rpc_url):
        now = datetime.now().isoformat()
        try:
            # 使用requests直接发JSON-RPC，避免Web3.py在eventlet下的兼容性问题
            def rpc_call(method, params=None):
                payload = {"jsonrpc": "2.0", "method": method, "params": params or [], "id": 1}
                resp = requests.post(rpc_url, json=payload, timeout=3)
                result = resp.json()
                return result.get("result")

            chain_id = rpc_call("eth_chainId")
            if chain_id is None:
                system_status[key] = {'status': 'offline', 'last_check': now, 'details': {'message': '无法连接'}}
                return
            block_number = int(rpc_call("eth_blockNumber"), 16)
            peer_count = rpc_call("net_peerCount")
            peer_count = int(peer_count, 16) if peer_count else 0
            syncing = rpc_call("eth_syncing")
            system_status[key] = {
                'status': 'online',
                'last_check': now,
                'details': {
                    'chain_id': str(int(chain_id, 16)),
                    'latest_block': str(block_number),
                    'peer_count': str(peer_count),
                    'syncing': bool(syncing)
                }
            }
        except Exception as e:
            system_status[key] = {'status': 'offline', 'last_check': now, 'details': {'message': str(e)[:80]}}

    def _check_http(self, key, url, timeout=3):
        now = datetime.now().isoformat()
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                system_status[key] = {
                    'status': 'online',
                    'last_check': now,
                    'details': {'message': '服务正常'}
                }
            else:
                system_status[key] = {
                    'status': 'error',
                    'last_check': now,
                    'details': {'message': f'HTTP {resp.status_code}'}
                }
        except requests.exceptions.ConnectionError:
            system_status[key] = {'status': 'offline', 'last_check': now, 'details': {'message': '连接被拒绝'}}
        except requests.exceptions.Timeout:
            system_status[key] = {'status': 'offline', 'last_check': now, 'details': {'message': '请求超时'}}
        except Exception as e:
            system_status[key] = {'status': 'offline', 'last_check': now, 'details': {'message': str(e)[:80]}}

    def _check_vc_transfer_oracle(self):
        """VC传输Oracle没有HTTP接口，通过检查两条链连通性间接判断"""
        now = datetime.now().isoformat()
        try:
            def chain_ok(rpc_url):
                payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
                resp = requests.post(rpc_url, json=payload, timeout=3)
                return resp.json().get("result") is not None

            a_ok = chain_ok('http://localhost:8545')
            b_ok = chain_ok('http://localhost:8555')
            if a_ok and b_ok:
                system_status['vc_transfer_oracle'] = {
                    'status': 'online', 'last_check': now,
                    'details': {'message': '双链连通'}
                }
            else:
                system_status['vc_transfer_oracle'] = {
                    'status': 'offline', 'last_check': now,
                    'details': {'message': f'Chain A: {"连通" if a_ok else "不通"}, Chain B: {"连通" if b_ok else "不通"}'}
                }
        except Exception as e:
            system_status['vc_transfer_oracle'] = {'status': 'offline', 'last_check': now, 'details': {'message': str(e)[:80]}}

    def _check_acapy(self, key, admin_url):
        now = datetime.now().isoformat()
        try:
            resp = requests.get(f'{admin_url}/status', timeout=3)
            if resp.status_code == 200:
                system_status[key] = {
                    'status': 'online',
                    'last_check': now,
                    'details': {'message': '服务正常'}
                }
            else:
                system_status[key] = {
                    'status': 'error',
                    'last_check': now,
                    'details': {'message': f'HTTP {resp.status_code}'}
                }
        except requests.exceptions.ConnectionError:
            system_status[key] = {'status': 'offline', 'last_check': now, 'details': {'message': '连接被拒绝'}}
        except requests.exceptions.Timeout:
            system_status[key] = {'status': 'offline', 'last_check': now, 'details': {'message': '请求超时'}}
        except Exception as e:
            system_status[key] = {'status': 'offline', 'last_check': now, 'details': {'message': str(e)[:80]}}

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
bridge_system = None  # CrossChainBridge()  # 模块不存在，暂时注释

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

@app.route('/contract-viewer')
def contract_viewer_page():
    """智能合约状态查看器页面"""
    return render_template('contract_viewer.html')

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

# ==================== 智能合约状态查看器 API ====================

CONTRACTS_DIR = '/home/manifold/cursor/cross-chain-new/contracts/kept'
OUTPUT_FILE = os.path.join(CONTRACTS_DIR, 'contract_state', 'all_public_variables.json')
SCRIPT_PATH = os.path.join(CONTRACTS_DIR, 'read_all_public_variables.py')

# 合约查看器全局状态
contract_viewer_status = {
    "is_running": False,
    "last_success": None,
    "last_error": None,
    "start_time": None,
    "progress": ""
}

def load_contract_data():
    """加载合约数据"""
    try:
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        logger.error(f"加载合约数据失败: {e}")
        return None

def run_refresh_script():
    """后台运行刷新脚本"""
    contract_viewer_status["is_running"] = True
    contract_viewer_status["start_time"] = datetime.now().isoformat()
    contract_viewer_status["progress"] = "开始执行..."
    contract_viewer_status["last_error"] = None

    try:
        result = subprocess.run(
            ["python3", SCRIPT_PATH],
            cwd=CONTRACTS_DIR,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            contract_viewer_status["last_success"] = datetime.now().isoformat()
            contract_viewer_status["progress"] = "执行成功"
            logger.info("合约数据刷新成功")
        else:
            contract_viewer_status["last_error"] = result.stderr[-500:] if result.stderr else "未知错误"
            contract_viewer_status["progress"] = "执行失败"
            logger.error(f"合约数据刷新失败: {contract_viewer_status['last_error']}")
    except subprocess.TimeoutExpired:
        contract_viewer_status["last_error"] = "执行超时（超过2分钟）"
        contract_viewer_status["progress"] = "执行超时"
        logger.error("合约数据刷新超时")
    except Exception as e:
        contract_viewer_status["last_error"] = str(e)
        contract_viewer_status["progress"] = "执行失败"
        logger.error(f"合约数据刷新异常: {e}")
    finally:
        contract_viewer_status["is_running"] = False

@app.route('/api/contract-viewer/status')
def contract_viewer_api_status():
    """获取刷新状态"""
    last_modified = None
    if os.path.exists(OUTPUT_FILE):
        last_modified = datetime.fromtimestamp(os.path.getmtime(OUTPUT_FILE)).isoformat()

    return jsonify({
        "is_running": contract_viewer_status["is_running"],
        "last_success": contract_viewer_status.get("last_success"),
        "last_error": contract_viewer_status.get("last_error"),
        "start_time": contract_viewer_status.get("start_time"),
        "progress": contract_viewer_status.get("progress"),
        "file_last_modified": last_modified
    })

@app.route('/api/contract-viewer/refresh', methods=['POST'])
def contract_viewer_api_refresh():
    """触发数据刷新"""
    if contract_viewer_status["is_running"]:
        return jsonify({"success": False, "message": "刷新任务正在运行中..."})

    thread = threading.Thread(target=run_refresh_script)
    thread.daemon = True
    thread.start()

    return jsonify({"success": True, "message": "刷新任务已启动"})

@app.route('/api/contract-viewer/summary')
def contract_viewer_api_summary():
    """获取数据摘要"""
    data = load_contract_data()

    if data is None:
        return jsonify({"error": "无法加载数据文件"})

    summary = data.get("summary", {})
    chains = data.get("chains", {})

    result = {
        "timestamp": data.get("timestamp"),
        "summary": summary,
        "chains": {}
    }

    for chain_name, chain_data in chains.items():
        contracts = []
        for contract in chain_data.get("contracts", []):
            contracts.append({
                "name": contract.get("contract_name"),
                "address": contract.get("address"),
                "simple_vars_count": len(contract.get("simple_variables", {})),
                "mappings_count": len(contract.get("mappings", {}))
            })

        result["chains"][chain_name] = {
            "name": chain_data.get("name"),
            "contracts": contracts
        }

    return jsonify(result)

@app.route('/api/contract-viewer/contract/<chain_name>/<contract_name>')
def contract_viewer_api_contract_detail(chain_name, contract_name):
    """获取单个合约的详细信息"""
    data = load_contract_data()

    if data is None:
        return jsonify({"error": "无法加载数据文件"})

    chain_data = data.get("chains", {}).get(chain_name)
    if not chain_data:
        return jsonify({"error": f"未找到链: {chain_name}"})

    for contract in chain_data.get("contracts", []):
        if contract.get("contract_name") == contract_name:
            return jsonify(contract)

    return jsonify({"error": f"未找到合约: {contract_name}"})

# ==================== 配置文件查看器 API ====================

# 配置文件路径配置
CONFIG_DIR = '/home/manifold/cursor/cross-chain-new/config'
ORACLE_DIR = '/home/manifold/cursor/cross-chain-new/oracle'

# 配置文件定义 - 按实际文件位置分类
CONFIG_FILES = {
    'did': {
        'files': ['did.json', 'address.json', 'did_address_map.json', 'did_registration_result.json'],
        'base_dir': CONFIG_DIR
    },
    'schema': {
        'files': ['vc_config.json', 'schema_cred_def_batch_results.json'],
        'base_dir': CONFIG_DIR
    },
    'contract': {
        'files': ['deployed_contracts_config.json'],  # cross_chain_config.json 不存在，已移除
        'base_dir': CONFIG_DIR
    },
    'oracle': {
        # oracle目录下的文件
        'files': ['vc_issuance_config.json', 'vp_verification_oracle_config.json'],
        'base_dir': ORACLE_DIR
    },
    'oracle_config': {
        # config目录下的oracle相关文件
        'files': ['cross_chain_oracle_config.json', 'blockchain_config.json'],
        'base_dir': CONFIG_DIR
    }
}


def get_config_file_path(category, filename, subdir=None):
    """获取配置文件完整路径"""
    if category in CONFIG_FILES:
        return os.path.join(CONFIG_FILES[category]['base_dir'], filename)

    # 兼容旧的路径逻辑
    if subdir == 'oracle':
        return os.path.join(ORACLE_DIR, filename)
    return os.path.join(CONFIG_DIR, filename)


def load_config_file(category, filename, subdir=None):
    """加载配置文件内容"""
    filepath = get_config_file_path(category, filename, subdir)

    if not os.path.exists(filepath):
        return {
            'error': f'文件不存在: {filepath}',
            'filepath': filepath,
            'exists': False
        }

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = json.load(f)

        file_stat = os.stat(filepath)

        return {
            'category': category,
            'filename': filename,
            'filepath': filepath,
            'exists': True,
            'size': file_stat.st_size,
            'modified': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
            'content': content,
            'subdir': subdir
        }
    except json.JSONDecodeError as e:
        return {
            'error': f'JSON解析错误: {str(e)}',
            'filepath': filepath,
            'exists': True,
            'parse_error': True
        }
    except Exception as e:
        return {
            'error': f'读取文件失败: {str(e)}',
            'filepath': filepath,
            'exists': True,
            'read_error': True
        }


@app.route('/config-viewer')
def config_viewer_page():
    """配置文件查看器页面"""
    return render_template('config_viewer.html')


@app.route('/api/config-viewer/status')
def config_viewer_api_status():
    """获取配置文件状态"""
    status_info = {
        'last_load': datetime.now().isoformat(),
        'categories': {}
    }

    for category, config in CONFIG_FILES.items():
        category_status = {
            'exists': True,
            'file_count': len(config['files']),
            'files': {}
        }

        for filename in config['files']:
            filepath = os.path.join(config['base_dir'], filename)
            category_status['files'][filename] = {
                'exists': os.path.exists(filepath),
                'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat() if os.path.exists(filepath) else None
            }

        status_info['categories'][category] = category_status

    return jsonify(status_info)


@app.route('/api/config-viewer/summary')
def config_viewer_api_summary():
    """获取配置文件摘要"""
    summary = {
        'did': {'exists': False, 'count': 0},
        'schema': {'exists': False, 'count': 0},
        'contract': {'exists': False, 'count': 0},
        'oracle': {'exists': False, 'count': 0}
    }

    for category, config in CONFIG_FILES.items():
        for filename in config['files']:
            filepath = os.path.join(config['base_dir'], filename)
            if os.path.exists(filepath):
                # oracle_config 分类合并到 oracle 中
                summary_key = 'oracle' if category == 'oracle_config' else category
                summary[summary_key]['exists'] = True
                summary[summary_key]['count'] += 1

    return jsonify(summary)


@app.route('/api/config-viewer/config/<category>/<filename>')
def config_viewer_api_config(category, filename):
    """获取单个配置文件的详细内容"""
    subdir = request.args.get('subdir')
    result = load_config_file(category, filename, subdir)

    if 'error' in result:
        return jsonify(result)

    return jsonify(result)


@app.route('/api/config-viewer/list')
def config_viewer_api_list():
    """获取所有配置文件列表"""
    config_list = {
        'categories': []
    }

    for category, config in CONFIG_FILES.items():
        # 跳过 oracle_config，它将在前端合并到 oracle 中
        if category == 'oracle_config':
            continue

        category_info = {
            'name': category,
            'display_name': get_category_display_name(category),
            'files': []
        }

        for filename in config['files']:
            filepath = os.path.join(config['base_dir'], filename)
            file_info = {
                'filename': filename,
                'exists': os.path.exists(filepath),
                'path': filepath
            }

            if os.path.exists(filepath):
                file_stat = os.stat(filepath)
                file_info['size'] = file_stat.st_size
                file_info['modified'] = datetime.fromtimestamp(file_stat.st_mtime).isoformat()

            category_info['files'].append(file_info)

        config_list['categories'].append(category_info)

    return jsonify(config_list)


def get_category_display_name(category):
    """获取分类显示名称"""
    names = {
        'did': 'DID注册配置',
        'schema': 'Schema/Cred-Def配置',
        'contract': '智能合约配置',
        'oracle': 'Oracle服务配置',
        'oracle_config': 'Oracle服务配置'
    }
    return names.get(category, category)

# ==================== VC发行服务 API ====================

# VC发行Oracle配置
VC_ISSUANCE_ORACLE_URL = 'http://localhost:6000'

# ACA-Py配置
ISSUER_ADMIN_URL = 'http://localhost:8080'
HOLDER_ADMIN_URL = 'http://localhost:8081'
HOLDER_DID = 'YL2HDxkVL8qMrssaZbvtfH'
ISSUER_DID = 'DPvobytTtKvmyeRTJZYjsg'

# 链上查询配置
CHAIN_A_RPC_URL = 'http://localhost:8545'

# VC类型配置常量
VC_TYPE_NAMES = {
    'InspectionReport': '质检报告',
    'InsuranceContract': '保险合同',
    'CertificateOfOrigin': '原产地证明',
    'BillOfLadingCertificate': '提单证书'
}

VC_CRED_DEF_IDS = {
    'InspectionReport': 'DPvobytTtKvmyeRTJZYjsg:3:CL:62:InspectionReport_V9',
    'InsuranceContract': 'DPvobytTtKvmyeRTJZYjsg:3:CL:64:InsuranceContract_V9',
    'CertificateOfOrigin': 'DPvobytTtKvmyeRTJZYjsg:3:CL:66:CertificateOfOrigin_V9',
    'BillOfLadingCertificate': 'DPvobytTtKvmyeRTJZYjsg:3:CL:68:BillOfLadingCertificate_V9'
}

VC_CONTRACT_ADDRESSES = {
    'InspectionReport': '0xf5573AA77552858d70384FCAC615EeDb4e05Ba7B',
    'InsuranceContract': '0xC1e2E535D3979F868455A82D208EfABdC3174aa5',
    'CertificateOfOrigin': '0x8499286b6d3B9c4b9c15A8A855a8B4839026fD7C',
    'BillOfLadingCertificate': '0xA9a4074B2A92E63e4c7DC440E80ea1f76a28F701'
}

# VC类型配置（从vc_issuance_config.json读取）
VC_TYPES_CONFIG = '/home/manifold/cursor/cross-chain-new/VcIssureOracle/vc_issuance_config.json'

# 全局发行历史记录（简单内存存储）
issuance_history = []


def sync_vc_config_from_oracle():
    """从Oracle配置文件同步VC类型配置"""
    oracle_config_path = '/home/manifold/cursor/cross-chain-new/VcIssureOracle/vc_issuance_config.json'
    try:
        with open(oracle_config_path, 'r', encoding='utf-8') as f:
            oracle_config = json.load(f)

        # 同步cred_def_id和contract_address
        synced = False
        for vc_type, config in oracle_config.get('vc_types', {}).items():
            if vc_type in VC_CRED_DEF_IDS:
                old_id = VC_CRED_DEF_IDS[vc_type]
                new_id = config.get('cred_def_id')
                if old_id != new_id:
                    logger.info(f"更新 {vc_type} cred_def_id: {old_id} -> {new_id}")
                    VC_CRED_DEF_IDS[vc_type] = new_id
                    synced = True

            if vc_type in VC_CONTRACT_ADDRESSES:
                old_addr = VC_CONTRACT_ADDRESSES[vc_type]
                new_addr = config.get('contract_address')
                if old_addr != new_addr:
                    logger.info(f"更新 {vc_type} contract_address: {old_addr} -> {new_addr}")
                    VC_CONTRACT_ADDRESSES[vc_type] = new_addr
                    synced = True

        if synced:
            logger.info(f"VC配置同步完成，支持的VC类型: {list(VC_CRED_DEF_IDS.keys())}")
        return True
    except Exception as e:
        logger.error(f"VC配置同步失败: {e}")
        return False


# 启动时同步配置
sync_vc_config_from_oracle()


# ==================== Issuer-Holder连接管理 ====================

def check_issuer_holder_connection() -> bool:
    """检查Issuer和Holder之间是否有有效连接（DID匹配）"""
    try:
        # 获取Issuer的连接列表
        resp = requests.get(f"{ISSUER_ADMIN_URL}/connections", timeout=10)
        if resp.status_code != 200:
            return False

        data = resp.json()
        for conn in data.get('results', []):
            state = conn.get('state')
            their_label = conn.get('their_label', '')
            if state in ['active', 'response'] and 'Holder' in their_label:
                issuer_conn_id = conn.get('connection_id')
                issuer_their_did = conn.get('their_did')

                # 验证Holder端是否也有对应的连接（通过DID匹配）
                holder_resp = requests.get(f"{HOLDER_ADMIN_URL}/connections", timeout=10)
                if holder_resp.status_code == 200:
                    holder_data = holder_resp.json()
                    for holder_conn in holder_data.get('results', []):
                        holder_state = holder_conn.get('state')
                        holder_label = holder_conn.get('their_label', '')
                        holder_my_did = holder_conn.get('my_did')

                        # 检查DID是否匹配
                        if (holder_state in ['active', 'response'] and
                            'Issuer' in holder_label and
                            holder_my_did == issuer_their_did):
                            logger.info(f"发现有效连接 (DID匹配): Issuer={issuer_conn_id}, Holder={holder_conn.get('connection_id')}")
                            return True

        logger.info("未发现DID匹配的有效连接")
        return False
    except Exception as e:
        logger.error(f"连接检查失败: {e}")
        return False


def create_issuer_holder_connection() -> bool:
    """创建Issuer和Holder之间的新连接"""
    logger.info("正在创建Issuer-Holder连接...")

    try:
        # 1. Issuer创建邀请
        resp = requests.post(
            f"{ISSUER_ADMIN_URL}/connections/create-invitation",
            params={"alias": "oracle-holder", "auto_accept": "true"},
            timeout=30
        )

        if resp.status_code not in [200, 201]:
            logger.error(f"创建邀请失败: {resp.status_code}")
            return False

        data = resp.json()
        issuer_conn_id = data.get('connection_id')
        invitation = data.get('invitation')
        logger.info(f"Issuer创建邀请: {issuer_conn_id}")

        # 2. Holder接受邀请
        resp2 = requests.post(
            f"{HOLDER_ADMIN_URL}/connections/receive-invitation",
            params={"alias": "oracle-issuer", "auto_accept": "true"},
            json=invitation,
            timeout=30
        )

        if resp2.status_code not in [200, 201]:
            logger.error(f"Holder接受邀请失败: {resp2.status_code}")
            return False

        holder_data = resp2.json()
        holder_conn_id = holder_data.get('connection_id')
        logger.info(f"Holder接受邀请: {holder_conn_id}")

        # 3. 等待连接建立
        logger.info("等待连接建立...")
        time.sleep(5)

        # 4. 验证连接状态
        resp3 = requests.get(f"{ISSUER_ADMIN_URL}/connections/{issuer_conn_id}", timeout=10)
        if resp3.status_code == 200:
            conn_data = resp3.json()
            state = conn_data.get('state')
            logger.info(f"连接已建立 (状态: {state})")
            return True

        return False

    except Exception as e:
        logger.error(f"创建连接异常: {e}")
        return False


def cleanup_old_issuer_holder_connections():
    """只清除旧的Issuer-Holder连接，不创建新连接（让Oracle自己管理）

    这与测试脚本的行为一致：先清除旧连接，然后调用Oracle让Oracle自己创建连接。
    避免webapp和Oracle之间的连接管理竞态条件。
    """
    logger.info("清理旧的Issuer-Holder连接...")
    try:
        resp = requests.get(f"{ISSUER_ADMIN_URL}/connections", timeout=10)
        if resp.status_code != 200:
            logger.warning("无法获取Issuer连接列表")
            return

        connections = resp.json().get('results', [])
        holder_conns = [c for c in connections if 'Holder' in c.get('their_label', '')]

        for conn in holder_conns:
            conn_id = conn.get('connection_id')
            state = conn.get('state')
            logger.info(f"删除旧连接: {conn_id} ({state})")
            requests.delete(f"{ISSUER_ADMIN_URL}/connections/{conn_id}", timeout=10)

        logger.info(f"已清理 {len(holder_conns)} 个旧连接")
    except Exception as e:
        logger.warning(f"清理旧连接时出错: {e}")


def ensure_issuer_holder_connection() -> bool:
    """确保Issuer和Holder之间有有效连接，并清理旧连接（与测试脚本一致）"""
    logger.info("检查Issuer-Holder连接...")

    # 第一步：清理Issuer端所有到Holder的旧连接
    # 这样Oracle会被迫使用新创建的连接
    logger.info("清理旧连接...")
    try:
        resp = requests.get(f"{ISSUER_ADMIN_URL}/connections", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            holder_conns = []
            for conn in data.get('results', []):
                their_label = conn.get('their_label', '')
                if 'Holder' in their_label:
                    holder_conns.append(conn)

            # 删除所有到Holder的旧连接
            for conn in holder_conns:
                conn_id = conn.get('connection_id')
                state = conn.get('state')
                logger.info(f"删除旧连接: {conn_id} ({state})")
                requests.delete(f"{ISSUER_ADMIN_URL}/connections/{conn_id}", timeout=10)
    except Exception as e:
        logger.error(f"清理旧连接时出错: {e}")

    # 第二步：创建新连接
    logger.info("创建新连接...")
    if create_issuer_holder_connection():
        logger.info("连接创建成功")
        return True

    logger.error("连接创建失败")
    return False


def get_holder_vc_by_contract_name(contract_name):
    """从Holder ACA-Py获取指定contractName的VC（如果找不到则返回最新的VC）"""
    try:
        # 使用 start/count 参数获取所有凭证（默认最多 1000 条）
        response = requests.get(
            f"{HOLDER_ADMIN_URL}/credentials",
            params={"start": 0, "count": 1000},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])

            # 首先尝试通过contractName精确匹配
            for cred in results:
                attrs = cred.get('attrs', {})
                if attrs.get('contractName') == contract_name:
                    return {
                        'referent': cred.get('referent'),
                        'schema_id': cred.get('schema_id'),
                        'cred_def_id': cred.get('cred_def_id'),
                        'rev_reg_id': cred.get('rev_reg_id'),
                        'cred_rev_id': cred.get('cred_rev_id'),
                        'attrs': attrs
                    }

            # 如果没有找到匹配的，返回最新的VC（第一个就是最新的）
            if results:
                cred = results[0]
                attrs = cred.get('attrs', {})
                logger.info(f"未找到contractName匹配的VC，返回最新的VC: {attrs.get('contractName')}")
                return {
                    'referent': cred.get('referent'),
                    'schema_id': cred.get('schema_id'),
                    'cred_def_id': cred.get('cred_def_id'),
                    'rev_reg_id': cred.get('rev_reg_id'),
                    'cred_rev_id': cred.get('cred_rev_id'),
                    'attrs': attrs,
                    'fallback': True  # 标记这是fallback数据
                }

        return None
    except Exception as e:
        logger.error(f"从Holder获取VC失败: {e}")
        return None


def get_chain_vc_metadata(vc_hash, contract_address):
    """从合约获取VC元数据"""
    try:
        from web3 import Web3
        from web3.middleware import geth_poa_middleware

        w3 = Web3(Web3.HTTPProvider(CHAIN_A_RPC_URL))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        # ABI for vcMetadataList mapping (12字段 struct)
        abi = [{
            "inputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
            "name": "vcMetadataList",
            "outputs": [
                {"internalType": "bytes32", "name": "vcHash", "type": "bytes32"},
                {"internalType": "string", "name": "vcName", "type": "string"},
                {"internalType": "string", "name": "vcDescription", "type": "string"},
                {"internalType": "string", "name": "issuerEndpoint", "type": "string"},
                {"internalType": "string", "name": "issuerDID", "type": "string"},
                {"internalType": "string", "name": "holderEndpoint", "type": "string"},
                {"internalType": "string", "name": "holderDID", "type": "string"},
                {"internalType": "string", "name": "blockchainEndpoint", "type": "string"},
                {"internalType": "address", "name": "vcManagerAddress", "type": "address"},
                {"internalType": "string", "name": "blockchainType", "type": "string"},
                {"internalType": "uint256", "name": "expiryTime", "type": "uint256"},
                {"internalType": "bool", "name": "exists", "type": "bool"}
            ],
            "stateMutability": "view",
            "type": "function"
        }]

        contract = w3.eth.contract(address=contract_address, abi=abi)
        vc_hash_bytes = bytes.fromhex(vc_hash.replace('0x', ''))

        result = contract.functions.vcMetadataList(vc_hash_bytes).call()

        return {
            'vc_hash': '0x' + result[0].hex() if result[0] else vc_hash,
            'vc_name': result[1],
            'vc_description': result[2],
            'issuer_endpoint': result[3],
            'issuer_did': result[4],
            'holder_endpoint': result[5],
            'holder_did': result[6],
            'blockchain_endpoint': result[7],
            'vc_manager_address': result[8],
            'blockchain_type': result[9],
            'expiry_time': result[10]
        }
    except Exception as e:
        logger.error(f"从合约获取元数据失败: {e}")
        return None


def find_holder_vc_by_uuid(chain_uuid):
    """
    使用 UUID 精确匹配 Holder 中的 VC

    参考：test_vc_issuance_full_flow.py:verify_holder_storage()

    Args:
        chain_uuid: 链上 UUID（即 contractName）

    Returns:
        Tuple[holder_vc_data, match_result]
        - holder_vc_data: 匹配成功的 VC 数据，失败时返回 None
        - match_result: 匹配结果字典，包含匹配状态和调试信息
    """
    try:
        # 使用 start/count 参数获取所有凭证
        response = requests.get(
            f"{HOLDER_ADMIN_URL}/credentials",
            params={"start": 0, "count": 1000},
            timeout=30
        )

        if response.status_code != 200:
            return None, {
                'error': f'获取 Holder 凭证失败，HTTP {response.status_code}',
                'holder_count': 0
            }

        creds_data = response.json()
        results = creds_data.get('results', [])

        # 遍历查找 UUID 匹配的 VC
        for i, cred in enumerate(results):
            attrs = cred.get('attrs', {})
            holder_contract_name = attrs.get('contractName', '')

            # 精确匹配：contractName 就是 UUID
            if holder_contract_name == chain_uuid:
                holder_vc_data = {
                    'referent': cred.get('referent'),
                    'schema_id': cred.get('schema_id'),
                    'cred_def_id': cred.get('cred_def_id'),
                    'rev_reg_id': cred.get('rev_reg_id'),
                    'cred_rev_id': cred.get('cred_rev_id'),
                    'attributes': attrs,
                    'vc_hash': attrs.get('vc_hash')
                }

                return holder_vc_data, {
                    'matched_by': 'uuid_exact_match',
                    'holder_count': len(results)
                }

        # UUID 匹配失败
        return None, {
            'error': f'未在 Holder 中找到 UUID 匹配的 VC (共{len(results)}个)',
            'holder_count': len(results),
            'searched_uuid': chain_uuid
        }

    except Exception as e:
        logger.error(f"获取 Holder VC 失败：{e}")
        return None, {
            'error': f'获取 Holder 凭证异常：{str(e)}',
            'holder_count': 0
        }


def verify_holder_vc_hash(holder_vc_data, expected_vc_hash):
    """
    验证 Holder 凭证的 vc_hash 是否与预期一致

    Args:
        holder_vc_data: Holder 中的 VC 数据
        expected_vc_hash: 预期的 vc_hash（从链上获取）

    Returns:
        Tuple[是否匹配，验证消息]
    """
    if not holder_vc_data:
        return False, "未找到匹配的 Holder VC"

    holder_vc_hash = holder_vc_data.get('vc_hash')
    if holder_vc_hash and holder_vc_hash.lower() != expected_vc_hash.lower():
        return False, f"vc_hash 不匹配：Holder={holder_vc_hash}, 链上={expected_vc_hash}"

    return True, "vc_hash 验证通过"


def load_vc_config():
    """加载VC配置"""
    try:
        with open(VC_TYPES_CONFIG, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载VC配置失败: {e}")
        return {}


@app.route('/vc-issuance')
def vc_issuance_page():
    """VC发行服务页面"""
    return render_template('vc_issuance.html')


@app.route('/api/vc-issuance/status')
def vc_issuance_api_status():
    """获取VC发行Oracle状态"""
    try:
        # Oracle使用 /health 端点，不是 /status
        response = requests.get(f"{VC_ISSUANCE_ORACLE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return jsonify({'status': 'online' if data.get('status') == 'ok' else 'offline', 'data': data})
        return jsonify({'status': 'offline'})
    except Exception as e:
        logger.error(f"检查Oracle状态失败: {e}")
        return jsonify({'status': 'offline'})


@app.route('/api/vc-issuance/connection-status')
def vc_issuance_api_connection_status():
    """获取ACA-Py连接状态"""
    try:
        # 调用Oracle的health端点获取连接状态
        response = requests.get(f"{VC_ISSUANCE_ORACLE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                'success': True,
                'oracle_status': data.get('status', 'unknown'),
                'connections': data.get('connections', {})
            })
        return jsonify({'success': False, 'error': 'Oracle离线'})
    except Exception as e:
        logger.error(f"获取连接状态失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/vc-issuance/config')
def vc_issuance_api_config():
    """获取VC类型配置"""
    vc_config = load_vc_config()
    vc_types = vc_config.get('vc_types', {})

    result = []
    for vc_type, config in vc_types.items():
        result.append({
            'name': vc_type,
            'schema_name': config.get('schema_name'),
            'cred_def_id': config.get('cred_def_id'),
            'contract_address': config.get('contract_address'),
            'attributes': config.get('attributes', [])
        })

    return jsonify({'vc_types': result})


@app.route('/api/vc-issuance/vc-types-config')
def vc_issuance_api_vc_types_config():
    """获取VC类型配置（供前端动态加载cred_def_id和contract_address）"""
    sync_vc_config_from_oracle()  # 确保配置是最新的

    vc_types = {}
    for vc_type in VC_CRED_DEF_IDS.keys():
        vc_types[vc_type] = {
            'cred_def_id': VC_CRED_DEF_IDS.get(vc_type),
            'contract_address': VC_CONTRACT_ADDRESSES.get(vc_type)
        }

    return jsonify({
        'success': True,
        'vc_types': vc_types
    })


@app.route('/api/vc-issuance/issue', methods=['POST'])
def vc_issuance_api_issue():
    """发行 VC - 直接调用新 Oracle 服务 (http://localhost:6000/issue-vc)"""
    try:
        data = request.json
        vc_type = data.get('vc_type')
        attributes = data.get('attributes', {})

        if not vc_type or not attributes:
            return jsonify({
                'success': False,
                'error': '缺少必要参数',
                'error_type': 'validation_error'
            })

        # 同步最新配置
        sync_vc_config_from_oracle()

        # 验证VC类型
        if vc_type not in VC_CRED_DEF_IDS:
            return jsonify({
                'success': False,
                'error': f'不支持的VC类型: {vc_type}',
                'error_type': 'validation_error',
                'supported_types': list(VC_CRED_DEF_IDS.keys())
            })

        # 添加当前时间戳（如果未提供）
        if 'Date' in attributes and not attributes['Date']:
            attributes['Date'] = datetime.now().strftime('%Y-%m-%d')

        # 构建 Oracle API 请求
        oracle_request = {
            "vc_type": vc_type,
            "metadata": {
                "vcName": f"{VC_TYPE_NAMES.get(vc_type, vc_type)}-{attributes.get('contractName', 'UNKNOWN')}",
                "vcDescription": f"{VC_TYPE_NAMES.get(vc_type, vc_type)} VC",
                "expiryTime": int((datetime.now() + timedelta(days=365)).timestamp())
            },
            "attributes": attributes
        }

        # 直接调用新 Oracle 服务
        oracle_url = f'{VC_ISSUANCE_ORACLE_URL}/issue-vc'
        response = requests.post(oracle_url, json=oracle_request, timeout=180)
        result = response.json()

        if result.get('status') == 'success':
            vc_hash = result.get('vc_hash')
            vc_uuid = result.get('vc_uuid')
            tx_hash = result.get('tx_hash')
            cred_ex_id = result.get('cred_ex_id')
            contract_address = VC_CONTRACT_ADDRESSES.get(vc_type, '')

            # 构建返回结果（保持与原有格式兼容）
            response_data = {
                'success': True,
                'vc_type': vc_type,
                'holder_vc': {
                    'referent': None,  # 需要刷新获取
                    'schema_id': VC_CRED_DEF_IDS.get(vc_type, ''),
                    'cred_def_id': VC_CRED_DEF_IDS.get(vc_type, ''),
                    'rev_reg_id': None,
                    'cred_rev_id': None,
                    'attributes': attributes,
                    'vc_hash': vc_hash,
                    'vc_uuid': vc_uuid
                },
                'chain_data': {
                    'vc_hash': vc_hash,
                    'contract_address': contract_address,
                    'block_number': None,  # 后续从链上获取
                    'metadata': {
                        'vc_type': vc_type,
                        'vc_name': oracle_request['metadata']['vcName'],
                        'vc_description': oracle_request['metadata']['vcDescription'],
                        'issuer_endpoint': '',
                        'issuer_did': ISSUER_DID,
                        'holder_endpoint': '',
                        'holder_did': HOLDER_DID,
                        'blockchain_endpoint': CHAIN_A_RPC_URL,
                        'vc_manager_address': contract_address,
                        'blockchain_type': 'Hyperledger Besu',
                        'expiry_time': oracle_request['metadata']['expiryTime'],
                        'timestamp': None
                    }
                },
                'transaction': {
                    'tx_hash': tx_hash,
                    'gas_used': None,
                    'status': 'success'
                },
                'oracle_response': {
                    'request_id': result.get('request_id'),
                    'vc_uuid': vc_uuid,
                    'cred_ex_id': cred_ex_id
                },
                'timestamp': result.get('timestamp', datetime.now().isoformat())
            }

            # 添加到历史记录
            issuance_history.insert(0, response_data)
            if len(issuance_history) > 50:
                issuance_history.pop()

            return jsonify(response_data)
        else:
            # Oracle 返回失败状态
            error = result.get('error', '发行失败')
            error_type = result.get('error_type', 'issuance_error')

            return jsonify({
                'success': False,
                'error': error,
                'error_type': error_type,
                'vc_type': vc_type
            })

    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Oracle 服务请求超时（超过 180 秒）',
            'error_type': 'timeout_error'
        })
    except requests.exceptions.RequestException as e:
        logger.error(f"调用 Oracle 服务失败：{e}")
        return jsonify({
            'success': False,
            'error': f'调用 Oracle 服务失败：{str(e)}',
            'error_type': 'network_error'
        })
    except json.JSONDecodeError as e:
        logger.error(f"解析 Oracle 响应失败：{e}")
        return jsonify({
            'success': False,
            'error': f'解析 Oracle 响应失败：{str(e)}',
            'error_type': 'json_parse_error'
        })
    except Exception as e:
        logger.error(f"VC 发行失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': 'unknown_error'
        })




@app.route('/api/vc-issuance/refresh-data', methods=['POST'])
def vc_issuance_api_refresh_data():
    """
    刷新 VC 数据（使用链上 UUID 进行精确匹配 + vc_hash 双重验证）

    流程：
    1. 从链上合约获取 vcName，包含 UUID（格式："{original_vc_name} (UUID: {vc_uuid})"）
    2. 从 vcName 中提取 UUID
    3. 使用 UUID 精确匹配 Holder 中 VC 的 contractName 属性
    4. 验证 Holder VC 的 vc_hash 是否与链上一致

    返回格式：
    - 成功：包含 holder_vc, chain_metadata, chain_uuid, matched_by, verification
    - 失败：包含 success=False, error, error_step, debug_info
    """
    try:
        data = request.json
        vc_hash = data.get('vc_hash')
        contract_address = data.get('contract_address')
        issuance_timestamp = data.get('issuance_timestamp')  # 保留用于调试

        if not vc_hash or not contract_address:
            return jsonify({
                'success': False,
                'error': '缺少必要参数：vc_hash 和 contract_address',
                'error_step': 'parameter_validation',
                'debug_info': {'provided_params': list(data.keys()) if data else None}
            })

        logger.info(f"[刷新 VC 数据] vc_hash: {vc_hash}, contract: {contract_address}")

        # === 步骤 1: 从链上获取元数据（包含 vcName，其中包含 UUID）===
        chain_metadata = get_chain_vc_metadata(vc_hash, contract_address)

        if not chain_metadata:
            return jsonify({
                'success': False,
                'error': '无法从链上获取 VC 元数据',
                'error_step': 'chain_metadata_fetch',
                'debug_info': {
                    'vc_hash': vc_hash,
                    'contract_address': contract_address
                }
            })

        vc_name = chain_metadata.get('vc_name', '')

        # === 步骤 2: 从 vcName 中提取 UUID ===
        # 格式："{original_vc_name} (UUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)"
        import re
        uuid_match = re.search(r'UUID:\s*([a-f0-9\-]{36})', vc_name, re.IGNORECASE)

        if not uuid_match:
            return jsonify({
                'success': False,
                'error': f'无法从链上元数据中提取 UUID',
                'error_step': 'uuid_extraction',
                'debug_info': {
                    'vc_name': vc_name,
                    'vc_hash': vc_hash
                }
            })

        chain_uuid = uuid_match.group(1)
        logger.info(f"[刷新 VC 数据] 从链上提取到 UUID: {chain_uuid}")

        # === 步骤 3: 使用新辅助函数匹配 Holder 中的 VC ===
        holder_vc_data, match_result = find_holder_vc_by_uuid(chain_uuid)

        if not holder_vc_data:
            return jsonify({
                'success': False,
                'error': match_result.get('error', '未找到匹配的 Holder VC'),
                'error_step': 'holder_vc_match',
                'debug_info': {
                    'searched_uuid': chain_uuid,
                    'holder_count': match_result.get('holder_count', 0),
                    'vc_hash': vc_hash
                }
            })

        logger.info(f"[刷新 VC 数据] ✅ UUID 精确匹配成功！referent: {holder_vc_data.get('referent')}")

        # === 步骤 4: 验证 vc_hash ===
        hash_verified, hash_msg = verify_holder_vc_hash(holder_vc_data, vc_hash)

        if not hash_verified:
            return jsonify({
                'success': False,
                'error': hash_msg,
                'error_step': 'vc_hash_verification',
                'debug_info': {
                    'expected_hash': vc_hash,
                    'holder_hash': holder_vc_data.get('vc_hash'),
                    'chain_uuid': chain_uuid
                }
            })

        logger.info(f"[刷新 VC 数据] ✅ vc_hash 验证通过")

        # === 步骤 5: 返回成功结果 ===
        return jsonify({
            'success': True,
            'holder_vc': holder_vc_data,
            'chain_metadata': chain_metadata,
            'chain_uuid': chain_uuid,
            'matched_by': match_result.get('matched_by', 'uuid_exact_match'),
            'verification': {
                'uuid_match': True,
                'vc_hash_match': True
            },
            'debug_info': {
                'holder_count': match_result.get('holder_count', 0)
            }
        })

    except Exception as e:
        logger.error(f"刷新 VC 数据失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'error_step': 'unknown_error',
            'debug_info': {}
        })


@app.route('/api/vc-issuance/history')
def vc_issuance_api_history():
    """获取发行历史"""
    return jsonify({
        'success': True,
        'history': issuance_history[:20]  # 返回最近20条
    })


@app.route('/api/vc-issuance/holder-vcs')
def vc_issuance_api_holder_vcs():
    """获取Holder中的VC列表"""
    try:
        # 获取分页参数
        start = request.args.get('start', 0, type=int)
        count = request.args.get('count', 1000, type=int)

        # 获取排序参数
        sort_by_date = request.args.get('sort_by_date', None)
        descending = request.args.get('descending', 'true', type=str).lower() == 'true'

        # 获取日期范围参数
        start_date = request.args.get('start_date', None)
        end_date = request.args.get('end_date', None)

        # 构建查询参数
        params = {'start': start, 'count': count}
        if sort_by_date:
            params['sort_by_date'] = 'Date'
            params['descending'] = 'true' if descending else 'false'
        if start_date and end_date:
            params['start_date'] = start_date
            params['end_date'] = end_date

        response = requests.get(f"{VC_ISSUANCE_ORACLE_URL}/credentials", params=params, timeout=30)
        if response.status_code == 200:
            return jsonify(response.json())
        return jsonify({'success': False, 'error': '获取VC列表失败'})
    except Exception as e:
        logger.error(f"获取 Holder VC 列表失败：{e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/vc-issuance/credentials-count')
def vc_issuance_api_credentials_count():
    """获取 Holder 凭证总数（调用新 Oracle /credentials/count 端点）"""
    try:
        response = requests.get(f"{VC_ISSUANCE_ORACLE_URL}/credentials/count", timeout=10)
        if response.status_code == 200:
            return jsonify(response.json())
        return jsonify({'success': False, 'error': '获取凭证数量失败'})
    except Exception as e:
        logger.error(f"获取凭证数量失败：{e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/vc-issuance/verify/<vc_id>')
def vc_issuance_api_verify_vc(vc_id):
    """验证VC"""
    try:
        response = requests.post(
            f"{VC_ISSUANCE_ORACLE_URL}/verify",
            json={'vc_id': vc_id},
            timeout=30
        )
        if response.status_code == 200:
            return jsonify(response.json())
        return jsonify({'success': False, 'error': '验证失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== VC跨链传输 ====================

# 跨链传输Oracle配置

# VC管理器合约配置（Chain A）
VC_MANAGERS_CONFIG = {
    'InspectionReport': {
        'name': '质检报告VC管理器',
        'icon': '📋',
        'address': '0xf5573AA77552858d70384FCAC615EeDb4e05Ba7B'
    },
    'InsuranceContract': {
        'name': '保险合同VC管理器',
        'icon': '🛡️',
        'address': '0xC1e2E535D3979F868455A82D208EfABdC3174aa5'
    },
    'CertificateOfOrigin': {
        'name': '原产地证书VC管理器',
        'icon': '📜',
        'address': '0x8499286b6d3B9c4b9c15A8A855a8B4839026fD7C'
    },
    'BillOfLading': {
        'name': '提单VC管理器',
        'icon': '📦',
        'address': '0xA9a4074B2A92E63e4c7DC440E80ea1f76a28F701'
    }
}

# Chain B跨链桥合约配置
BRIDGE_B_CONFIG = {
    'name': 'VCCrossChainBridge',
    'address': '0x4675a1BD937363fe1E7b6fF2129F3f7f3ccB10Df'
}

# 链配置
CHAIN_CONFIG = {
    'chainA': {
        'name': 'Besu A',
        'rpc_url': 'http://localhost:8545'
    },
    'chainB': {
        'name': 'Besu B',
        'rpc_url': 'http://localhost:8546'
    }
}


@app.route('/vc-crosschain-transfer')
def vc_crosschain_transfer_page():
    """VC跨链传输页面"""
    return render_template('vc_crosschain_transfer.html')


@app.route('/api/crosschain/status')
def api_crosschain_status():
    """获取跨链传输服务状态"""
    status = {
        'vc_managers': VC_MANAGERS_CONFIG,
        'bridge_b': BRIDGE_B_CONFIG,
        'chains': CHAIN_CONFIG
    }

    # 检查 vc_crosschain_service 状态
    try:
        if vc_crosschain_service.config:
            status['vc_crosschain_service'] = {
                'status': 'online',
                'message': 'VC 跨链传输服务已初始化',
                'vc_managers_count': len(vc_crosschain_service.config.get('vc_managers', {}).get('chain_a', {}))
            }
        else:
            status['vc_crosschain_service'] = {'status': 'offline', 'error': '配置未加载'}
    except Exception as e:
        logger.error(f"检查 VC 跨链传输服务状态失败：{e}")
        status['vc_crosschain_service'] = {'status': 'offline', 'error': str(e)}


    return jsonify(status)


@app.route('/api/crosschain/vc-managers')
def api_crosschain_vc_managers():
    """获取VC管理器列表"""
    result = []
    for vc_type, config in VC_MANAGERS_CONFIG.items():
        result.append({
            'type': vc_type,
            'name': config['name'],
            'icon': config['icon'],
            'address': config['address']
        })
    return jsonify({'vc_managers': result})


@app.route('/api/crosschain/vc-hashes/<vc_manager_type>')
def api_crosschain_vc_hashes(vc_manager_type):
    """从Chain A VC管理器读取VC哈希列表"""
    try:
        if vc_manager_type not in VC_MANAGERS_CONFIG:
            return jsonify({'success': False, 'error': '无效的VC管理器类型'})

        manager_address = VC_MANAGERS_CONFIG[vc_manager_type]['address']

        # 使用Web3直接调用合约，添加POA中间件支持Besu IBFT
        from web3 import Web3
        from web3.middleware import geth_poa_middleware

        w3 = Web3(Web3.HTTPProvider(CHAIN_CONFIG['chainA']['rpc_url']))
        # 添加PoA中间件（Besu使用IBFT 2.0共识）
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        # 测试连接
        try:
            chain_id = w3.eth.chain_id
        except Exception as e:
            return jsonify({'success': False, 'error': f'无法连接到Chain A: {str(e)}'})

        # VC Manager ABI - 只需要getAllVCHashes和getVCMetadata方法
        vc_manager_abi = [
            {
                "inputs": [],
                "name": "getAllVCHashes",
                "outputs": [{"internalType": "bytes32[]", "name": "", "type": "bytes32[]"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "bytes32", "name": "_vcHash", "type": "bytes32"}],
                "name": "getVCMetadata",
                "outputs": [
                    {"internalType": "string", "name": "vcName", "type": "string"},
                    {"internalType": "string", "name": "vcDescription", "type": "string"},
                    {"internalType": "string", "name": "issuerEndpoint", "type": "string"},
                    {"internalType": "string", "name": "issuerDID", "type": "string"},
                    {"internalType": "string", "name": "holderEndpoint", "type": "string"},
                    {"internalType": "string", "name": "holderDID", "type": "string"},
                    {"internalType": "address", "name": "vcManagerAddress", "type": "address"},
                    {"internalType": "uint256", "name": "expiryTime", "type": "uint256"},
                    {"internalType": "bool", "name": "exists", "type": "bool"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        contract = w3.eth.contract(address=manager_address, abi=vc_manager_abi)

        # 获取所有VC哈希
        vc_hashes = contract.functions.getAllVCHashes().call()

        # 获取每个VC的元数据
        vc_list = []
        for vc_hash in vc_hashes:
            try:
                metadata = contract.functions.getVCMetadata(vc_hash).call()
                # metadata是一个元组，按照ABI顺序: (vcName, vcDescription, issuerEndpoint, issuerDID, holderEndpoint, holderDID, vcManagerAddress, expiryTime, exists)
                if metadata[8]:  # exists == True
                    vc_list.append({
                        'hash': vc_hash.hex() if hasattr(vc_hash, 'hex') else vc_hash,
                        'vcHash': '0x' + (metadata[0].hex() if hasattr(metadata[0], 'hex') else metadata[0]),
                        'vcDescription': metadata[1],
                        'issuerEndpoint': metadata[2],
                        'issuerDID': metadata[3],
                        'holderEndpoint': metadata[4],
                        'holderDID': metadata[5],
                        'vcManagerAddress': metadata[6],
                        'expiryTime': metadata[7],
                        'exists': metadata[8]
                    })
            except Exception as e:
                logger.warning(f"无法读取VC {vc_hash} 的元数据: {e}")
                continue

        return jsonify({
            'success': True,
            'vc_manager_type': vc_manager_type,
            'vc_manager_address': manager_address,
            'vc_list': vc_list
        })

    except Exception as e:
        logger.error(f"读取VC哈希列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/crosschain/vc-metadata/<vc_manager_type>/<vc_hash>')
def api_crosschain_vc_metadata(vc_manager_type, vc_hash):
    """获取指定 VC 的元数据"""
    try:
        if vc_manager_type not in VC_MANAGERS_CONFIG:
            return jsonify({'success': False, 'error': '无效的 VC 管理器类型'})

        manager_address = VC_MANAGERS_CONFIG[vc_manager_type]['address']

        from web3 import Web3
        from web3.middleware import geth_poa_middleware
        import json

        w3 = Web3(Web3.HTTPProvider(CHAIN_CONFIG['chainA']['rpc_url']))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        # 测试连接
        try:
            chain_id = w3.eth.chain_id
        except Exception as e:
            return jsonify({'success': False, 'error': f'无法连接到 Chain A: {str(e)}'})

        # 读取完整的 ABI 文件（包含 vcMetadataList 的 12 字段 struct）
        abi_map = {
            'InspectionReportVCManager': 'InspectionReportVCManager.json',
            'InsuranceContractVCManager': 'InsuranceContractVCManager.json',
            'CertificateOfOriginVCManager': 'CertificateOfOriginVCManager.json',
            'BillOfLadingVCManager': 'BillOfLadingVCManager.json'
        }
        
        # 根据 vc_manager_type 获取 ABI 文件名
        abi_file = None
        for key, filename in abi_map.items():
            if key in vc_manager_type or vc_manager_type in key:
                abi_file = f'/home/manifold/cursor/cross-chain-new/contracts/kept/contract_abis/{filename}'
                break
        
        if not abi_file:
            return jsonify({'success': False, 'error': f'未知的 VC 管理器类型：{vc_manager_type}'})

        try:
            with open(abi_file, 'r') as f:
                vc_manager_abi = json.load(f)['abi']
        except Exception as e:
            return jsonify({'success': False, 'error': f'无法加载 ABI 文件：{str(e)}'})

        contract = w3.eth.contract(address=manager_address, abi=vc_manager_abi)

        # 将 hex 字符串转换为 bytes32
        if isinstance(vc_hash, str) and vc_hash.startswith('0x'):
            vc_hash_bytes = Web3.to_bytes(hexstr=vc_hash)
        else:
            vc_hash_bytes = vc_hash

        # 使用 vcMetadataList mapping（public，不需要验证）
        metadata = contract.functions.vcMetadataList(vc_hash_bytes).call()

        return jsonify({
            'success': True,
            'metadata': {
                'vcHash': '0x' + (metadata[0].hex() if hasattr(metadata[0], 'hex') else metadata[0]),
                'vcName': metadata[1],
                'vcDescription': metadata[2],
                'issuerEndpoint': metadata[3],
                'issuerDID': metadata[4],
                'holderEndpoint': metadata[5],
                'holderDID': metadata[6],
                'blockchainEndpoint': metadata[7],
                'vcManagerAddress': metadata[8],
                'blockchainType': metadata[9],
                'expiryTime': str(metadata[10]),
                'exists': metadata[11]
            }
        })

    except Exception as e:
        logger.error(f"读取 VC 元数据失败：{e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/crosschain/transfer', methods=['POST'])
def api_crosschain_transfer():
    """执行跨链传输 - 直接使用 vc_crosschain_service"""
    try:
        data = request.json
        vc_manager_address = data.get('vc_manager_address')
        vc_manager_type = data.get('vc_manager_type')
        vc_hash = data.get('vc_hash')
        target_chain = data.get('target_chain', 'chain_b')
        metadata = data.get('metadata', {})

        if not vc_manager_address or not vc_hash:
            return jsonify({'success': False, 'error': '缺少必要参数'})

        # 根据 vc_manager_type 推断 vc_type
        vc_type_mapping = {
            'InspectionReportVCManager': 'InspectionReport',
            'InsuranceContractVCManager': 'InsuranceContract',
            'CertificateOfOriginVCManager': 'CertificateOfOrigin',
            'BillOfLadingVCManager': 'BillOfLadingCertificate'
        }

        vc_type = None
        for type_name, manager_name in vc_type_mapping.items():
            if vc_manager_type and (vc_manager_type == type_name or vc_manager_type == manager_name):
                vc_type = manager_name
                break

        if not vc_type:
            for type_name in vc_type_mapping.values():
                if vc_manager_type and type_name in vc_manager_type:
                    vc_type = type_name
                    break

        if not vc_type:
            vc_type = metadata.get('vc_type', 'InspectionReport')

        logger.info(f"发起跨链传输：vc_hash={vc_hash}, vc_type={vc_type}, target_chain={target_chain}")

        # 使用 vc_crosschain_service 直接发起跨链传输
        result = vc_crosschain_service.initiate_cross_chain_transfer(
            vc_hash=vc_hash,
            vc_type=vc_type,
            target_chain=target_chain
        )

        if result.get('success'):
            logger.info(f"跨链传输成功！tx_hash={result.get('tx_hash')}")
            return jsonify({
                'success': True,
                'target_chain': target_chain,
                'chain_a_tx_hash': result.get('tx_hash'),
                'block_number': result.get('block_number'),
                'gas_used': result.get('gas_used'),
                'caller_address': result.get('caller_address'),
                'timestamp': datetime.now().isoformat(),
                'message': 'VC 跨链传输成功，正在等待 Oracle 处理...'
            })
        else:
            error_msg = result.get('error', '传输失败')
            logger.error(f"跨链传输失败：{error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg,
                'current_balance_eth': result.get('current_balance_eth'),
                'required_balance_eth': result.get('required_balance_eth')
            }), 500

    except Exception as e:
        logger.error(f"跨链传输失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/crosschain/bridge-record/<vc_hash>')
def api_crosschain_bridge_record(vc_hash):
    """从Chain B跨链桥合约读取接收记录"""
    try:
        from web3 import Web3
        from web3.middleware import geth_poa_middleware

        w3 = Web3(Web3.HTTPProvider(CHAIN_CONFIG['chainB']['rpc_url']))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        # 测试连接
        try:
            chain_id = w3.eth.chain_id
        except Exception as e:
            return jsonify({'success': False, 'error': f'无法连接到Chain B: {str(e)}'})

        # 跨链桥合约ABI
        bridge_abi = [
            {
                "inputs": [{"internalType": "bytes32", "name": "_vcHash", "type": "bytes32"}],
                "name": "getReceiveRecord",
                "outputs": [
                    {"internalType": "string", "name": "vcName", "type": "string"},
                    {"internalType": "string", "name": "holderEndpoint", "type": "string"},
                    {"internalType": "string", "name": "holderDID", "type": "string"},
                    {"internalType": "string", "name": "sourceChain", "type": "string"},
                    {"internalType": "uint256", "name": "timestamp", "type": "uint256"}
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
                "name": "receiveRecords",
                "outputs": [
                    {"internalType": "string", "name": "vcName", "type": "string"},
                    {"internalType": "string", "name": "holderEndpoint", "type": "string"},
                    {"internalType": "string", "name": "holderDID", "type": "string"},
                    {"internalType": "string", "name": "sourceChain", "type": "string"},
                    {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
                    {"internalType": "bool", "name": "exists", "type": "bool"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        bridge_address = BRIDGE_B_CONFIG['address']
        contract = w3.eth.contract(address=bridge_address, abi=bridge_abi)

        # 将hex字符串转换为bytes32
        if isinstance(vc_hash, str) and vc_hash.startswith('0x'):
            vc_hash_bytes = Web3.to_bytes(hexstr=vc_hash)
        else:
            vc_hash_bytes = vc_hash

        # 先尝试使用receiveRecords映射检查是否存在
        try:
            record_data = contract.functions.receiveRecords(vc_hash_bytes).call()
            if record_data[5]:  # exists == True
                return jsonify({
                    'success': True,
                    'found': True,
                    'record': {
                        'vcName': record_data[0],
                        'holderEndpoint': record_data[1],
                        'holderDID': record_data[2],
                        'sourceChain': record_data[3],
                        'timestamp': record_data[4],
                        'exists': record_data[5]
                    }
                })
        except Exception as e:
            logger.warning(f"使用receiveRecords查询失败，尝试getReceiveRecord: {e}")

        # 尝试使用getReceiveRecord函数
        try:
            record = contract.functions.getReceiveRecord(vc_hash_bytes).call()
            # 如果timestamp > 0，说明存在记录
            if record[4] > 0:
                return jsonify({
                    'success': True,
                    'found': True,
                    'record': {
                        'vcName': record[0],
                        'holderEndpoint': record[1],
                        'holderDID': record[2],
                        'sourceChain': record[3],
                        'timestamp': record[4]
                    }
                })
        except Exception as e:
            logger.warning(f"使用getReceiveRecord查询失败: {e}")

        # 未找到记录
        return jsonify({
            'success': True,
            'found': False,
            'message': '链B暂未收到该VC记录'
        })

    except Exception as e:
        logger.error(f"读取链B桥接记录失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/crosschain/transfer-history')
def api_crosschain_transfer_history():
    """获取跨链传输历史记录"""
    # 简单实现，返回空列表或从Oracle获取
    # 简单实现，返回空列表
    # 未来可以从数据库或日志文件中读取历史传输记录
    return jsonify({'history': [], 'message': '跨链传输历史记录功能暂未实现'})


# ==================== VP 验证 API ====================

UUID_JSON_PATH = '/home/manifold/cursor/cross-chain-new/VcIssureOracle/logs/uuid.json'
VP_PREDICATE_CONFIG_PATH = '/home/manifold/cursor/cross-chain-new/oracle/vp_predicate_config.json'


@app.route('/vp-verification')
def vp_verification_page():
    """VP 验证前端页面"""
    return render_template('vp_verification.html')


@app.route('/api/vp-verification/latest-uuids', methods=['GET'])
def get_latest_uuids_api():
    """获取各 VC 类型最新的 vc_hash 列表"""
    try:
        vc_type_filter = request.args.get('vc_type', None)

        # 读取 uuid.json
        with open(UUID_JSON_PATH, 'r', encoding='utf-8') as f:
            uuid_data = json.load(f)

        # 将 sys.path 扩展到 oracle 目录
        import sys
        sys.path.insert(0, '/home/manifold/cursor/cross-chain-new/oracle')

        from test_predicate_with_uuid import get_latest_uuids

        result = get_latest_uuids(uuid_data, vc_type_filter)

        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        logger.error(f"获取最新 UUID 失败：{e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/vp-verification/holder-credentials/<vc_type>', methods=['GET'])
def get_holder_credentials_api(vc_type):
    """获取 Holder 指定 VC 类型的凭证列表"""
    try:
        # 加载配置
        with open(VP_PREDICATE_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)

        import sys
        sys.path.insert(0, '/home/manifold/cursor/cross-chain-new/oracle')

        from test_predicate_with_uuid import get_holder_credentials_for_vc_type

        credentials = get_holder_credentials_for_vc_type(vc_type, config)

        return jsonify({
            'success': True,
            'vc_type': vc_type,
            'count': len(credentials),
            'credentials': credentials
        })
    except Exception as e:
        logger.error(f"获取 Holder 凭证失败：{e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/vp-verification/config/<vc_type>', methods=['GET'])
def get_vp_config_api(vc_type):
    """获取 VC 类型的默认谓词配置"""
    try:
        # 加载配置
        with open(VP_PREDICATE_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)

        predicate_policies = config.get('predicate_policies', {})
        vc_config = config.get('vc_types', {}).get(vc_type, {})

        policy = predicate_policies.get(vc_type, {})

        return jsonify({
            'success': True,
            'vc_type': vc_type,
            'description': policy.get('description', ''),
            'attributes_to_reveal': policy.get('attributes_to_reveal', []),
            'predicates': policy.get('predicates', {}),
            'attribute_filters': policy.get('attribute_filters', {}),
            'all_attributes': vc_config.get('attributes', [])
        })
    except Exception as e:
        logger.error(f"获取配置失败：{e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/vp-verification/validate', methods=['POST'])
def validate_vp_api():
    """执行 VP 验证"""
    try:
        data = request.get_json()

        vc_type = data.get('vc_type')
        vc_hash = data.get('vc_hash')
        uuid = data.get('uuid')
        custom_predicates = data.get('predicates')
        custom_attribute_filters = data.get('attribute_filters')

        if not vc_type or not vc_hash or not uuid:
            return jsonify({
                'success': False,
                'error': '缺少必需参数：vc_type, vc_hash, uuid'
            })

        # 加载配置
        with open(VP_PREDICATE_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)

        oracle_verify_url = "http://localhost:7003"  # Oracle 服务基础 URL

        # 导入测试脚本中的函数
        import sys
        sys.path.insert(0, '/home/manifold/cursor/cross-chain-new/oracle')

        from test_predicate_with_uuid import execute_verification

        # 执行验证
        result = execute_verification(
            vc_type=vc_type,
            vc_hash=vc_hash,
            uuid=uuid,
            oracle_url=oracle_verify_url,
            config=config,
            custom_predicates=custom_predicates,
            custom_attribute_filters=custom_attribute_filters,
            skip_uuid_only=False,
            skip_full_verification=False
        )

        return jsonify(result)
    except Exception as e:
        logger.error(f"VP 验证失败：{e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


# ==================== Socket.IO 事件处理 ====================

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
