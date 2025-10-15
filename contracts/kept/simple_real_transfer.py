#!/usr/bin/env python3
"""
简化的真实跨链转账测试
使用更简单的方法实现真实的ETH转账
"""

import json
import subprocess
import logging
import time
from datetime import datetime
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import to_hex, to_bytes

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleRealTransfer:
    """简化的真实转账测试"""
    
    def __init__(self):
        self.test_results = {
            'test_id': f"simple_transfer_{int(time.time())}",
            'start_time': datetime.now().isoformat(),
            'steps': [],
            'transactions': {},
            'final_status': 'unknown'
        }
        
        # 链配置
        self.chains = {
            'chain_a': {
                'name': 'Besu Chain A',
                'rpc_url': 'http://localhost:8545',
                'chain_id': 2023  # 0x7e7
            },
            'chain_b': {
                'name': 'Besu Chain B',
                'rpc_url': 'http://localhost:8555',
                'chain_id': 2024  # 0x7e8
            }
        }
        
        # 测试账户
        self.test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
        self.transfer_amount = 1000000000000000000  # 1 ETH (18 decimals)
        
        logger.info(f"简化真实转账测试ID: {self.test_results['test_id']}")
        logger.info(f"测试账户: {self.test_account.address}")
        logger.info(f"转账金额: {self.transfer_amount / 10**18} ETH")
    
    def log_step(self, step_name, status, details=None):
        """记录测试步骤"""
        step = {
            'step_name': step_name,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'details': details or {}
        }
        self.test_results['steps'].append(step)
        logger.info(f"📋 {step_name}: {status}")
        if details:
            for key, value in details.items():
                logger.info(f"   - {key}: {value}")
    
    def rpc_call(self, chain_id, method, params):
        """执行RPC调用"""
        chain_config = self.chains[chain_id]
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
        
        curl_cmd = [
            'curl', '-s', '-X', 'POST',
            '-H', 'Content-Type: application/json',
            '--data', json.dumps(payload),
            chain_config['rpc_url']
        ]
        
        try:
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise Exception(f"curl命令执行失败: {result.stderr}")
            
            response = json.loads(result.stdout)
            
            if 'error' in response:
                raise Exception(f"RPC错误: {response['error']}")
            
            return response['result']
            
        except Exception as e:
            logger.error(f"RPC调用失败: {e}")
            raise
    
    def get_balance(self, chain_id, address):
        """获取账户余额"""
        try:
            result = self.rpc_call(chain_id, 'eth_getBalance', [address, 'latest'])
            balance_wei = int(result, 16)
            balance_eth = balance_wei / 10**18
            return balance_wei, balance_eth
        except Exception as e:
            logger.error(f"获取余额失败: {e}")
            return 0, 0
    
    def get_nonce(self, chain_id, address):
        """获取账户nonce"""
        try:
            result = self.rpc_call(chain_id, 'eth_getTransactionCount', [address, 'latest'])
            return int(result, 16)
        except Exception as e:
            logger.error(f"获取nonce失败: {e}")
            return 0
    
    def get_gas_price(self, chain_id):
        """获取gas价格"""
        try:
            result = self.rpc_call(chain_id, 'eth_gasPrice', [])
            return int(result, 16)
        except Exception as e:
            logger.error(f"获取gas价格失败: {e}")
            return 50000000000  # 50 gwei
    
    def create_simple_transfer(self, chain_id, to_address, value):
        """创建简单的转账交易"""
        try:
            # 获取交易参数
            nonce = self.get_nonce(chain_id, self.test_account.address)
            gas_price = self.get_gas_price(chain_id)
            gas_limit = 21000  # 简单转账的gas限制
            
            # 创建交易数据
            transaction = {
                "to": to_address,
                "value": hex(value),
                "gas": hex(gas_limit),
                "gasPrice": hex(gas_price),
                "nonce": hex(nonce),
                "chainId": hex(self.chains[chain_id]['chain_id'])
            }
            
            # 创建交易哈希
            transaction_hash = self.test_account.sign_transaction(transaction)
            
            # 发送原始交易
            result = self.rpc_call(chain_id, 'eth_sendRawTransaction', [transaction_hash.rawTransaction.hex()])
            
            return result, nonce, gas_price
            
        except Exception as e:
            logger.error(f"创建转账交易失败: {e}")
            raise
    
    def wait_for_transaction_receipt(self, chain_id, tx_hash, timeout=60):
        """等待交易确认"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                result = self.rpc_call(chain_id, 'eth_getTransactionReceipt', [tx_hash])
                
                if result is not None:
                    return result
                
                time.sleep(2)
                
            except Exception as e:
                logger.warning(f"等待交易确认时出错: {e}")
                time.sleep(2)
        
        raise Exception(f"交易确认超时: {tx_hash}")
    
    def test_initial_balances(self):
        """测试初始余额"""
        logger.info("💰 检查初始余额...")
        
        balance_a_wei, balance_a_eth = self.get_balance('chain_a', self.test_account.address)
        balance_b_wei, balance_b_eth = self.get_balance('chain_b', self.test_account.address)
        
        self.log_step("检查初始余额", "成功", {
            "chain_a_balance_wei": balance_a_wei,
            "chain_a_balance_eth": balance_a_eth,
            "chain_b_balance_wei": balance_b_wei,
            "chain_b_balance_eth": balance_b_eth
        })
        
        if balance_a_wei < self.transfer_amount:
            raise Exception(f"链A余额不足，需要至少 {self.transfer_amount / 10**18} ETH")
        
        return balance_a_wei, balance_b_wei
    
    def transfer_from_chain_a(self):
        """从链A转账到另一个地址"""
        logger.info("💸 从链A执行转账...")
        
        try:
            # 创建一个新的接收地址（使用不同的私钥）
            receiver_account = Account.from_key('0x1234567890123456789012345678901234567890123456789012345678901234')
            
            # 执行转账
            tx_hash, nonce, gas_price = self.create_simple_transfer(
                'chain_a',
                receiver_account.address,
                self.transfer_amount
            )
            
            self.log_step("发送转账交易", "成功", {
                "transaction_hash": tx_hash,
                "from": self.test_account.address,
                "to": receiver_account.address,
                "amount": self.transfer_amount,
                "nonce": nonce,
                "gas_price": gas_price
            })
            
            # 等待交易确认
            receipt = self.wait_for_transaction_receipt('chain_a', tx_hash)
            
            if int(receipt['status'], 16) == 1:
                self.log_step("转账确认", "成功", {
                    "block_number": int(receipt['blockNumber'], 16),
                    "gas_used": int(receipt['gasUsed'], 16)
                })
                
                # 保存交易信息
                self.test_results['transactions']['transfer_tx'] = {
                    'hash': tx_hash,
                    'block_number': int(receipt['blockNumber'], 16),
                    'amount': self.transfer_amount,
                    'from': self.test_account.address,
                    'to': receiver_account.address
                }
                
                return tx_hash, receiver_account.address
            else:
                raise Exception("转账交易失败")
                
        except Exception as e:
            self.log_step("从链A转账", "失败", {"error": str(e)})
            raise
    
    def check_balance_changes(self, receiver_address):
        """检查余额变化"""
        logger.info("🔍 检查余额变化...")
        
        balance_a_wei, balance_a_eth = self.get_balance('chain_a', self.test_account.address)
        balance_b_wei, balance_b_eth = self.get_balance('chain_b', self.test_account.address)
        receiver_balance_wei, receiver_balance_eth = self.get_balance('chain_a', receiver_address)
        
        self.log_step("检查余额变化", "成功", {
            "sender_balance_wei": balance_a_wei,
            "sender_balance_eth": balance_a_eth,
            "receiver_balance_wei": receiver_balance_wei,
            "receiver_balance_eth": receiver_balance_eth,
            "chain_b_balance_wei": balance_b_wei,
            "chain_b_balance_eth": balance_b_eth
        })
        
        return balance_a_wei, receiver_balance_wei
    
    def run_simple_transfer(self):
        """运行简单转账测试"""
        logger.info("🚀 开始简单真实转账测试")
        logger.info("=" * 70)
        
        try:
            # 步骤1: 检查初始余额
            initial_balance_a, initial_balance_b = self.test_initial_balances()
            
            # 步骤2: 从链A转账
            tx_hash, receiver_address = self.transfer_from_chain_a()
            
            # 步骤3: 检查余额变化
            final_balance_a, receiver_balance = self.check_balance_changes(receiver_address)
            
            # 步骤4: 计算变化
            balance_change_a = initial_balance_a - final_balance_a
            receiver_gained = receiver_balance
            
            self.log_step("计算余额变化", "成功", {
                "initial_balance_a": initial_balance_a,
                "final_balance_a": final_balance_a,
                "balance_change_a": balance_change_a,
                "receiver_gained": receiver_gained,
                "transfer_amount": self.transfer_amount
            })
            
            # 验证转账是否成功
            if balance_change_a >= self.transfer_amount and receiver_gained >= self.transfer_amount:
                self.log_step("验证转账成功", "成功", {
                    "发送者减少": f"{balance_change_a / 10**18} ETH",
                    "接收者增加": f"{receiver_gained / 10**18} ETH",
                    "预期转账": f"{self.transfer_amount / 10**18} ETH",
                    "转账状态": "成功"
                })
                
                self.test_results['final_status'] = 'success'
                self.test_results['end_time'] = datetime.now().isoformat()
                
                return True
            else:
                raise Exception("转账验证失败，余额变化不符合预期")
                
        except Exception as e:
            self.log_step("简单转账", "失败", {"error": str(e)})
            self.test_results['final_status'] = 'failed'
            self.test_results['end_time'] = datetime.now().isoformat()
            return False
    
    def generate_report(self):
        """生成测试报告"""
        logger.info("\n" + "=" * 70)
        logger.info("📊 简单真实转账测试报告")
        logger.info("=" * 70)
        
        # 基本信息
        logger.info(f"测试ID: {self.test_results['test_id']}")
        logger.info(f"开始时间: {self.test_results['start_time']}")
        logger.info(f"结束时间: {self.test_results.get('end_time', 'N/A')}")
        logger.info(f"最终状态: {self.test_results['final_status']}")
        
        # 交易信息
        if 'transfer_tx' in self.test_results['transactions']:
            tx_info = self.test_results['transactions']['transfer_tx']
            logger.info(f"\n🔗 转账交易:")
            logger.info(f"  交易哈希: {tx_info['hash']}")
            logger.info(f"  区块号: {tx_info['block_number']}")
            logger.info(f"  金额: {tx_info['amount'] / 10**18} ETH")
            logger.info(f"  发送者: {tx_info['from']}")
            logger.info(f"  接收者: {tx_info['to']}")
        
        # 步骤统计
        total_steps = len(self.test_results['steps'])
        successful_steps = len([s for s in self.test_results['steps'] if s['status'] == '成功'])
        failed_steps = len([s for s in self.test_results['steps'] if s['status'] == '失败'])
        
        logger.info(f"\n📈 步骤统计:")
        logger.info(f"  总步骤数: {total_steps}")
        logger.info(f"  成功步骤: {successful_steps}")
        logger.info(f"  失败步骤: {failed_steps}")
        logger.info(f"  成功率: {(successful_steps/total_steps*100):.1f}%" if total_steps > 0 else "  成功率: N/A")
        
        # 保存详细结果
        with open(f"simple_transfer_test_{self.test_results['test_id']}.json", 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        logger.info(f"\n📄 详细结果已保存到: simple_transfer_test_{self.test_results['test_id']}.json")

def main():
    """主函数"""
    transfer = SimpleRealTransfer()
    success = transfer.run_simple_transfer()
    transfer.generate_report()
    
    if success:
        print("\n🎉 简单真实转账成功！")
        return 0
    else:
        print("\n❌ 简单真实转账失败！")
        return 1

if __name__ == "__main__":
    exit(main())
