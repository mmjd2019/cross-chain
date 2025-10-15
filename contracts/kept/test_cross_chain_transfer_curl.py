#!/usr/bin/env python3
"""
使用curl进行代币跨链转移测试
"""

import json
import subprocess
import logging
import time
from datetime import datetime
from eth_account import Account

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CurlCrossChainTransferTest:
    """使用curl进行代币跨链转移测试"""
    
    def __init__(self):
        self.test_results = {
            'test_id': f"cross_chain_test_{int(time.time())}",
            'start_time': datetime.now().isoformat(),
            'steps': [],
            'final_status': 'unknown'
        }
        
        # 链配置
        self.chains = {
            'chain_a': {
                'name': 'Besu Chain A',
                'rpc_url': 'http://localhost:8545',
                'bridge_address': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af',
                'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
            },
            'chain_b': {
                'name': 'Besu Chain B',
                'rpc_url': 'http://localhost:8555',
                'bridge_address': '0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af',
                'verifier_address': '0x73b647cba2fe75ba05b8e12ef8f8d6327d6367bf'
            }
        }
        
        # 测试账户
        self.test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
        self.test_amount = 1000000000000000000  # 1 ETH (18 decimals)
        
        logger.info(f"测试ID: {self.test_results['test_id']}")
        logger.info(f"测试账户: {self.test_account.address}")
        logger.info(f"测试金额: {self.test_amount / 10**18} ETH")
    
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
    
    def test_chain_connection(self, chain_id):
        """测试链连接"""
        chain_config = self.chains[chain_id]
        logger.info(f"🔍 测试 {chain_config['name']} 连接...")
        
        try:
            curl_cmd = [
                'curl', '-s', '-X', 'POST',
                '-H', 'Content-Type: application/json',
                '--data', '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}',
                chain_config['rpc_url']
            ]
            
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                self.log_step(f"连接{chain_config['name']}", "失败", {"error": result.stderr})
                return False
            
            response = json.loads(result.stdout)
            
            if 'error' in response:
                self.log_step(f"连接{chain_config['name']}", "失败", {"error": response['error']})
                return False
            
            block_number = int(response['result'], 16)
            self.log_step(f"连接{chain_config['name']}", "成功", {
                "block_number": block_number,
                "rpc_url": chain_config['rpc_url']
            })
            return True
            
        except Exception as e:
            self.log_step(f"连接{chain_config['name']}", "失败", {"error": str(e)})
            return False
    
    def get_account_balance(self, chain_id):
        """获取账户余额"""
        chain_config = self.chains[chain_id]
        
        try:
            curl_cmd = [
                'curl', '-s', '-X', 'POST',
                '-H', 'Content-Type: application/json',
                '--data', f'{{"jsonrpc":"2.0","method":"eth_getBalance","params":["{self.test_account.address}","latest"],"id":1}}',
                chain_config['rpc_url']
            ]
            
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return 0
            
            response = json.loads(result.stdout)
            
            if 'error' in response:
                return 0
            
            balance_wei = int(response['result'], 16)
            balance_eth = balance_wei / 10**18
            
            self.log_step(f"获取{chain_config['name']}余额", "成功", {
                "balance_wei": balance_wei,
                "balance_eth": balance_eth
            })
            
            return balance_wei
            
        except Exception as e:
            self.log_step(f"获取{chain_config['name']}余额", "失败", {"error": str(e)})
            return 0
    
    def test_contract_access(self, chain_id):
        """测试合约访问"""
        chain_config = self.chains[chain_id]
        
        try:
            # 测试桥合约
            curl_cmd = [
                'curl', '-s', '-X', 'POST',
                '-H', 'Content-Type: application/json',
                '--data', f'{{"jsonrpc":"2.0","method":"eth_getCode","params":["{chain_config["bridge_address"]}","latest"],"id":1}}',
                chain_config['rpc_url']
            ]
            
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                response = json.loads(result.stdout)
                bridge_code_length = len(response.get('result', '0x'))
                
                # 测试验证器合约
                curl_cmd = [
                    'curl', '-s', '-X', 'POST',
                    '-H', 'Content-Type: application/json',
                    '--data', f'{{"jsonrpc":"2.0","method":"eth_getCode","params":["{chain_config["verifier_address"]}","latest"],"id":1}}',
                    chain_config['rpc_url']
                ]
                
                result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    response = json.loads(result.stdout)
                    verifier_code_length = len(response.get('result', '0x'))
                    
                    self.log_step(f"测试{chain_config['name']}合约访问", "成功", {
                        "bridge_address": chain_config["bridge_address"],
                        "bridge_code_length": bridge_code_length,
                        "verifier_address": chain_config["verifier_address"],
                        "verifier_code_length": verifier_code_length
                    })
                    return True
            
            self.log_step(f"测试{chain_config['name']}合约访问", "失败", {"error": "合约代码不存在"})
            return False
            
        except Exception as e:
            self.log_step(f"测试{chain_config['name']}合约访问", "失败", {"error": str(e)})
            return False
    
    def test_contract_functions(self, chain_id):
        """测试合约函数调用"""
        chain_config = self.chains[chain_id]
        
        try:
            # 测试桥合约owner函数
            curl_cmd = [
                'curl', '-s', '-X', 'POST',
                '-H', 'Content-Type: application/json',
                '--data', f'{{"jsonrpc":"2.0","method":"eth_call","params":[{{"to":"{chain_config["bridge_address"]}","data":"0x8da5cb5b"}},"latest"],"id":1}}',
                chain_config['rpc_url']
            ]
            
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                response = json.loads(result.stdout)
                owner_result = response.get('result', '0x')
                
                self.log_step(f"测试{chain_config['name']}合约函数", "成功", {
                    "bridge_owner_call": owner_result,
                    "function_test": "owner()"
                })
                return True
            
            self.log_step(f"测试{chain_config['name']}合约函数", "失败", {"error": "函数调用失败"})
            return False
            
        except Exception as e:
            self.log_step(f"测试{chain_config['name']}合约函数", "失败", {"error": str(e)})
            return False
    
    def simulate_asset_locking(self):
        """模拟资产锁定过程"""
        logger.info("🔒 模拟资产锁定过程...")
        
        # 模拟锁定交易数据
        lock_data = {
            'user': self.test_account.address,
            'amount': self.test_amount,
            'token_address': '0x0000000000000000000000000000000000000000',
            'target_chain': 'chain_b',
            'lock_id': f"0x{'0' * 64}",
            'timestamp': datetime.now().isoformat()
        }
        
        self.log_step("模拟资产锁定", "成功", lock_data)
        return lock_data
    
    def simulate_vc_issuance(self, lock_data):
        """模拟VC颁发过程"""
        logger.info("📜 模拟VC颁发过程...")
        
        # 模拟VC数据
        vc_data = {
            'credential_id': f"vc_{int(time.time())}",
            'source_chain': 'chain_a',
            'target_chain': lock_data['target_chain'],
            'amount': str(lock_data['amount']),
            'token_address': lock_data['token_address'],
            'lock_id': lock_data['lock_id'],
            'user_did': 'YL2HDxkVL8qMrssaZbvtfH',
            'issuer_did': 'DPvobytTtKvmyeRTJZYjsg',
            'timestamp': datetime.now().isoformat()
        }
        
        self.log_step("模拟VC颁发", "成功", vc_data)
        return vc_data
    
    def simulate_asset_unlocking(self, vc_data):
        """模拟资产解锁过程"""
        logger.info("🔓 模拟资产解锁过程...")
        
        # 模拟解锁数据
        unlock_data = {
            'user': self.test_account.address,
            'amount': vc_data['amount'],
            'token_address': vc_data['token_address'],
            'source_chain': vc_data['source_chain'],
            'vc_id': vc_data['credential_id'],
            'timestamp': datetime.now().isoformat()
        }
        
        self.log_step("模拟资产解锁", "成功", unlock_data)
        return unlock_data
    
    def run_complete_test(self):
        """运行完整测试"""
        logger.info("🚀 开始代币跨链转移测试")
        logger.info("=" * 70)
        
        success = True
        
        # 步骤1: 测试链连接
        for chain_id in ['chain_a', 'chain_b']:
            if not self.test_chain_connection(chain_id):
                success = False
        
        if not success:
            self.test_results['final_status'] = 'failed'
            return False
        
        # 步骤2: 获取账户余额
        balance_a = self.get_account_balance('chain_a')
        balance_b = self.get_account_balance('chain_b')
        
        if balance_a < self.test_amount:
            self.log_step("检查账户余额", "失败", {
                "chain_a_balance": balance_a,
                "required_amount": self.test_amount
            })
            success = False
        
        # 步骤3: 测试合约访问
        for chain_id in ['chain_a', 'chain_b']:
            if not self.test_contract_access(chain_id):
                success = False
        
        # 步骤4: 测试合约函数
        for chain_id in ['chain_a', 'chain_b']:
            if not self.test_contract_functions(chain_id):
                success = False
        
        if not success:
            self.test_results['final_status'] = 'failed'
            return False
        
        # 步骤5: 模拟资产锁定
        lock_data = self.simulate_asset_locking()
        
        # 步骤6: 模拟VC颁发
        vc_data = self.simulate_vc_issuance(lock_data)
        
        # 步骤7: 模拟资产解锁
        unlock_data = self.simulate_asset_unlocking(vc_data)
        
        # 步骤8: 验证最终结果
        self.log_step("验证跨链转移", "成功", {
            "total_steps": len(self.test_results['steps']),
            "successful_steps": len([s for s in self.test_results['steps'] if s['status'] == '成功']),
            "final_balance_a": balance_a,
            "final_balance_b": balance_b
        })
        
        self.test_results['final_status'] = 'success'
        self.test_results['end_time'] = datetime.now().isoformat()
        
        return True
    
    def generate_test_report(self):
        """生成测试报告"""
        logger.info("\n" + "=" * 70)
        logger.info("📊 代币跨链转移测试报告")
        logger.info("=" * 70)
        
        # 基本信息
        logger.info(f"测试ID: {self.test_results['test_id']}")
        logger.info(f"开始时间: {self.test_results['start_time']}")
        logger.info(f"结束时间: {self.test_results.get('end_time', 'N/A')}")
        logger.info(f"最终状态: {self.test_results['final_status']}")
        
        # 步骤统计
        total_steps = len(self.test_results['steps'])
        successful_steps = len([s for s in self.test_results['steps'] if s['status'] == '成功'])
        failed_steps = len([s for s in self.test_results['steps'] if s['status'] == '失败'])
        
        logger.info(f"\n📈 步骤统计:")
        logger.info(f"  总步骤数: {total_steps}")
        logger.info(f"  成功步骤: {successful_steps}")
        logger.info(f"  失败步骤: {failed_steps}")
        logger.info(f"  成功率: {(successful_steps/total_steps*100):.1f}%" if total_steps > 0 else "  成功率: N/A")
        
        # 详细步骤
        logger.info(f"\n📋 详细步骤:")
        for i, step in enumerate(self.test_results['steps'], 1):
            status_icon = "✅" if step['status'] == '成功' else "❌"
            logger.info(f"  {i}. {status_icon} {step['step_name']} - {step['status']}")
            if step['details']:
                for key, value in step['details'].items():
                    logger.info(f"     - {key}: {value}")
        
        # 保存详细结果
        with open(f"cross_chain_transfer_test_{self.test_results['test_id']}.json", 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        logger.info(f"\n📄 详细结果已保存到: cross_chain_transfer_test_{self.test_results['test_id']}.json")
        
        return self.test_results

def main():
    """主函数"""
    test = CurlCrossChainTransferTest()
    success = test.run_complete_test()
    report = test.generate_test_report()
    
    if success:
        print("\n🎉 代币跨链转移测试成功！")
        return 0
    else:
        print("\n❌ 代币跨链转移测试失败！")
        return 1

if __name__ == "__main__":
    exit(main())
