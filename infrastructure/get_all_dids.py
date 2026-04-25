#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取所有DID列表脚本
从发行者和持有者ACA-Py服务获取所有DID
"""

import json
import requests
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DIDListRetriever:
    """DID列表获取器"""

    def __init__(self,
                 issuer_admin_url: str = "http://localhost:8080",
                 holder_admin_url: str = "http://localhost:8081",
                 output_file: str = "all_dids_list.json"):
        """
        初始化DID列表获取器

        Args:
            issuer_admin_url: 发行者ACA-Py管理API地址
            holder_admin_url: 持有者ACA-Py管理API地址
            output_file: 输出JSON文件名
        """
        self.issuer_admin_url = issuer_admin_url.rstrip('/')
        self.holder_admin_url = holder_admin_url.rstrip('/')
        self.output_file = output_file

        logger.info(f"初始化DID列表获取器")
        logger.info(f"  发行者: {self.issuer_admin_url}")
        logger.info(f"  持有者: {self.holder_admin_url}")
        logger.info(f"  输出文件: {self.output_file}")

    def check_connection(self, admin_url: str, name: str) -> bool:
        """检查ACA-Py连接"""
        try:
            response = requests.get(f"{admin_url}/status", timeout=10)
            if response.status_code == 200:
                status_data = response.json()
                logger.info(f"✅ {name}连接成功: {status_data.get('version', 'Unknown')}")
                return True
            else:
                logger.error(f"❌ {name}连接失败: HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ {name}连接错误: {e}")
            return False

    def get_did_list(self, admin_url: str, role: str) -> List[Dict[str, Any]]:
        """
        获取DID列表

        Args:
            admin_url: ACA-Py管理API地址
            role: 角色 (issuer 或 holder)

        Returns:
            DID列表
        """
        try:
            logger.info(f"🔍 获取{role}的DID列表...")

            response = requests.get(
                f"{admin_url}/wallet/did",
                params={"verify": False},
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                dids = result.get('results', [])

                logger.info(f"✅ {role}找到 {len(dids)} 个DID")

                # 添加角色信息
                for did in dids:
                    did['role'] = role
                    did['retrieved_at'] = datetime.now().isoformat()

                return dids
            else:
                logger.error(f"❌ {role}获取DID列表失败: HTTP {response.status_code}")
                logger.error(f"响应: {response.text}")
                return []

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ {role}获取DID列表时出错: {e}")
            return []

    def retrieve_all_dids(self) -> Dict[str, Any]:
        """
        获取所有DID列表

        Returns:
            包含所有DID的字典
        """
        logger.info("🚀 开始获取所有DID列表")
        logger.info("=" * 60)

        all_dids = {
            "retrieved_at": datetime.now().isoformat(),
            "issuer": {
                "admin_url": self.issuer_admin_url,
                "dids": []
            },
            "holder": {
                "admin_url": self.holder_admin_url,
                "dids": []
            },
            "summary": {}
        }

        # 检查连接
        if not self.check_connection(self.issuer_admin_url, "发行者"):
            logger.error("❌ 无法连接到发行者ACA-Py")
            return all_dids

        if not self.check_connection(self.holder_admin_url, "持有者"):
            logger.error("❌ 无法连接到持有者ACA-Py")
            return all_dids

        # 获取发行者DID列表
        issuer_dids = self.get_did_list(self.issuer_admin_url, "issuer")
        all_dids["issuer"]["dids"] = issuer_dids
        all_dids["issuer"]["count"] = len(issuer_dids)

        # 获取持有者DID列表
        holder_dids = self.get_did_list(self.holder_admin_url, "holder")
        all_dids["holder"]["dids"] = holder_dids
        all_dids["holder"]["count"] = len(holder_dids)

        # 生成摘要
        total_dids = len(issuer_dids) + len(holder_dids)

        # 统计DID方法
        did_methods = {}
        for did in issuer_dids + holder_dids:
            method = did.get("method", "unknown")
            did_methods[method] = did_methods.get(method, 0) + 1

        all_dids["summary"] = {
            "total_dids": total_dids,
            "issuer_count": len(issuer_dids),
            "holder_count": len(holder_dids),
            "did_methods": did_methods
        }

        return all_dids

    def save_results(self, data: Dict[str, Any]) -> str:
        """保存结果到JSON文件"""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ 结果已保存到: {self.output_file}")
            return self.output_file
        except Exception as e:
            logger.error(f"❌ 保存结果时出错: {e}")
            return ""

    def print_summary(self, data: Dict[str, Any]):
        """打印获取摘要"""
        summary = data.get("summary", {})
        issuer_dids = data.get("issuer", {}).get("dids", [])
        holder_dids = data.get("holder", {}).get("dids", [])

        print("\n" + "=" * 60)
        print("📊 DID列表摘要")
        print("=" * 60)
        print(f"获取时间: {data.get('retrieved_at', 'Unknown')}")
        print(f"总DID数量: {summary.get('total_dids', 0)}")
        print(f"发行者DID: {summary.get('issuer_count', 0)} 个")
        print(f"持有者DID: {summary.get('holder_count', 0)} 个")
        print(f"DID方法: {summary.get('did_methods', {})}")

        if issuer_dids:
            print("\n🔑 发行者DID (前5个):")
            for did in issuer_dids[:5]:
                did_id = did.get('did', 'Unknown')
                posture = did.get('posture', 'Unknown')
                print(f"  {did_id} (状态: {posture})")
            if len(issuer_dids) > 5:
                print(f"  ... 还有 {len(issuer_dids) - 5} 个")

        if holder_dids:
            print("\n🔑 持有者DID (前5个):")
            for did in holder_dids[:5]:
                did_id = did.get('did', 'Unknown')
                posture = did.get('posture', 'Unknown')
                print(f"  {did_id} (状态: {posture})")
            if len(holder_dids) > 5:
                print(f"  ... 还有 {len(holder_dids) - 5} 个")

        print("=" * 60)

    def run(self):
        """运行完整的获取流程"""
        try:
            # 获取所有DID
            all_dids_data = self.retrieve_all_dids()

            # 保存结果
            self.save_results(all_dids_data)

            # 打印摘要
            self.print_summary(all_dids_data)

            logger.info("🎉 DID列表获取完成！")

            return all_dids_data

        except Exception as e:
            logger.error(f"❌ 获取过程中出现错误: {e}")
            raise


def load_config(config_file: str = "config/cross_chain_vc_config.json") -> Dict[str, Any]:
    """加载配置文件"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ 无法加载配置文件 {config_file}: {e}")
        return {}


def main():
    """主函数"""
    print("📋 获取所有DID列表工具")
    print("=" * 60)
    print()

    # 加载配置
    config = load_config()
    if config:
        issuer_url = config.get("acapy_services", {}).get("issuer", {}).get("admin_url", "http://localhost:8080")
        holder_url = config.get("acapy_services", {}).get("holder", {}).get("admin_url", "http://localhost:8081")
    else:
        issuer_url = "http://localhost:8080"
        holder_url = "http://localhost:8081"

    # 创建获取器
    retriever = DIDListRetriever(
        issuer_admin_url=issuer_url,
        holder_admin_url=holder_url,
        output_file="all_dids_list.json"
    )

    # 运行获取
    retriever.run()


if __name__ == "__main__":
    main()
