#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量生成DID脚本
根据种子范围创建多个DID并保存到JSON文件
"""

import json
import requests
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BatchDIDGenerator:
    """批量DID生成器"""

    def __init__(self,
                 issuer_admin_url: str = "http://localhost:8080",
                 holder_admin_url: str = "http://localhost:8081",
                 start_seed: str = "000000000000000000000000002Agent",
                 count: int = 100,
                 output_file: str = "generated_dids.json"):
        """
        初始化批量DID生成器

        Args:
            issuer_admin_url: 发行者ACA-Py管理API地址
            holder_admin_url: 持有者ACA-Py管理API地址
            start_seed: 起始种子 (格式: 000000000000000000000000002Agent)
            count: 要生成的DID数量
            output_file: 输出JSON文件名
        """
        self.issuer_admin_url = issuer_admin_url.rstrip('/')
        self.holder_admin_url = holder_admin_url.rstrip('/')
        self.start_seed = start_seed
        self.count = count
        self.output_file = output_file
        self.results: List[Dict[str, Any]] = []

        logger.info(f"初始化批量DID生成器")
        logger.info(f"  发行者: {self.issuer_admin_url}")
        logger.info(f"  持有者: {self.holder_admin_url}")
        logger.info(f"  起始种子: {self.start_seed}")
        logger.info(f"  生成数量: {self.count}")
        logger.info(f"  输出文件: {self.output_file}")

    def check_connection(self, admin_url: str, name: str) -> bool:
        """检查ACA-Py连接"""
        try:
            logger.info(f"🔍 检查{name}连接...")
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

    def create_did_with_seed(self, admin_url: str, seed: str, role: str) -> Optional[Dict[str, Any]]:
        """
        使用指定种子创建DID

        Args:
            admin_url: ACA-Py管理API地址
            seed: DID种子
            role: 角色 (issuer 或 holder)

        Returns:
            包含DID信息的字典，如果失败则返回None
        """
        try:
            # 准备创建DID的数据
            did_data = {
                "seed": seed,
                "method": "did:sov",
                "options": {
                    "did_method": "sov"
                }
            }

            # 调用ACA-Py API创建DID (使用正确的端点 /wallet/did/create)
            response = requests.post(
                f"{admin_url}/wallet/did/create",
                json=did_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            if response.status_code in [200, 201]:
                result = response.json()
                did_info = {
                    "seed": seed,
                    "did": result.get('result', {}).get('did'),
                    "verkey": result.get('result', {}).get('verkey'),
                    "role": role,
                    "created_at": datetime.now().isoformat(),
                    "success": True
                }
                logger.info(f"✅ {role} DID创建成功: {did_info['did']} (种子: {seed})")
                return did_info
            else:
                error_info = {
                    "seed": seed,
                    "role": role,
                    "error": f"HTTP {response.status_code}",
                    "response": response.text,
                    "success": False,
                    "created_at": datetime.now().isoformat()
                }
                logger.error(f"❌ {role} DID创建失败 (种子: {seed}): HTTP {response.status_code}")
                logger.error(f"响应: {response.text}")
                return error_info

        except requests.exceptions.RequestException as e:
            error_info = {
                "seed": seed,
                "role": role,
                "error": str(e),
                "success": False,
                "created_at": datetime.now().isoformat()
            }
            logger.error(f"❌ {role} DID创建时出错 (种子: {seed}): {e}")
            return error_info

    def generate_seed_sequence(self, start_seed: str, count: int) -> List[str]:
        """
        生成种子序列

        Args:
            start_seed: 起始种子 (格式: 000000000000000000000000002Agent)
            count: 要生成的种子数量

        Returns:
            种子列表
        """
        seeds = []

        # 解析起始种子
        # 格式: 000000000000000000000000002Agent
        # 前25个字符是前缀，然后是数字，最后是"Agent"
        prefix = start_seed[:25]  # 0000000000000000000000000
        suffix = start_seed[-5:]  # Agent

        # 提取数字部分
        number_part = start_seed[25:-5]  # 002
        start_number = int(number_part)

        logger.info(f"📝 生成种子序列:")
        logger.info(f"  前缀: {prefix}")
        logger.info(f"  起始数字: {start_number}")
        logger.info(f"  后缀: {suffix}")
        logger.info(f"  数量: {count}")

        for i in range(count):
            number = start_number + i
            # 格式化数字为3位，前面补零
            number_str = str(number).zfill(3)
            seed = f"{prefix}{number_str}{suffix}"
            seeds.append(seed)

        return seeds

    def generate_batch_dids(self, role: str = "both") -> List[Dict[str, Any]]:
        """
        批量生成DID

        Args:
            role: 要生成的角色 ("issuer", "holder", 或 "both")

        Returns:
            生成的DID信息列表
        """
        logger.info("🚀 开始批量生成DID")
        logger.info("=" * 60)

        # 生成种子序列
        seeds = self.generate_seed_sequence(self.start_seed, self.count)

        # 确定要处理的角色
        roles_to_process = []
        if role == "issuer":
            roles_to_process = [("issuer", self.issuer_admin_url)]
        elif role == "holder":
            roles_to_process = [("holder", self.holder_admin_url)]
        else:  # both
            roles_to_process = [
                ("issuer", self.issuer_admin_url),
                ("holder", self.holder_admin_url)
            ]

        all_results = []

        # 为每个种子和每个角色创建DID
        for seed in seeds:
            logger.info(f"\n🔐 处理种子: {seed}")

            for role_name, admin_url in roles_to_process:
                # 检查是否为发行者且种子以特定模式开头（可选的过滤逻辑）
                did_info = self.create_did_with_seed(admin_url, seed, role_name)
                all_results.append(did_info)

                # 添加小延迟避免API过载
                time.sleep(0.1)

        self.results = all_results
        return all_results

    def save_results(self) -> str:
        """保存结果到JSON文件"""
        # 统计信息
        successful = [r for r in self.results if r.get('success', False)]
        failed = [r for r in self.results if not r.get('success', False)]

        summary = {
            "generated_at": datetime.now().isoformat(),
            "total_attempts": len(self.results),
            "successful": len(successful),
            "failed": len(failed),
            "start_seed": self.start_seed,
            "count": self.count,
            "dids": self.results
        }

        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ 结果已保存到: {self.output_file}")
            return self.output_file
        except Exception as e:
            logger.error(f"❌ 保存结果时出错: {e}")
            return ""

    def print_summary(self):
        """打印生成摘要"""
        successful = [r for r in self.results if r.get('success', False)]
        failed = [r for r in self.results if not r.get('success', False)]

        print("\n" + "=" * 60)
        print("📊 生成摘要")
        print("=" * 60)
        print(f"总尝试次数: {len(self.results)}")
        print(f"成功数量: {len(successful)}")
        print(f"失败数量: {len(failed)}")
        print(f"成功率: {len(successful) / len(self.results) * 100:.2f}%")

        if successful:
            print("\n✅ 成功的DID (前5个):")
            for did_info in successful[:5]:
                print(f"  [{did_info['role']}] {did_info['did']} (种子: {did_info['seed']})")
            if len(successful) > 5:
                print(f"  ... 还有 {len(successful) - 5} 个")

        if failed:
            print("\n❌ 失败的DID (前5个):")
            for did_info in failed[:5]:
                print(f"  [{did_info['role']}] 种子: {did_info['seed']}, 错误: {did_info.get('error', 'Unknown')}")
            if len(failed) > 5:
                print(f"  ... 还有 {len(failed) - 5} 个")

        print("=" * 60)

    def run(self, role: str = "both"):
        """
        运行完整的批量生成流程

        Args:
            role: 要生成的角色 ("issuer", "holder", 或 "both")
        """
        try:
            # 检查连接
            if not self.check_connection(self.issuer_admin_url, "发行者"):
                logger.error("❌ 无法连接到发行者ACA-Py")
                return

            if not self.check_connection(self.holder_admin_url, "持有者"):
                logger.error("❌ 无法连接到持有者ACA-Py")
                return

            # 批量生成DID
            self.generate_batch_dids(role)

            # 保存结果
            self.save_results()

            # 打印摘要
            self.print_summary()

            logger.info("🎉 批量DID生成完成！")

        except Exception as e:
            logger.error(f"❌ 生成过程中出现错误: {e}")
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
    print("🔐 批量DID生成工具")
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

    # 创建生成器
    generator = BatchDIDGenerator(
        issuer_admin_url=issuer_url,
        holder_admin_url=holder_url,
        start_seed="000000000000000000000000002Agent",
        count=100,
        output_file="generated_dids.json"
    )

    # 运行生成（可以指定 "issuer", "holder", 或 "both"）
    # 默认为 "both"，即为发行者和持有者都生成
    generator.run(role="both")


if __name__ == "__main__":
    main()
