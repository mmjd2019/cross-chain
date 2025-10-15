#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨链VC生成器
为跨链交易生成专用的可验证凭证
"""

import json
import requests
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CrossChainVCGenerator:
    """跨链VC生成器"""
    
    def __init__(self, 
                 issuer_admin_url: str = "http://localhost:8000",
                 holder_admin_url: str = "http://localhost:8001"):
        """
        初始化跨链VC生成器
        
        Args:
            issuer_admin_url: 发行者ACA-Py管理API地址
            holder_admin_url: 持有者ACA-Py管理API地址
        """
        self.issuer_admin_url = issuer_admin_url.rstrip('/')
        self.holder_admin_url = holder_admin_url.rstrip('/')
        
        # API端点
        self.issuer_connections_endpoint = f"{self.issuer_admin_url}/connections"
        self.issuer_credentials_endpoint = f"{self.issuer_admin_url}/issue-credential"
        self.holder_connections_endpoint = f"{self.holder_admin_url}/connections"
        self.holder_credentials_endpoint = f"{self.holder_admin_url}/issue-credential"
        
        logger.info(f"初始化跨链VC生成器")
        logger.info(f"  发行者: {self.issuer_admin_url}")
        logger.info(f"  持有者: {self.holder_admin_url}")
    
    def check_connections(self) -> bool:
        """检查ACA-Py连接"""
        try:
            # 检查发行者
            logger.info("🔍 检查发行者连接...")
            issuer_admin_url = self.issuer_admin_url.replace(':8000', ':8080')
            response = requests.get(f"{issuer_admin_url}/status", timeout=10)
            if response.status_code != 200:
                logger.error(f"❌ 发行者连接失败: HTTP {response.status_code}")
                return False
            
            # 检查持有者
            logger.info("🔍 检查持有者连接...")
            holder_admin_url = self.holder_admin_url.replace(':8001', ':8081')
            response = requests.get(f"{holder_admin_url}/status", timeout=10)
            if response.status_code != 200:
                logger.error(f"❌ 持有者连接失败: HTTP {response.status_code}")
                return False
            
            logger.info("✅ 所有连接正常")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 连接检查失败: {e}")
            return False
    
    def create_connection(self) -> Optional[Dict[str, Any]]:
        """创建连接"""
        try:
            logger.info("📨 创建连接邀请...")
            
            # 发行者创建邀请
            invitation_data = {
                "auto_accept": True,
                "multi_use": False
            }
            
            # 使用管理API端口创建连接邀请
            issuer_admin_url = self.issuer_admin_url.replace(':8000', ':8080')
            response = requests.post(
                f"{issuer_admin_url}/connections/create-invitation",
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
            
            # 使用管理API端口接收邀请
            holder_admin_url = self.holder_admin_url.replace(':8001', ':8081')
            response = requests.post(
                f"{holder_admin_url}/connections/receive-invitation",
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
                # 使用管理API端口检查连接状态
                issuer_admin_url = self.issuer_admin_url.replace(':8000', ':8080')
                response = requests.get(
                    f"{issuer_admin_url}/connections/{connection_id}",
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
                {"name": "expiry", "value": cross_chain_data.get('expiry', '')}
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
            
            # 使用管理API端口发送凭证提供
            issuer_admin_url = self.issuer_admin_url.replace(':8000', ':8080')
            response = requests.post(
                f"{issuer_admin_url}/issue-credential/send-offer",
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
            
            # 使用管理API端口请求凭证
            holder_admin_url = self.holder_admin_url.replace(':8001', ':8081')
            response = requests.post(
                f"{holder_admin_url}/issue-credential/send-request",
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
            
            # 使用管理API端口颁发凭证
            issuer_admin_url = self.issuer_admin_url.replace(':8000', ':8080')
            response = requests.post(
                f"{issuer_admin_url}/issue-credential/issue",
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
            
            # 检查最终状态
            # 使用管理API端口检查凭证状态
            issuer_admin_url = self.issuer_admin_url.replace(':8000', ':8080')
            response = requests.get(
                f"{issuer_admin_url}/issue-credential/{cred_ex_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                state = result.get('state')
                if state == 'credential_acked':
                    logger.info("🎉 跨链VC颁发完成！")
                    return cred_ex_id
                else:
                    logger.warning(f"凭证状态: {state}")
                    return cred_ex_id
            else:
                logger.warning("无法检查凭证状态，但可能已成功")
                return cred_ex_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 颁发跨链VC时出错: {e}")
            return None
    
    def generate_cross_chain_vc(self, 
                              cred_def_id: str,
                              cross_chain_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成跨链VC的完整流程"""
        logger.info("🚀 开始跨链VC生成流程")
        logger.info("=" * 60)
        
        result = {
            "success": False,
            "connection_id": None,
            "cred_ex_id": None,
            "error": None
        }
        
        try:
            # 1. 检查连接
            if not self.check_connections():
                result["error"] = "无法连接到ACA-Py服务"
                return result
            
            # 2. 创建连接
            connection_info = self.create_connection()
            if not connection_info:
                result["error"] = "无法创建连接"
                return result
            
            result["connection_id"] = connection_info["issuer_connection_id"]
            
            # 3. 等待连接建立
            if not self.wait_for_connection(connection_info["issuer_connection_id"]):
                result["error"] = "连接建立失败"
                return result
            
            # 4. 颁发跨链VC
            cred_ex_id = self.issue_cross_chain_vc(
                connection_info["issuer_connection_id"],
                cred_def_id,
                cross_chain_data
            )
            
            if not cred_ex_id:
                result["error"] = "跨链VC颁发失败"
                return result
            
            result["cred_ex_id"] = cred_ex_id
            result["success"] = True
            
            logger.info("🎉 跨链VC生成完成！")
            return result
            
        except Exception as e:
            logger.error(f"❌ 生成跨链VC时出错: {e}")
            result["error"] = str(e)
            return result
    
    def save_vc_result(self, result: Dict[str, Any], filename: str = "cross_chain_vc_result.json"):
        """保存VC生成结果"""
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
    """主函数 - 演示跨链VC生成"""
    print("🔐 跨链VC生成器")
    print("=" * 60)
    
    # 加载配置
    config = load_config()
    if not config:
        print("❌ 无法加载配置文件，使用默认配置")
        config = {
            "acapy_services": {
                "issuer": {"admin_url": "http://localhost:8000"},
                "holder": {"admin_url": "http://localhost:8001"}
            }
        }
    
    # 创建VC生成器
    vc_generator = CrossChainVCGenerator(
        issuer_admin_url=config.get("acapy_services", {}).get("issuer", {}).get("admin_url", "http://localhost:8000"),
        holder_admin_url=config.get("acapy_services", {}).get("holder", {}).get("admin_url", "http://localhost:8001")
    )
    
    # 示例跨链数据
    cross_chain_data = {
        "source_chain": "chain_a",
        "target_chain": "chain_b",
        "amount": "100",
        "token_address": "0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af",
        "lock_id": "lock_123456",
        "transaction_hash": "0xabcdef1234567890",
        "expiry": (datetime.now() + timedelta(hours=24)).isoformat()
    }
    
    # 使用之前注册的凭证定义ID
    cred_def_id = "DPvobytTtKvmyeRTJZYjsg:3:CL:11:cross-chain-lock"  # 从Schema注册结果获取
    
    print(f"📋 跨链数据:")
    for key, value in cross_chain_data.items():
        print(f"   {key}: {value}")
    print(f"   凭证定义ID: {cred_def_id}")
    print()
    
    # 生成跨链VC
    result = vc_generator.generate_cross_chain_vc(cred_def_id, cross_chain_data)
    
    # 保存结果
    if result["success"]:
        vc_generator.save_vc_result(result)
        print("\n🎉 跨链VC生成成功！")
        print("=" * 60)
        print(f"✅ 连接ID: {result['connection_id']}")
        print(f"✅ 凭证交换ID: {result['cred_ex_id']}")
    else:
        print(f"\n❌ 跨链VC生成失败: {result['error']}")

if __name__ == "__main__":
    main()
