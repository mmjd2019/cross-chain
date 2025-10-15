#!/usr/bin/env python3
"""
测试BesuA和BesuB网络联通性及已部署智能合约访问
"""

import json
import logging
import time
from web3 import Web3
from eth_account import Account

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BesuConnectivityTest:
    """Besu网络联通性和合约访问测试"""
    
    def __init__(self):
        self.test_results = {
            'chain_a': {},
            'chain_b': {},
            'contracts': {},
            'overall_status': 'unknown'
        }
        
        # 链配置
        self.chains = {
            'chain_a': {
                'name': 'Besu Chain A',
                'rpc_url': 'http://localhost:8545',
                'chain_id': 1337
            },
            'chain_b': {
                'name': 'Besu Chain B', 
                'rpc_url': 'http://localhost:8555',
                'chain_id': 1338
            }
        }
        
        # 测试账户
        self.test_account = Account.from_key('0x076c1c44551a9505f179fa29df6bc456276ffb60e98312e2360f923b42dfb52a')
        
        # 合约地址（从deployment.json加载）
        self.contract_addresses = self.load_contract_addresses()
    
    def load_contract_addresses(self):
        """加载合约地址"""
        try:
            with open('deployment.json', 'r') as f:
                deployment_data = json.load(f)
            logger.info("✅ 合约地址加载成功")
            return deployment_data
        except Exception as e:
            logger.error(f"❌ 合约地址加载失败: {e}")
            return {}
    
    def test_chain_connectivity(self, chain_name, chain_config):
        """测试单链联通性"""
        logger.info(f"🔍 测试 {chain_name} 联通性...")
        
        try:
            # 创建Web3连接
            w3 = Web3(Web3.HTTPProvider(chain_config['rpc_url']))
            
            # 测试连接
            if not w3.is_connected():
                logger.error(f"❌ {chain_name} 连接失败")
                return False
            
            # 获取链信息
            block_number = w3.eth.block_number
            chain_id = w3.eth.chain_id
            gas_price = w3.eth.gas_price
            accounts = w3.eth.accounts
            
            # 检查账户余额
            test_balance = w3.eth.get_balance(self.test_account.address)
            
            result = {
                'connected': True,
                'block_number': block_number,
                'chain_id': chain_id,
                'gas_price': gas_price,
                'accounts_count': len(accounts),
                'test_account_balance': w3.from_wei(test_balance, 'ether'),
                'rpc_url': chain_config['rpc_url']
            }
            
            logger.info(f"✅ {chain_name} 连接成功")
            logger.info(f"   - 当前区块: {block_number}")
            logger.info(f"   - 链ID: {chain_id}")
            logger.info(f"   - Gas价格: {w3.from_wei(gas_price, 'gwei')} Gwei")
            logger.info(f"   - 账户数量: {len(accounts)}")
            logger.info(f"   - 测试账户余额: {w3.from_wei(test_balance, 'ether')} ETH")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ {chain_name} 连接测试失败: {e}")
            return False
    
    def test_contract_access(self, chain_name, w3, contract_name, contract_address, abi_file):
        """测试合约访问"""
        logger.info(f"🔍 测试 {chain_name} 上的 {contract_name} 合约访问...")
        
        try:
            # 加载合约ABI
            with open(abi_file, 'r') as f:
                abi = json.load(f)
            
            # 创建合约实例
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=abi
            )
            
            # 测试合约调用
            test_results = {}
            
            # 测试基本函数
            try:
                if hasattr(contract.functions, 'owner'):
                    owner = contract.functions.owner().call()
                    test_results['owner'] = owner
                    logger.info(f"   - 合约所有者: {owner}")
            except Exception as e:
                logger.warning(f"   - 无法获取owner: {e}")
            
            try:
                if hasattr(contract.functions, 'chainId'):
                    chain_id = contract.functions.chainId().call()
                    test_results['chain_id'] = chain_id
                    logger.info(f"   - 合约链ID: {chain_id}")
            except Exception as e:
                logger.warning(f"   - 无法获取chainId: {e}")
            
            try:
                if hasattr(contract.functions, 'isVerified'):
                    # 测试DID验证功能
                    is_verified = contract.functions.isVerified(self.test_account.address).call()
                    test_results['is_verified'] = is_verified
                    logger.info(f"   - 测试账户验证状态: {is_verified}")
            except Exception as e:
                logger.warning(f"   - 无法测试isVerified: {e}")
            
            # 测试事件
            try:
                # 获取最近的合约事件
                latest_block = w3.eth.block_number
                from_block = max(latest_block - 100, 0)
                
                # 尝试获取事件（如果有的话）
                if hasattr(contract.events, 'CrossChainProofRecorded'):
                    events = contract.events.CrossChainProofRecorded().get_logs(
                        fromBlock=from_block,
                        toBlock=latest_block
                    )
                    test_results['events_count'] = len(events)
                    logger.info(f"   - 最近事件数量: {len(events)}")
            except Exception as e:
                logger.warning(f"   - 无法获取事件: {e}")
            
            result = {
                'accessible': True,
                'address': contract_address,
                'test_results': test_results
            }
            
            logger.info(f"✅ {contract_name} 合约访问成功")
            return result
            
        except Exception as e:
            logger.error(f"❌ {contract_name} 合约访问失败: {e}")
            return {
                'accessible': False,
                'address': contract_address,
                'error': str(e)
            }
    
    def test_contract_interaction(self, chain_name, w3, contract_name, contract_address, abi_file):
        """测试合约交互（只读操作）"""
        logger.info(f"🔍 测试 {chain_name} 上的 {contract_name} 合约交互...")
        
        try:
            # 加载合约ABI
            with open(abi_file, 'r') as f:
                abi = json.load(f)
            
            # 创建合约实例
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=abi
            )
            
            # 测试只读函数
            interaction_results = {}
            
            # 测试DID验证器合约
            if 'DIDVerifier' in contract_name:
                try:
                    # 检查DID映射
                    did = contract.functions.didOfAddress(self.test_account.address).call()
                    interaction_results['did_of_address'] = did
                    logger.info(f"   - 地址对应的DID: {did}")
                except Exception as e:
                    logger.warning(f"   - 无法获取DID: {e}")
                
                try:
                    # 检查验证状态
                    is_verified = contract.functions.isVerified(self.test_account.address).call()
                    interaction_results['is_verified'] = is_verified
                    logger.info(f"   - 验证状态: {is_verified}")
                except Exception as e:
                    logger.warning(f"   - 无法检查验证状态: {e}")
            
            # 测试跨链桥合约
            elif 'Bridge' in contract_name:
                try:
                    # 检查链类型
                    chain_type = contract.functions.chainType().call()
                    interaction_results['chain_type'] = chain_type
                    logger.info(f"   - 链类型: {chain_type}")
                except Exception as e:
                    logger.warning(f"   - 无法获取链类型: {e}")
                
                try:
                    # 检查链ID
                    chain_id = contract.functions.chainId().call()
                    interaction_results['chain_id'] = chain_id
                    logger.info(f"   - 链ID: {chain_id}")
                except Exception as e:
                    logger.warning(f"   - 无法获取链ID: {e}")
            
            # 测试代币合约
            elif 'Token' in contract_name:
                try:
                    # 检查总供应量
                    total_supply = contract.functions.totalSupply().call()
                    interaction_results['total_supply'] = total_supply
                    logger.info(f"   - 总供应量: {w3.from_wei(total_supply, 'ether')} ETH")
                except Exception as e:
                    logger.warning(f"   - 无法获取总供应量: {e}")
                
                try:
                    # 检查测试账户余额
                    balance = contract.functions.balanceOf(self.test_account.address).call()
                    interaction_results['balance'] = balance
                    logger.info(f"   - 测试账户余额: {w3.from_wei(balance, 'ether')} ETH")
                except Exception as e:
                    logger.warning(f"   - 无法获取余额: {e}")
            
            result = {
                'interaction_successful': True,
                'interaction_results': interaction_results
            }
            
            logger.info(f"✅ {contract_name} 合约交互成功")
            return result
            
        except Exception as e:
            logger.error(f"❌ {contract_name} 合约交互失败: {e}")
            return {
                'interaction_successful': False,
                'error': str(e)
            }
    
    def run_comprehensive_test(self):
        """运行综合测试"""
        logger.info("🚀 开始Besu网络联通性和合约访问综合测试")
        logger.info("=" * 60)
        
        overall_success = True
        
        # 测试链A
        logger.info("\n📡 测试Besu链A...")
        chain_a_result = self.test_chain_connectivity('chain_a', self.chains['chain_a'])
        if chain_a_result:
            self.test_results['chain_a'] = chain_a_result
            w3_a = Web3(Web3.HTTPProvider(self.chains['chain_a']['rpc_url']))
            
            # 测试链A上的合约
            self.test_results['contracts']['chain_a'] = {}
            for contract_name, contract_info in self.contract_addresses.get('chain_a', {}).items():
                if contract_info and contract_info.get('address'):
                    abi_file = f"{contract_name}.json"
                    contract_result = self.test_contract_access(
                        'chain_a', w3_a, contract_name, 
                        contract_info['address'], abi_file
                    )
                    self.test_results['contracts']['chain_a'][contract_name] = contract_result
                    
                    # 测试合约交互
                    if contract_result.get('accessible'):
                        interaction_result = self.test_contract_interaction(
                            'chain_a', w3_a, contract_name,
                            contract_info['address'], abi_file
                        )
                        contract_result['interaction'] = interaction_result
        else:
            overall_success = False
        
        # 测试链B
        logger.info("\n📡 测试Besu链B...")
        chain_b_result = self.test_chain_connectivity('chain_b', self.chains['chain_b'])
        if chain_b_result:
            self.test_results['chain_b'] = chain_b_result
            w3_b = Web3(Web3.HTTPProvider(self.chains['chain_b']['rpc_url']))
            
            # 测试链B上的合约
            self.test_results['contracts']['chain_b'] = {}
            for contract_name, contract_info in self.contract_addresses.get('chain_b', {}).items():
                if contract_info and contract_info.get('address'):
                    abi_file = f"{contract_name}.json"
                    contract_result = self.test_contract_access(
                        'chain_b', w3_b, contract_name,
                        contract_info['address'], abi_file
                    )
                    self.test_results['contracts']['chain_b'][contract_name] = contract_result
                    
                    # 测试合约交互
                    if contract_result.get('accessible'):
                        interaction_result = self.test_contract_interaction(
                            'chain_b', w3_b, contract_name,
                            contract_info['address'], abi_file
                        )
                        contract_result['interaction'] = interaction_result
        else:
            overall_success = False
        
        # 设置总体状态
        self.test_results['overall_status'] = 'success' if overall_success else 'failed'
        
        # 生成测试报告
        self.generate_test_report()
        
        return overall_success
    
    def generate_test_report(self):
        """生成测试报告"""
        logger.info("\n" + "=" * 60)
        logger.info("📊 测试结果汇总")
        logger.info("=" * 60)
        
        # 链连接状态
        logger.info("\n🔗 链连接状态:")
        for chain_name, result in [('chain_a', self.test_results.get('chain_a')), 
                                 ('chain_b', self.test_results.get('chain_b'))]:
            if result:
                logger.info(f"  ✅ {chain_name}: 连接成功")
                logger.info(f"     - 区块高度: {result.get('block_number', 'N/A')}")
                logger.info(f"     - 链ID: {result.get('chain_id', 'N/A')}")
                logger.info(f"     - 测试账户余额: {result.get('test_account_balance', 'N/A')} ETH")
            else:
                logger.info(f"  ❌ {chain_name}: 连接失败")
        
        # 合约访问状态
        logger.info("\n📋 合约访问状态:")
        for chain_name in ['chain_a', 'chain_b']:
            chain_contracts = self.test_results.get('contracts', {}).get(chain_name, {})
            if chain_contracts:
                logger.info(f"  📡 {chain_name}:")
                for contract_name, contract_result in chain_contracts.items():
                    if contract_result.get('accessible'):
                        logger.info(f"    ✅ {contract_name}: 可访问")
                        if contract_result.get('interaction', {}).get('interaction_successful'):
                            logger.info(f"      - 交互测试: 成功")
                        else:
                            logger.info(f"      - 交互测试: 失败")
                    else:
                        logger.info(f"    ❌ {contract_name}: 不可访问")
            else:
                logger.info(f"  ⚠️  {chain_name}: 无合约信息")
        
        # 总体状态
        logger.info(f"\n🎯 总体状态: {'✅ 成功' if self.test_results['overall_status'] == 'success' else '❌ 失败'}")
        
        # 保存详细结果
        with open('besu_connectivity_test_results.json', 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        logger.info("\n📄 详细结果已保存到: besu_connectivity_test_results.json")

def main():
    """主函数"""
    test = BesuConnectivityTest()
    success = test.run_comprehensive_test()
    
    if success:
        print("\n🎉 Besu网络联通性和合约访问测试成功！")
        return 0
    else:
        print("\n❌ Besu网络联通性和合约访问测试失败！")
        return 1

if __name__ == "__main__":
    exit(main())
