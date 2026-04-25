#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量创建Schema和凭证定义
从config/cross_chain_vc_config.json读取schema1-4的配置
通过发行者ACA-Py创建这4个schema和对应的凭证定义
"""

import json
import requests
import logging
import time
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SchemaCredDefBatchCreator:
    """批量创建Schema和凭证定义"""

    def __init__(self, config_file: str = "config/cross_chain_vc_config.json"):
        """
        初始化批量创建器

        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = self.load_config()

        # 从配置获取发行者URL
        acapy_services = self.config.get("acapy_services", {})
        issuer_config = acapy_services.get("issuer", {})
        self.issuer_admin_url = issuer_config.get("admin_url", "http://localhost:8080")

        # API端点
        self.schemas_endpoint = f"{self.issuer_admin_url}/schemas"
        self.cred_defs_endpoint = f"{self.issuer_admin_url}/credential-definitions"
        self.status_endpoint = f"{self.issuer_admin_url}/status"
        self.wallet_did_endpoint = f"{self.issuer_admin_url}/wallet/did"

        # 获取发行者DID
        self.issuer_did = self.get_issuer_did()

        logger.info(f"初始化Schema批量创建器")
        logger.info(f"发行者URL: {self.issuer_admin_url}")
        logger.info(f"发行者DID: {self.issuer_did}")

    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"✅ 成功加载配置文件: {self.config_file}")
                return config
            else:
                logger.error(f"❌ 配置文件不存在: {self.config_file}")
                return {}
        except Exception as e:
            logger.error(f"❌ 加载配置文件失败: {e}")
            return {}

    def get_issuer_did(self) -> Optional[str]:
        """获取发行者DID"""
        try:
            response = requests.get(self.wallet_did_endpoint, timeout=10)
            if response.status_code == 200:
                result = response.json()
                dids = result.get('results', [])
                if dids:
                    # 优先使用公共DID
                    for did_info in dids:
                        if did_info.get('posture') == 'public':
                            logger.info(f"✅ 使用公共DID: {did_info['did']}")
                            return did_info['did']
                    # 如果没有公共DID，使用第一个
                    logger.info(f"✅ 使用DID: {dids[0]['did']}")
                    return dids[0]['did']
            return None
        except Exception as e:
            logger.error(f"❌ 获取发行者DID失败: {e}")
            return None

    def check_connection(self) -> bool:
        """检查ACA-Py连接"""
        try:
            response = requests.get(self.status_endpoint, timeout=10)
            if response.status_code == 200:
                status_data = response.json()
                logger.info(f"✅ 发行者连接成功: {status_data.get('version', 'Unknown')}")
                return True
            else:
                logger.error(f"❌ 发行者连接失败: HTTP {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ 连接检查失败: {e}")
            return False

    def get_schema_configs(self) -> List[Dict[str, Any]]:
        """
        从配置文件获取所有schema配置

        Returns:
            schema配置列表
        """
        schemas = []

        # 获取schema1-4
        for i in range(1, 5):
            schema_key = f"schema{i}"
            if schema_key in self.config:
                schema_config = self.config[schema_key]
                schemas.append({
                    "key": schema_key,
                    "name": schema_config.get("name"),
                    "version": schema_config.get("version"),
                    "attributes": schema_config.get("attributes", [])
                })

        logger.info(f"找到 {len(schemas)} 个schema配置")
        return schemas

    def create_schema(self, schema_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        创建单个Schema

        Args:
            schema_config: Schema配置

        Returns:
            创建结果
        """
        try:
            name = schema_config["name"]
            version = schema_config["version"]
            attributes = schema_config["attributes"]

            logger.info(f"📋 创建Schema: {name} v{version}")
            logger.info(f"   属性: {', '.join(attributes)}")

            schema_data = {
                "schema_name": name,
                "schema_version": version,
                "attributes": attributes
            }

            response = requests.post(
                self.schemas_endpoint,
                json=schema_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            if response.status_code in [200, 201]:
                result = response.json()
                schema_id = result.get('schema_id')
                logger.info(f"✅ Schema创建成功: {schema_id}")
                return {
                    "success": True,
                    "schema_id": schema_id,
                    "schema_name": name,
                    "schema_version": version
                }
            else:
                error_msg = response.text
                logger.error(f"❌ Schema创建失败: HTTP {response.status_code}")
                logger.error(f"响应: {error_msg}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "response": error_msg
                }

        except Exception as e:
            logger.error(f"❌ 创建Schema时出错: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def create_credential_definition(self, schema_id: str, tag: str = "default") -> Optional[Dict[str, Any]]:
        """
        创建凭证定义

        Args:
            schema_id: Schema ID
            tag: 凭证定义标签

        Returns:
            创建结果
        """
        try:
            logger.info(f"📜 创建凭证定义: {schema_id}")
            logger.info(f"   标签: {tag}")

            cred_def_data = {
                "schema_id": schema_id,
                "tag": tag,
                "support_revocation": False
            }

            response = requests.post(
                self.cred_defs_endpoint,
                json=cred_def_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            if response.status_code in [200, 201]:
                result = response.json()
                cred_def_id = result.get('credential_definition_id')
                logger.info(f"✅ 凭证定义创建成功: {cred_def_id}")
                return {
                    "success": True,
                    "cred_def_id": cred_def_id,
                    "schema_id": schema_id,
                    "tag": tag
                }
            else:
                error_msg = response.text
                logger.error(f"❌ 凭证定义创建失败: HTTP {response.status_code}")
                logger.error(f"响应: {error_msg}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "response": error_msg
                }

        except Exception as e:
            logger.error(f"❌ 创建凭证定义时出错: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def create_all_schemas_and_cred_defs(self) -> Dict[str, Any]:
        """
        创建所有Schema和凭证定义

        Returns:
            创建结果摘要
        """
        logger.info("🚀 开始批量创建Schema和凭证定义")
        logger.info("=" * 60)

        results = {
            "created_at": datetime.now().isoformat(),
            "issuer_did": self.issuer_did,
            "issuer_admin_url": self.issuer_admin_url,
            "total_schemas": 0,
            "successful_schemas": 0,
            "failed_schemas": 0,
            "successful_cred_defs": 0,
            "failed_cred_defs": 0,
            "schemas": []
        }

        # 获取所有schema配置
        schema_configs = self.get_schema_configs()
        results["total_schemas"] = len(schema_configs)

        if not schema_configs:
            logger.error("❌ 未找到任何schema配置")
            return results

        # 为每个schema创建凭证定义
        for schema_config in schema_configs:
            schema_key = schema_config["key"]
            logger.info(f"\n{'=' * 60}")
            logger.info(f"处理 {schema_key}: {schema_config['name']}")
            logger.info('=' * 60)

            # 创建Schema
            schema_result = self.create_schema(schema_config)

            schema_info = {
                "key": schema_key,
                "name": schema_config["name"],
                "version": schema_config["version"],
                "attributes": schema_config["attributes"],
                "schema_result": schema_result,
                "cred_def_result": None
            }

            if schema_result.get("success"):
                results["successful_schemas"] += 1
                schema_id = schema_result["schema_id"]

                # 等待一下
                time.sleep(1)

                # 创建凭证定义（使用schema名称作为tag）
                cred_def_result = self.create_credential_definition(
                    schema_id,
                    tag=schema_config["name"]
                )
                schema_info["cred_def_result"] = cred_def_result

                if cred_def_result.get("success"):
                    results["successful_cred_defs"] += 1
                else:
                    results["failed_cred_defs"] += 1
            else:
                results["failed_schemas"] += 1
                results["failed_cred_defs"] += 1

            results["schemas"].append(schema_info)

            # 等待一下再处理下一个
            time.sleep(2)

        return results

    def save_results(self, results: Dict[str, Any], filename: str = "schema_cred_def_batch_results.json"):
        """保存结果到JSON文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ 结果已保存到: {filename}")
            return filename
        except Exception as e:
            logger.error(f"❌ 保存结果时出错: {e}")
            return None

    def generate_vc_config(self, results: Dict[str, Any], output_file: str = "config/vc_config.json"):
        """
        生成vc_config.json配置文件

        Args:
            results: 创建结果
            output_file: 输出文件路径

        Returns:
            文件路径或None
        """
        try:
            logger.info(f"📝 生成vc_config.json...")

            # 构建vc_config结构
            vc_config = {
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "description": "VC凭证配置文件 - 包含Schema和Credential Definition信息",
                    "version": "1.0"
                },
                "issuer": {
                    "did": results["issuer_did"],
                    "admin_url": results["issuer_admin_url"],
                    "endpoint": self.config.get("acapy_services", {}).get("issuer", {}).get("endpoint", "http://localhost:8000")
                },
                "holder": {
                    "admin_url": self.config.get("acapy_services", {}).get("holder", {}).get("admin_url", "http://localhost:8081"),
                    "endpoint": self.config.get("acapy_services", {}).get("holder", {}).get("endpoint", "http://localhost:8001")
                },
                "von_network": {
                    "genesis_url": self.config.get("genesis", {}).get("url", "http://localhost/genesis"),
                    "network_name": self.config.get("genesis", {}).get("network_name", "von-network")
                },
                "schemas": {}
            }

            # 处理每个schema的结果
            for schema_info in results["schemas"]:
                key = schema_info["key"]
                schema_result = schema_info["schema_result"]
                cred_def_result = schema_info["cred_def_result"]

                # 构建schema配置
                schema_config = {
                    "name": schema_info["name"],
                    "version": schema_info["version"],
                    "attributes": schema_info["attributes"]
                }

                # 如果schema创建成功，添加ID
                if schema_result and schema_result.get("success"):
                    schema_config["schema_id"] = schema_result["schema_id"]

                # 如果cred_def创建成功，添加ID
                if cred_def_result and cred_def_result.get("success"):
                    schema_config["cred_def_id"] = cred_def_result["cred_def_id"]
                    schema_config["tag"] = cred_def_result.get("tag", schema_info["name"])

                # 添加到vc_config
                vc_config["schemas"][key] = schema_config

            # 添加统计信息
            vc_config["summary"] = {
                "total_schemas": results["total_schemas"],
                "successful_schemas": results["successful_schemas"],
                "failed_schemas": results["failed_schemas"],
                "successful_cred_defs": results["successful_cred_defs"],
                "failed_cred_defs": results["failed_cred_defs"]
            }

            # 确保config目录存在
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            # 保存到文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(vc_config, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ vc_config.json已保存到: {output_file}")
            return output_file

        except Exception as e:
            logger.error(f"❌ 生成vc_config.json时出错: {e}")
            return None

    def print_summary(self, results: Dict[str, Any]):
        """打印创建摘要"""
        print("\n" + "=" * 60)
        print("📊 创建摘要")
        print("=" * 60)
        print(f"创建时间: {results['created_at']}")
        print(f"发行者DID: {results['issuer_did']}")
        print(f"总Schema数: {results['total_schemas']}")
        print(f"成功Schema: {results['successful_schemas']}")
        print(f"失败Schema: {results['failed_schemas']}")
        print(f"成功凭证定义: {results['successful_cred_defs']}")
        print(f"失败凭证定义: {results['failed_cred_defs']}")

        # 打印每个schema的详细信息
        print(f"\n📋 Schema详情:")
        for schema_info in results["schemas"]:
            status = "✅" if schema_info["schema_result"].get("success") else "❌"
            print(f"\n{status} {schema_info['key']}: {schema_info['name']} v{schema_info['version']}")

            if schema_info["schema_result"].get("success"):
                print(f"   Schema ID: {schema_info['schema_result']['schema_id']}")

            if schema_info["cred_def_result"]:
                cred_status = "✅" if schema_info["cred_def_result"].get("success") else "❌"
                if schema_info["cred_def_result"].get("success"):
                    print(f"   {cred_status} 凭证定义ID: {schema_info['cred_def_result']['cred_def_id']}")
                else:
                    print(f"   {cred_status} 凭证定义创建失败: {schema_info['cred_def_result'].get('error')}")
            else:
                print(f"   ❌ 凭证定义未创建")

        print("=" * 60)


def main():
    """主函数"""
    print("🔐 批量创建Schema和凭证定义")
    print("=" * 60)

    # 创建批量创建器
    creator = SchemaCredDefBatchCreator()

    # 检查连接
    if not creator.check_connection():
        print("❌ 无法连接到发行者ACA-Py，请检查服务是否运行")
        return

    # 创建所有Schema和凭证定义
    results = creator.create_all_schemas_and_cred_defs()

    # 保存详细结果
    creator.save_results(results)

    # 生成vc_config.json
    vc_config_file = creator.generate_vc_config(results)

    # 打印摘要
    creator.print_summary(results)

    # 额外打印vc_config信息
    if vc_config_file:
        print(f"\n📁 VC配置文件: {vc_config_file}")
        print(f"   包含4个Schema和Credential Definition的完整配置")
        print(f"   可用于VC发行服务和验证服务")

    if results["successful_schemas"] == results["total_schemas"]:
        print("\n🎉 所有Schema和凭证定义创建成功！")
        print("✅ vc_config.json已生成到config目录")
    else:
        print(f"\n⚠️ 部分Schema或凭证定义创建失败")
        print(f"   成功: {results['successful_schemas']}/{results['total_schemas']}")


if __name__ == "__main__":
    main()
