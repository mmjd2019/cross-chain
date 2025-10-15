#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨链Schema注册脚本
为跨链交易建立专用的Schema和凭证定义
"""

import json
import requests
import time
import logging
from typing import Dict, Any, Optional

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CrossChainSchemaRegistrar:
    """跨链Schema注册器"""
    
    def __init__(self, 
                 issuer_admin_url: str = "http://localhost:8000",
                 holder_admin_url: str = "http://localhost:8001",
                 genesis_url: str = "http://localhost/genesis"):
        """
        初始化跨链Schema注册器
        
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
        
        logger.info(f"初始化跨链Schema注册器")
        logger.info(f"  发行者: {self.issuer_admin_url}")
        logger.info(f"  持有者: {self.holder_admin_url}")
        logger.info(f"  Genesis: {self.genesis_url}")
    
    def check_issuer_connection(self) -> bool:
        """检查发行者连接"""
        try:
            logger.info("🔍 检查发行者ACA-Py连接...")
            # 使用管理API端口检查状态
            admin_url = self.issuer_admin_url.replace(':8000', ':8080')
            response = requests.get(f"{admin_url}/status", timeout=10)
            
            if response.status_code == 200:
                status_data = response.json()
                logger.info(f"✅ 发行者连接成功: {status_data.get('version', 'Unknown')}")
                return True
            else:
                logger.error(f"❌ 发行者连接失败: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 发行者连接错误: {e}")
            return False
    
    def check_holder_connection(self) -> bool:
        """检查持有者连接"""
        try:
            logger.info("🔍 检查持有者ACA-Py连接...")
            # 使用管理API端口检查状态
            admin_url = self.holder_admin_url.replace(':8001', ':8081')
            response = requests.get(f"{admin_url}/status", timeout=10)
            
            if response.status_code == 200:
                status_data = response.json()
                logger.info(f"✅ 持有者连接成功: {status_data.get('version', 'Unknown')}")
                return True
            else:
                logger.error(f"❌ 持有者连接失败: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 持有者连接错误: {e}")
            return False
    
    def get_issuer_did(self) -> Optional[str]:
        """获取发行者DID"""
        try:
            logger.info("🔍 获取发行者DID...")
            # 使用管理API端口获取DID
            admin_url = self.issuer_admin_url.replace(':8000', ':8080')
            response = requests.get(f"{admin_url}/wallet/did", timeout=10)
            
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
                    "expiry"
                ]
            }
            
            # 使用管理API端口注册Schema
            admin_url = self.issuer_admin_url.replace(':8000', ':8080')
            response = requests.post(
                f"{admin_url}/schemas",
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
            
            # 使用管理API端口创建凭证定义
            admin_url = self.issuer_admin_url.replace(':8000', ':8080')
            response = requests.post(
                f"{admin_url}/credential-definitions",
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
    
    def run_full_registration(self) -> Dict[str, Any]:
        """运行完整的注册流程"""
        logger.info("🚀 开始跨链Schema注册流程")
        logger.info("=" * 60)
        
        result = {
            "success": False,
            "issuer_did": None,
            "schema_id": None,
            "cred_def_id": None,
            "error": None
        }
        
        try:
            # 1. 检查连接
            if not self.check_issuer_connection():
                result["error"] = "无法连接到发行者ACA-Py"
                return result
            
            if not self.check_holder_connection():
                result["error"] = "无法连接到持有者ACA-Py"
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
            result["success"] = True
            
            logger.info("🎉 跨链Schema注册完成！")
            logger.info("=" * 60)
            logger.info(f"✅ 发行者DID: {result['issuer_did']}")
            logger.info(f"✅ Schema ID: {result['schema_id']}")
            logger.info(f"✅ 凭证定义ID: {result['cred_def_id']}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 注册过程中出现错误: {e}")
            result["error"] = str(e)
            return result
    
    def save_results(self, result: Dict[str, Any], filename: str = "cross_chain_schema_results.json"):
        """保存注册结果"""
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
    print("🔐 跨链Schema注册工具")
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
    
    # 创建注册器
    registrar = CrossChainSchemaRegistrar(
        issuer_admin_url=config.get("acapy_services", {}).get("issuer", {}).get("admin_url", "http://localhost:8000"),
        holder_admin_url=config.get("acapy_services", {}).get("holder", {}).get("admin_url", "http://localhost:8001"),
        genesis_url=config.get("genesis", {}).get("url", "http://localhost/genesis")
    )
    
    # 运行注册流程
    result = registrar.run_full_registration()
    
    # 保存结果
    if result["success"]:
        registrar.save_results(result)
        print("\n🎉 跨链Schema注册成功！")
        print("现在您可以使用生成的Schema ID和凭证定义ID进行跨链VC颁发。")
    else:
        print(f"\n❌ 跨链Schema注册失败: {result['error']}")
        print("请检查:")
        print("  1. ACA-Py服务是否正在运行")
        print("  2. 网络连接是否正常")
        print("  3. 端口配置是否正确")

if __name__ == "__main__":
    main()
