# -*- coding: utf-8 -*-
"""
基于凭证定义ID的跨链VC生成器
使用指定的凭证定义ID: DPvobytTtKvmyeRTJZYjsg:3:CL:11:cross-chain-lock
与发行者ACA-Py通信生成可验证凭证
"""
import json
import requests
import time
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin
import urllib.parse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cross_chain_vc_generator.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CrossChainVCGenerator:
    """基于凭证定义ID的跨链VC生成器"""
    
    def __init__(self, 
                 issuer_admin_url: str = "http://192.168.230.178:8080",
                 issuer_endpoint: str = "http://192.168.230.178:8000",
                 holder_admin_url: str = "http://192.168.230.178:8081",
                 holder_endpoint: str = "http://192.168.230.178:8001"):
        """
        初始化跨链VC生成器
        
        Args:
            issuer_admin_url: 发行者ACA-Py管理API地址
            issuer_endpoint: 发行者端点地址
            holder_admin_url: 持有者ACA-Py管理API地址
            holder_endpoint: 持有者端点地址
        """
        self.issuer_admin_url = issuer_admin_url.rstrip('/')
        self.issuer_endpoint = issuer_endpoint.rstrip('/')
        self.holder_admin_url = holder_admin_url.rstrip('/')
        self.holder_endpoint = holder_endpoint.rstrip('/')
        
        # 跨链凭证定义ID
        self.cred_def_id = "DPvobytTtKvmyeRTJZYjsg:3:CL:11:cross-chain-lock"
        
        # API端点
        self.connections_endpoint = f"{self.issuer_admin_url}/connections"
        self.credentials_endpoint = f"{self.issuer_admin_url}/issue-credential"
        self.schemas_endpoint = f"{self.issuer_admin_url}/schemas"
        self.cred_defs_endpoint = f"{self.issuer_admin_url}/credential-definitions"
        self.status_endpoint = f"{self.issuer_admin_url}/status"
        
        # 持有者API端点
        self.holder_connections_endpoint = f"{self.holder_admin_url}/connections"
        self.holder_credentials_endpoint = f"{self.holder_admin_url}/issue-credential"
        
        logger.info(f"初始化跨链VC生成器")
        logger.info(f"发行者管理API: {self.issuer_admin_url}")
        logger.info(f"发行者端点: {self.issuer_endpoint}")
        logger.info(f"持有者管理API: {self.holder_admin_url}")
        logger.info(f"持有者端点: {self.holder_endpoint}")
        logger.info(f"凭证定义ID: {self.cred_def_id}")
    
    def check_issuer_connection(self) -> bool:
        """
        检查发行者ACA-Py连接状态
        
        Returns:
            连接是否成功
        """
        try:
            logger.info("🔍 检查发行者ACA-Py连接...")
            response = requests.get(self.status_endpoint, timeout=10)
            
            if response.status_code == 200:
                status_data = response.json()
                logger.info(f"✅ 发行者ACA-Py连接成功")
                logger.info(f"   版本: {status_data.get('version', 'Unknown')}")
                logger.info(f"   标签: {status_data.get('label', 'Unknown')}")
                return True
            else:
                logger.error(f"❌ 发行者ACA-Py连接失败: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 发行者ACA-Py连接错误: {e}")
            return False
    
    def check_holder_connection(self) -> bool:
        """
        检查持有者ACA-Py连接状态
        
        Returns:
            连接是否成功
        """
        try:
            logger.info("🔍 检查持有者ACA-Py连接...")
            response = requests.get(f"{self.holder_admin_url}/status", timeout=10)
            
            if response.status_code == 200:
                status_data = response.json()
                logger.info(f"✅ 持有者ACA-Py连接成功")
                logger.info(f"   版本: {status_data.get('version', 'Unknown')}")
                logger.info(f"   标签: {status_data.get('label', 'Unknown')}")
                return True
            else:
                logger.error(f"❌ 持有者ACA-Py连接失败: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 持有者ACA-Py连接错误: {e}")
            return False
    
    def verify_credential_definition(self) -> bool:
        """
        验证凭证定义是否存在
        
        Returns:
            凭证定义是否存在
        """
        try:
            logger.info(f"🔍 验证凭证定义: {self.cred_def_id}")
            
            response = requests.get(
                f"{self.cred_defs_endpoint}/{self.cred_def_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                cred_def_data = response.json()
                logger.info("✅ 凭证定义验证成功")
                logger.info(f"   ID: {cred_def_data.get('id')}")
                logger.info(f"   标签: {cred_def_data.get('tag')}")
                logger.info(f"   状态: {cred_def_data.get('state')}")
                return True
            else:
                logger.error(f"❌ 凭证定义验证失败: HTTP {response.status_code}")
                logger.error(f"响应: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 验证凭证定义时出错: {e}")
            return False
    
    def get_existing_connections(self) -> List[Dict[str, Any]]:
        """
        获取现有连接
        
        Returns:
            连接列表
        """
        try:
            logger.info("🔍 获取现有连接...")
            
            response = requests.get(self.connections_endpoint, timeout=10)
            
            if response.status_code == 200:
                connections_data = response.json()
                connections = connections_data.get('results', [])
                logger.info(f"✅ 找到 {len(connections)} 个连接")
                
                for i, conn in enumerate(connections):
                    logger.info(f"   连接 {i+1}: {conn.get('connection_id')} - {conn.get('state')}")
                
                return connections
            else:
                logger.error(f"❌ 获取连接失败: HTTP {response.status_code}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 获取连接时出错: {e}")
            return []
    
    def create_connection_invitation(self) -> Optional[Dict[str, Any]]:
        """
        创建连接邀请
        
        Returns:
            邀请信息或None
        """
        try:
            logger.info("📨 创建连接邀请...")
            
            invitation_data = {
                "auto_accept": True,
                "multi_use": False
            }
            
            response = requests.post(
                f"{self.connections_endpoint}/create-invitation",
                json=invitation_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                invitation = result.get('invitation', {})
                connection_id = result.get('connection_id')
                
                logger.info(f"✅ 连接邀请创建成功")
                logger.info(f"   连接ID: {connection_id}")
                
                # 确保邀请格式正确
                # 移除可能冲突的字段，使用正确的格式
                if 'did' in invitation:
                    del invitation['did']
                
                # 确保有正确的字段
                if '@type' not in invitation:
                    invitation['@type'] = "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/connections/1.0/invitation"
                
                # 构建完整的邀请URL
                invitation_url = f"{self.issuer_endpoint}?c_i={urllib.parse.quote(json.dumps(invitation))}"
                
                return {
                    'connection_id': connection_id,
                    'invitation': invitation,
                    'invitation_url': invitation_url
                }
            else:
                logger.error(f"❌ 创建连接邀请失败: HTTP {response.status_code}")
                logger.error(f"响应: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 创建连接邀请时出错: {e}")
            return None
    
    def receive_connection_invitation(self, invitation: Dict[str, Any]) -> Optional[str]:
        """
        持有者接收连接邀请
        
        Args:
            invitation: 邀请对象
            
        Returns:
            连接ID或None
        """
        try:
            logger.info("📨 持有者接收连接邀请...")
            
            # 直接传递邀请对象
            response = requests.post(
                f"{self.holder_connections_endpoint}/receive-invitation",
                json=invitation,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                connection_id = result.get('connection_id')
                
                logger.info(f"✅ 持有者接收邀请成功")
                logger.info(f"   连接ID: {connection_id}")
                return connection_id
            else:
                logger.error(f"❌ 持有者接收邀请失败: HTTP {response.status_code}")
                logger.error(f"响应: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 持有者接收邀请时出错: {e}")
            return None
    
    def accept_connection_response(self, connection_id: str) -> bool:
        """
        发行者接受连接响应
        
        Args:
            connection_id: 连接ID
            
        Returns:
            接受是否成功
        """
        try:
            logger.info(f"✅ 发行者接受连接响应: {connection_id}")
            
            response = requests.post(
                f"{self.connections_endpoint}/{connection_id}/accept-request",
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                logger.info("✅ 连接响应接受成功")
                return True
            else:
                logger.error(f"❌ 接受连接响应失败: HTTP {response.status_code}")
                logger.error(f"响应: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 接受连接响应时出错: {e}")
            return False
    
    def wait_for_connection_active(self, connection_id: str, timeout: int = 60) -> bool:
        """
        等待连接变为活跃状态
        
        Args:
            connection_id: 连接ID
            timeout: 超时时间（秒）
            
        Returns:
            连接是否变为活跃状态
        """
        try:
            logger.info(f"⏳ 等待连接变为活跃状态: {connection_id}")
            
            start_time = time.time()
            while time.time() - start_time < timeout:
                response = requests.get(
                    f"{self.connections_endpoint}/{connection_id}",
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    state = result.get('state')
                    
                    logger.info(f"   连接状态: {state}")
                    
                    if state == 'active':
                        logger.info("✅ 连接已变为活跃状态")
                        return True
                    elif state == 'error':
                        logger.error("❌ 连接建立失败")
                        return False
                    else:
                        time.sleep(3)
                else:
                    logger.error(f"❌ 检查连接状态失败: HTTP {response.status_code}")
                    return False
            
            logger.error("❌ 等待连接活跃状态超时")
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 等待连接时出错: {e}")
            return False
    
    def send_credential_offer(self, 
                            connection_id: str, 
                            attributes: Dict[str, str]) -> Optional[str]:
        """
        发送凭证提供
        
        Args:
            connection_id: 连接ID
            attributes: 凭证属性
            
        Returns:
            凭证交换ID或None
        """
        try:
            logger.info(f"📤 发送凭证提供...")
            logger.info(f"   连接ID: {connection_id}")
            logger.info(f"   凭证定义ID: {self.cred_def_id}")
            logger.info(f"   属性: {attributes}")
            
            # 构建属性列表
            attr_list = []
            for name, value in attributes.items():
                attr_list.append({"name": name, "value": value})
            
            offer_data = {
                "connection_id": connection_id,
                "cred_def_id": self.cred_def_id,
                "comment": "跨链锁定凭证",
                "credential_preview": {
                    "@type": "issue-credential/1.0/credential-preview",
                    "attributes": attr_list
                }
            }
            
            response = requests.post(
                f"{self.credentials_endpoint}/send-offer",
                json=offer_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                cred_ex_id = result.get('credential_exchange_id')
                
                logger.info(f"✅ 凭证提供发送成功")
                logger.info(f"   凭证交换ID: {cred_ex_id}")
                return cred_ex_id
            else:
                logger.error(f"❌ 发送凭证提供失败: HTTP {response.status_code}")
                logger.error(f"响应: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 发送凭证提供时出错: {e}")
            return None
    
    def get_credential_state(self, cred_ex_id: str) -> Optional[str]:
        """
        获取凭证状态
        
        Args:
            cred_ex_id: 凭证交换ID
            
        Returns:
            凭证状态或None
        """
        try:
            response = requests.get(
                f"{self.credentials_endpoint}/{cred_ex_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                state = result.get('state')
                logger.info(f"📊 凭证状态: {state}")
                return state
            else:
                logger.error(f"❌ 获取凭证状态失败: HTTP {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 获取凭证状态时出错: {e}")
            return None
    
    def issue_credential(self, cred_ex_id: str) -> bool:
        """
        颁发凭证
        
        Args:
            cred_ex_id: 凭证交换ID
            
        Returns:
            颁发是否成功
        """
        try:
            logger.info(f"📜 颁发凭证: {cred_ex_id}")
            
            issue_data = {
                "credential_exchange_id": cred_ex_id
            }
            
            response = requests.post(
                f"{self.credentials_endpoint}/issue",
                json=issue_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                logger.info("✅ 凭证颁发成功")
                return True
            else:
                logger.error(f"❌ 颁发凭证失败: HTTP {response.status_code}")
                logger.error(f"响应: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 颁发凭证时出错: {e}")
            return False
    
    def send_credential_request(self, holder_connection_id: str) -> Optional[str]:
        """
        持有者发送凭证请求
        
        Args:
            holder_connection_id: 持有者连接ID
            
        Returns:
            凭证交换ID或None
        """
        try:
            logger.info(f"📤 持有者发送凭证请求...")
            
            # 获取持有者的凭证交换记录
            response = requests.get(
                f"{self.holder_credentials_endpoint}/records",
                timeout=10
            )
            
            if response.status_code == 200:
                records = response.json()
                holder_cred_ex = None
                
                # 找到最新的凭证交换记录
                for record in records.get('results', []):
                    if record.get('state') == 'offer_received':
                        holder_cred_ex = record
                        break
                
                if not holder_cred_ex:
                    logger.error("❌ 未找到持有者的凭证提供记录")
                    return None
                
                cred_ex_id = holder_cred_ex['credential_exchange_id']
                logger.info(f"   持有者凭证交换ID: {cred_ex_id}")
                
                # 发送凭证请求
                request_data = {
                    "credential_exchange_id": cred_ex_id
                }
                
                response = requests.post(
                    f"{self.holder_credentials_endpoint}/records/{cred_ex_id}/send-request",
                    json=request_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                if response.status_code in [200, 201]:
                    logger.info("✅ 持有者凭证请求发送成功")
                    return cred_ex_id
                else:
                    logger.error(f"❌ 持有者发送凭证请求失败: HTTP {response.status_code}")
                    logger.error(f"响应: {response.text}")
                    return None
            else:
                logger.error(f"❌ 获取持有者凭证记录失败: HTTP {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 持有者发送凭证请求时出错: {e}")
            return None
    
    def generate_vc_with_holder(self, attributes: Dict[str, str]) -> Dict[str, Any]:
        """
        使用持有者生成VC的完整流程
        
        Args:
            attributes: 凭证属性
            
        Returns:
            生成结果字典
        """
        logger.info("🚀 使用持有者生成跨链VC完整流程")
        logger.info("=" * 60)
        
        result = {
            "success": False,
            "issuer_connection_id": None,
            "holder_connection_id": None,
            "cred_ex_id": None,
            "credential_id": None,
            "error": None,
            "invitation_url": None,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        try:
            # 1. 检查发行者连接
            if not self.check_issuer_connection():
                result["error"] = "无法连接到发行者ACA-Py"
                return result
            
            # 2. 检查持有者连接
            if not self.check_holder_connection():
                result["error"] = "无法连接到持有者ACA-Py"
                return result
            
            # 3. 验证凭证定义
            if not self.verify_credential_definition():
                result["error"] = "凭证定义验证失败"
                return result
            
            # 4. 发行者创建连接邀请
            invitation_info = self.create_connection_invitation()
            if not invitation_info:
                result["error"] = "无法创建连接邀请"
                return result
            
            result["issuer_connection_id"] = invitation_info["connection_id"]
            result["invitation_url"] = invitation_info["invitation_url"]
            
            logger.info("📋 发行者连接邀请已创建")
            logger.info(f"   邀请URL: {invitation_info['invitation_url']}")
            
            # 5. 持有者接收邀请
            holder_connection_id = self.receive_connection_invitation(invitation_info["invitation"])
            if not holder_connection_id:
                result["error"] = "持有者无法接收邀请"
                return result
            
            result["holder_connection_id"] = holder_connection_id
            
            # 6. 等待连接建立
            logger.info("⏳ 等待连接建立...")
            if self.wait_for_connection_active(invitation_info["connection_id"]):
                logger.info("✅ 连接建立成功")
            else:
                # 如果连接卡在response状态，尝试接受响应
                logger.info("🔄 连接卡在response状态，尝试接受响应...")
                self.accept_connection_response(invitation_info["connection_id"])
                
                # 等待一下让连接状态更新
                time.sleep(3)
            
            # 7. 发送凭证提供
            logger.info("📤 尝试发送凭证提供...")
            cred_ex_id = self.send_credential_offer(invitation_info["connection_id"], attributes)
            if not cred_ex_id:
                result["error"] = "无法发送凭证提供"
                return result
            
            result["cred_ex_id"] = cred_ex_id
            
            # 8. 持有者发送凭证请求
            logger.info("📤 持有者发送凭证请求...")
            holder_cred_ex_id = self.send_credential_request(holder_connection_id)
            if not holder_cred_ex_id:
                result["error"] = "持有者无法发送凭证请求"
                return result
            
            # 9. 发行者颁发凭证
            logger.info("📜 发行者颁发凭证...")
            if self.issue_credential(cred_ex_id):
                logger.info("✅ 凭证颁发成功")
            else:
                result["error"] = "凭证颁发失败"
                return result
            
            # 10. 等待凭证处理
            logger.info("⏳ 等待凭证处理...")
            time.sleep(5)
            
            # 11. 检查最终状态
            final_state = self.get_credential_state(cred_ex_id)
            if final_state in ["offer_sent", "request_received", "credential_issued", "credential_acked"]:
                result["success"] = True
                result["credential_id"] = cred_ex_id
                logger.info("🎉 跨链VC生成流程完成！")
            else:
                result["error"] = f"凭证状态异常: {final_state}"
            
            return result
            
        except Exception as e:
            logger.error(f"❌ VC生成过程中出现错误: {e}")
            result["error"] = str(e)
            return result
    
    def save_result(self, result: Dict[str, Any], filename: str = "cross_chain_vc_generation_result.json"):
        """
        保存生成结果
        
        Args:
            result: 生成结果
            filename: 文件名
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 结果已保存到: {filename}")
        except Exception as e:
            logger.error(f"❌ 保存结果时出错: {e}")

def main():
    """主函数 - 演示跨链VC生成流程"""
    print("🔐 基于凭证定义ID的跨链VC生成器")
    print("=" * 80)
    print(f"凭证定义ID: DPvobytTtKvmyeRTJZYjsg:3:CL:11:cross-chain-lock")
    print(f"发行者端点: http://192.168.230.178:8000")
    print(f"持有者端点: http://192.168.230.178:8001")
    print("=" * 80)
    
    # 创建跨链VC生成器
    vc_generator = CrossChainVCGenerator(
        issuer_admin_url="http://192.168.230.178:8080",
        issuer_endpoint="http://192.168.230.178:8000",
        holder_admin_url="http://192.168.230.178:8081",
        holder_endpoint="http://192.168.230.178:8001"
    )
    
    # 定义跨链凭证属性
    attributes = {
        "sourceChain": "chain_a",
        "targetChain": "chain_b",
        "amount": "100",
        "tokenAddress": "0x79eafd0b5ec8d3f945e6bb2817ed90b046c0d0af",
        "lockId": "cross_chain_lock_123456",
        "transactionHash": "0x1234567890abcdef",
        "expiry": "2024-12-31T23:59:59Z"
    }
    
    print(f"\n📝 跨链凭证属性: {attributes}")
    print()
    
    # 使用持有者生成跨链VC
    print("🚀 开始使用持有者生成跨链VC...")
    result = vc_generator.generate_vc_with_holder(attributes)
    
    # 保存结果
    vc_generator.save_result(result)
    
    # 显示结果
    print("\n📊 生成结果:")
    print("=" * 40)
    if result["success"]:
        print("✅ 跨链VC生成成功！")
        print(f"   发行者连接ID: {result['issuer_connection_id']}")
        print(f"   持有者连接ID: {result['holder_connection_id']}")
        print(f"   凭证交换ID: {result['cred_ex_id']}")
        print(f"   凭证ID: {result['credential_id']}")
        if result.get('invitation_url'):
            print(f"   邀请URL: {result['invitation_url']}")
    else:
        print(f"❌ 跨链VC生成失败: {result['error']}")
    
    print(f"\n💾 详细结果已保存到: cross_chain_vc_generation_result.json")

if __name__ == "__main__":
    main()
