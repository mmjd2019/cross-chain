#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨链VC完整设置脚本
一键完成跨链Schema注册、凭证定义创建和VC生成
"""

import json
import requests
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CrossChainVCSetup:
    """跨链VC完整设置"""
    
    def __init__(self, 
                 issuer_admin_url: str = "http://localhost:8000",
                 holder_admin_url: str = "http://localhost:8001",
                 genesis_url: str = "http://localhost/genesis"):
        """
        初始化跨链VC设置
        
        Args:
            issuer_admin_url: 发行者ACA-Py管理API地址
            holder_admin_url: 持有者ACA-Py管理API地址
            genesis_url: Genesis文件URL
        """
        self.issuer_admin_url = issuer_admin_url.rstrip('/')
        self.holder_admin_url = holder_admin_url.rstrip('/')
        self.genesis_url = genesis_url
        
        # API端点
        self.issuer_schemas_endpoint = f"{self.issuer_admin_url}/schemas"
        self.issuer_cred_defs_endpoint = f"{self.issuer_admin_url}/credential-definitions"
        self.issuer_wallet_endpoint = f"{self.issuer_admin_url}/wallet"
        self.issuer_connections_endpoint = f"{self.issuer_admin_url}/connections"
        self.issuer_credentials_endpoint = f"{self.issuer_admin_url}/issue-credential"
        
        self.holder_connections_endpoint = f"{self.holder_admin_url}/connections"
        self.holder_credentials_endpoint = f"{self.holder_admin_url}/issue-credential"
        
        logger.info(f"初始化跨链VC设置")
        logger.info(f"  发行者: {self.issuer_admin_url}")
        logger.info(f"  持有者: {self.holder_admin_url}")
        logger.info(f"  Genesis: {self.genesis_url}")
    
    def check_services(self) -> bool:
        """检查所有服务连接"""
        try:
            # 检查发行者
            logger.info("🔍 检查发行者ACA-Py...")
            response = requests.get(f"{self.issuer_admin_url}/status", timeout=10)
            if response.status_code != 200:
                logger.error(f"❌ 发行者连接失败: HTTP {response.status_code}")
                return False
            
            # 检查持有者
            logger.info("🔍 检查持有者ACA-Py...")
            response = requests.get(f"{self.holder_admin_url}/status", timeout=10)
            if response.status_code != 200:
                logger.error(f"❌ 持有者连接失败: HTTP {response.status_code}")
                return False
            
            logger.info("✅ 所有服务连接正常")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 服务检查失败: {e}")
            return False
    
    def get_issuer_did(self) -> Optional[str]:
        """获取发行者DID"""
        try:
            logger.info("🔍 获取发行者DID...")
            response = requests.get(f"{self.issuer_wallet_endpoint}/did", timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                dids = result.get('results', [])
                if dids:
                    did = dids[0].get('did')
                    logger.info(f"✅ 发行者DID: {did}")
                    return did
                else:
                    logger.error("❌ 未找到发行者DID")
                    return None
            else:
                logger.error(f"❌ 获取发行者DID失败: HTTP {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 获取发行者DID时出错: {e}")
            return None
    
    def register_cross_chain_schema(self) -> Optional[Dict[str, Any]]:
        """注册跨链Schema"""
        try:
            logger.info("📋 注册跨链Schema...")
            
            schema_data = {
                "schema_name": "CrossChainLockCredential",
                "schema_version": "1.0",
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
            
            response = requests.post(
                f"{self.issuer_schemas_endpoint}",
                json=schema_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                schema_id = result.get('schema_id')
                logger.info(f"✅ Schema注册成功: {schema_id}")
                return result
            else:
                logger.error(f"❌ Schema注册失败: HTTP {response.status_code}")
                logger.error(f"响应: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 注册Schema时出错: {e}")
            return None
    
    def create_credential_definition(self, schema_id: str) -> Optional[Dict[str, Any]]:
        """创建凭证定义"""
        try:
            logger.info(f"📜 创建凭证定义: {schema_id}")
            
            cred_def_data = {
                "schema_id": schema_id,
                "tag": "cross-chain-lock",
                "support_revocation": False
            }
            
            response = requests.post(
                f"{self.issuer_cred_defs_endpoint}",
                json=cred_def_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                cred_def_id = result.get('credential_definition_id')
                logger.info(f"✅ 凭证定义创建成功: {cred_def_id}")
                return result
            else:
                logger.error(f"❌ 凭证定义创建失败: HTTP {response.status_code}")
                logger.error(f"响应: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 创建凭证定义时出错: {e}")
            return None
    
    def create_connection(self) -> Optional[Dict[str, Any]]:
        """创建连接"""
        try:
            logger.info("📨 创建连接...")
            
            # 发行者创建邀请
            invitation_data = {
                "auto_accept": True,
                "multi_use": False
            }
            
            response = requests.post(
                f"{self.issuer_connections_endpoint}/create-invitation",
                json=invitation_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"❌ 创建邀请失败: HTTP {response.status_code}")
                return None
            
            issuer_result = response.json()
            connection_id = issuer_result.get('connection_id')
            invitation = issuer_result.get('invitation', {})
            
            logger.info(f"✅ 发行者邀请创建成功: {connection_id}")
            
            # 持有者接收邀请
            logger.info("📥 持有者接收邀请...")
            receive_data = {"invitation": invitation}
            
            response = requests.post(
                f"{self.holder_connections_endpoint}/receive-invitation",
                json=receive_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"❌ 接收邀请失败: HTTP {response.status_code}")
                return None
            
            holder_result = response.json()
            holder_connection_id = holder_result.get('connection_id')
            
            logger.info(f"✅ 持有者连接建立: {holder_connection_id}")
            
            return {
                'issuer_connection_id': connection_id,
                'holder_connection_id': holder_connection_id,
                'invitation': invitation
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 创建连接时出错: {e}")
            return None
    
    def wait_for_connection(self, connection_id: str, timeout: int = 60) -> bool:
        """等待连接建立"""
        try:
            logger.info(f"⏳ 等待连接建立: {connection_id}")
            
            start_time = time.time()
            while time.time() - start_time < timeout:
                response = requests.get(
                    f"{self.issuer_connections_endpoint}/{connection_id}",
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    state = result.get('state')
                    
                    if state == 'active':
                        logger.info("✅ 连接已建立")
                        return True
                    elif state == 'error':
                        logger.error("❌ 连接建立失败")
                        return False
                    else:
                        logger.info(f"连接状态: {state}")
                        time.sleep(2)
                else:
                    logger.error(f"❌ 检查连接状态失败: HTTP {response.status_code}")
                    return False
            
            logger.error("❌ 连接建立超时")
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 等待连接时出错: {e}")
            return False
    
    def issue_cross_chain_vc(self, 
                           connection_id: str,
                           cred_def_id: str,
                           cross_chain_data: Dict[str, Any]) -> Optional[str]:
        """颁发跨链VC"""
        try:
            logger.info(f"📤 颁发跨链VC: {cred_def_id}")
            
            # 构建凭证属性
            attributes = [
                {"name": "sourceChain", "value": cross_chain_data.get('source_chain', '')},
                {"name": "targetChain", "value": cross_chain_data.get('target_chain', '')},
                {"name": "amount", "value": str(cross_chain_data.get('amount', 0))},
                {"name": "tokenAddress", "value": cross_chain_data.get('token_address', '')},
                {"name": "lockId", "value": cross_chain_data.get('lock_id', '')},
                {"name": "transactionHash", "value": cross_chain_data.get('transaction_hash', '')},
                {"name": "expiry", "value": cross_chain_data.get('expiry', '')},
                {"name": "userAddress", "value": cross_chain_data.get('user_address', '')}
            ]
            
            # 发送凭证提供
            offer_data = {
                "connection_id": connection_id,
                "credential_definition_id": cred_def_id,
                "comment": "Cross-Chain Lock Credential",
                "credential_preview": {
                    "@type": "issue-credential/1.0/credential-preview",
                    "attributes": attributes
                }
            }
            
            response = requests.post(
                f"{self.issuer_credentials_endpoint}/send-offer",
                json=offer_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"❌ 发送凭证提供失败: HTTP {response.status_code}")
                logger.error(f"响应: {response.text}")
                return None
            
            result = response.json()
            cred_ex_id = result.get('credential_exchange_id')
            logger.info(f"✅ 凭证提供发送成功: {cred_ex_id}")
            
            # 持有者请求凭证
            logger.info("📥 持有者请求凭证...")
            request_data = {"credential_exchange_id": cred_ex_id}
            
            response = requests.post(
                f"{self.holder_credentials_endpoint}/send-request",
                json=request_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"❌ 请求凭证失败: HTTP {response.status_code}")
                return None
            
            logger.info("✅ 凭证请求发送成功")
            
            # 发行者颁发凭证
            logger.info("📜 发行者颁发凭证...")
            issue_data = {"credential_exchange_id": cred_ex_id}
            
            response = requests.post(
                f"{self.issuer_credentials_endpoint}/issue",
                json=issue_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"❌ 颁发凭证失败: HTTP {response.status_code}")
                return None
            
            logger.info("✅ 凭证颁发成功")
            
            # 等待凭证完成
            logger.info("⏳ 等待凭证完成...")
            time.sleep(5)
            
            return cred_ex_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 颁发跨链VC时出错: {e}")
            return None
    
    def run_full_setup(self) -> Dict[str, Any]:
        """运行完整的跨链VC设置"""
        logger.info("🚀 开始跨链VC完整设置")
        logger.info("=" * 60)
        
        result = {
            "success": False,
            "issuer_did": None,
            "schema_id": None,
            "cred_def_id": None,
            "connection_id": None,
            "test_vc_id": None,
            "error": None
        }
        
        try:
            # 1. 检查服务
            if not self.check_services():
                result["error"] = "无法连接到ACA-Py服务"
                return result
            
            # 2. 获取发行者DID
            issuer_did = self.get_issuer_did()
            if not issuer_did:
                result["error"] = "无法获取发行者DID"
                return result
            
            result["issuer_did"] = issuer_did
            
            # 3. 注册Schema
            schema_result = self.register_cross_chain_schema()
            if not schema_result:
                result["error"] = "Schema注册失败"
                return result
            
            result["schema_id"] = schema_result["schema_id"]
            
            # 4. 创建凭证定义
            cred_def_result = self.create_credential_definition(schema_result["schema_id"])
            if not cred_def_result:
                result["error"] = "凭证定义创建失败"
                return result
            
            result["cred_def_id"] = cred_def_result["credential_definition_id"]
            
            # 5. 创建连接
            connection_info = self.create_connection()
            if not connection_info:
                result["error"] = "无法创建连接"
                return result
            
            result["connection_id"] = connection_info["issuer_connection_id"]
            
            # 6. 等待连接建立
            if not self.wait_for_connection(connection_info["issuer_connection_id"]):
                result["error"] = "连接建立失败"
                return result
            
            # 7. 测试颁发VC
            test_data = {
                "source_chain": "chain_a",
                "target_chain": "chain_b",
                "amount": "100",
                "token_address": "0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af",
                "lock_id": "test_lock_123456",
                "transaction_hash": "0xabcdef1234567890",
                "expiry": (datetime.now() + timedelta(hours=24)).isoformat(),
                "user_address": "0x1234567890123456789012345678901234567890"
            }
            
            test_vc_id = self.issue_cross_chain_vc(
                connection_info["issuer_connection_id"],
                cred_def_result["credential_definition_id"],
                test_data
            )
            
            if test_vc_id:
                result["test_vc_id"] = test_vc_id
                result["success"] = True
                logger.info("🎉 跨链VC设置完成！")
            else:
                result["error"] = "测试VC颁发失败"
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 设置过程中出现错误: {e}")
            result["error"] = str(e)
            return result
    
    def save_results(self, result: Dict[str, Any], filename: str = "cross_chain_vc_setup_results.json"):
        """保存设置结果"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ 结果已保存到: {filename}")
        except Exception as e:
            logger.error(f"❌ 保存结果时出错: {e}")

def load_config(config_file: str = "cross_chain_vc_config.json") -> Dict[str, Any]:
    """加载配置文件"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ 加载配置文件失败: {e}")
        return {}

def main():
    """主函数"""
    print("🔐 跨链VC完整设置工具")
    print("=" * 60)
    print()
    
    # 加载配置
    config = load_config()
    if not config:
        print("❌ 无法加载配置文件，使用默认配置")
        config = {
            "acapy_services": {
                "issuer": {"admin_url": "http://localhost:8000"},
                "holder": {"admin_url": "http://localhost:8001"}
            },
            "genesis": {"url": "http://localhost/genesis"}
        }
    
    # 创建设置器
    setup = CrossChainVCSetup(
        issuer_admin_url=config.get("acapy_services", {}).get("issuer", {}).get("admin_url", "http://localhost:8000"),
        holder_admin_url=config.get("acapy_services", {}).get("holder", {}).get("admin_url", "http://localhost:8001"),
        genesis_url=config.get("genesis", {}).get("url", "http://localhost/genesis")
    )
    
    # 运行完整设置
    result = setup.run_full_setup()
    
    # 保存结果
    if result["success"]:
        setup.save_results(result)
        print("\n🎉 跨链VC设置成功！")
        print("=" * 60)
        print(f"✅ 发行者DID: {result['issuer_did']}")
        print(f"✅ Schema ID: {result['schema_id']}")
        print(f"✅ 凭证定义ID: {result['cred_def_id']}")
        print(f"✅ 连接ID: {result['connection_id']}")
        print(f"✅ 测试VC ID: {result['test_vc_id']}")
        print("\n现在您可以使用这些ID进行跨链VC操作了！")
    else:
        print(f"\n❌ 跨链VC设置失败: {result['error']}")
        print("请检查:")
        print("  1. ACA-Py服务是否正在运行")
        print("  2. 网络连接是否正常")
        print("  3. 端口配置是否正确")

if __name__ == "__main__":
    main()
