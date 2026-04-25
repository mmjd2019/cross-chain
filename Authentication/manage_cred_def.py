#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Credential Definition 管理程序

功能：
1. 检查 Schema 是否存在
2. 检查 CredDef 是否在钱包中可用
3. 如果 CredDef 不可用，自动创建新的 CredDef

使用方法：
    python3 manage_cred_def.py                    # 交互式管理
    python3 manage_cred_def.py --check            # 仅检查状态
    python3 manage_cred_def.py --create           # 强制创建新 CredDef
    python3 manage_cred_def.py --list             # 列出所有钱包中的 CredDef
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class CredDefManager:
    """Credential Definition 管理类"""

    def __init__(self, config_path: Optional[str] = None):
        """初始化管理器"""
        self.config = self._load_config(config_path)
        self.issuer_admin_url = self.config.get('issuer', {}).get('admin_url', 'http://localhost:8080')

        # 默认的 Schema 定义
        self.default_schemas = {
            "InspectionReport": {
                "schema_name": "InspectionReport",
                "schema_version": "2.0.0",
                "attributes": [
                    "exporter",
                    "contractName",
                    "productName",
                    "productQuantity",
                    "productBatch",
                    "inspectionPassed",
                    "Date"
                ]
            },
            "InsuranceContract": {
                "schema_name": "InsuranceContract",
                "schema_version": "1.0",
                "attributes": [
                    "exporter",
                    "importer",
                    "contractName",
                    "productName",
                    "productQuantity",
                    "productBatch",
                    "insuranceAmount",
                    "insuranceCompany",
                    "isInsured",
                    "Date"
                ]
            },
            "CertificateOfOrigin": {
                "schema_name": "CertificateOfOrigin",
                "schema_version": "1.0",
                "attributes": [
                    "exporter",
                    "importer",
                    "certifier",
                    "contractName",
                    "productName",
                    "productQuantity",
                    "productBatch",
                    "placeOfOrigin",
                    "Date"
                ]
            },
            "BillOfLadingCertificate": {
                "schema_name": "BillOfLadingCertificate",
                "schema_version": "1.0",
                "attributes": [
                    "exporter",
                    "shippingCompany",
                    "contractName",
                    "productName",
                    "productQuantity",
                    "productBatch",
                    "portOfDeparture",
                    "portOfArrival",
                    "departureDate",
                    "scheduledArrivalDate"
                ]
            }
        }

    def _load_config(self, config_path: Optional[str] = None) -> Dict:
        """加载配置文件"""
        if config_path:
            path = Path(config_path)
        else:
            script_dir = Path(__file__).parent
            path = script_dir.parent / "config" / "vc_config.json"

        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)

        # 默认配置
        return {
            "issuer": {
                "admin_url": "http://localhost:8080"
            }
        }

    def _get_issuer_did(self) -> Optional[str]:
        """获取 Issuer 的公共 DID"""
        try:
            resp = requests.get(f"{self.issuer_admin_url}/wallet/did/public", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('result', {}).get('did')
        except Exception as e:
            logger.error(f"获取 Issuer DID 失败: {e}")
        return None

    # ==================== Schema 管理 ====================

    def list_schemas_in_wallet(self) -> List[Dict]:
        """列出钱包中的所有 Schema"""
        try:
            resp = requests.get(f"{self.issuer_admin_url}/schemas/created", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('schema_ids', [])
        except Exception as e:
            logger.error(f"查询 Schema 失败: {e}")
        return []

    def get_schema_by_name(self, schema_name: str, schema_version: str = None) -> Optional[str]:
        """通过名称查找 Schema ID"""
        try:
            params = {"schema_name": schema_name}
            if schema_version:
                params["schema_version"] = schema_version

            resp = requests.get(
                f"{self.issuer_admin_url}/schemas/created",
                params=params,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                schema_ids = data.get('schema_ids', [])
                if schema_ids:
                    return schema_ids[0]  # 返回第一个匹配的
        except Exception as e:
            logger.error(f"查询 Schema 失败: {e}")
        return None

    def create_schema(self, schema_name: str, schema_version: str, attributes: List[str]) -> Optional[str]:
        """创建 Schema"""
        payload = {
            "schema_name": schema_name,
            "schema_version": schema_version,
            "attributes": attributes
        }

        try:
            resp = requests.post(
                f"{self.issuer_admin_url}/schemas",
                json=payload,
                timeout=30
            )
            if resp.status_code in [200, 201]:
                data = resp.json()
                schema_id = data.get('schema_id') or data.get('sent', {}).get('schema_id')
                logger.info(f"  ✓ Schema 创建成功: {schema_id}")
                return schema_id
            else:
                logger.error(f"  ✗ Schema 创建失败: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"  ✗ Schema 创建异常: {e}")
        return None

    def ensure_schema_exists(self, schema_name: str, schema_version: str = None, attributes: List[str] = None) -> Optional[str]:
        """确保 Schema 存在，不存在则创建"""
        # 检查是否存在
        existing_schema = self.get_schema_by_name(schema_name, schema_version)
        if existing_schema:
            logger.info(f"  ✓ Schema 已存在: {existing_schema}")
            return existing_schema

        # 不存在则创建
        logger.info(f"  Schema 不存在，正在创建...")
        if not schema_version:
            schema_version = "1.0"
        if not attributes:
            # 使用默认属性
            schema_def = self.default_schemas.get(schema_name, {})
            attributes = schema_def.get('attributes', [])

        if not attributes:
            logger.error(f"  ✗ 缺少 Schema 属性定义")
            return None

        return self.create_schema(schema_name, schema_version, attributes)

    # ==================== CredDef 管理 ====================

    def list_cred_defs_in_wallet(self) -> List[str]:
        """列出钱包中的所有 CredDef"""
        try:
            resp = requests.get(f"{self.issuer_admin_url}/credential-definitions/created", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('credential_definition_ids', [])
        except Exception as e:
            logger.error(f"查询 CredDef 失败: {e}")
        return []

    def check_cred_def_on_ledger(self, cred_def_id: str) -> bool:
        """检查 CredDef 是否在 Ledger 上存在"""
        try:
            resp = requests.get(
                f"{self.issuer_admin_url}/credential-definitions/{cred_def_id}",
                timeout=10
            )
            return resp.status_code == 200
        except Exception:
            return False

    def check_cred_def_in_wallet(self, cred_def_id: str) -> bool:
        """检查 CredDef 是否在钱包中可用"""
        cred_defs = self.list_cred_defs_in_wallet()
        return cred_def_id in cred_defs

    def get_cred_def_info(self, cred_def_id: str) -> Optional[Dict]:
        """获取 CredDef 详细信息"""
        try:
            resp = requests.get(
                f"{self.issuer_admin_url}/credential-definitions/{cred_def_id}",
                timeout=10
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"获取 CredDef 信息失败: {e}")
        return None

    def create_cred_def(self, schema_id: str, tag: str, support_revocation: bool = False) -> Optional[str]:
        """创建 Credential Definition"""
        payload = {
            "schema_id": schema_id,
            "tag": tag,
            "support_revocation": support_revocation
        }

        try:
            logger.info(f"  正在创建 CredDef...")
            logger.info(f"    Schema ID: {schema_id}")
            logger.info(f"    Tag: {tag}")

            resp = requests.post(
                f"{self.issuer_admin_url}/credential-definitions",
                json=payload,
                timeout=60  # CredDef 创建可能需要较长时间
            )
            if resp.status_code in [200, 201]:
                data = resp.json()
                cred_def_id = data.get('credential_definition_id') or data.get('sent', {}).get('credential_definition_id')
                logger.info(f"  ✓ CredDef 创建成功: {cred_def_id}")
                return cred_def_id
            else:
                logger.error(f"  ✗ CredDef 创建失败: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"  ✗ CredDef 创建异常: {e}")
        return None

    def ensure_cred_def_exists(self, schema_id: str, tag: str, support_revocation: bool = False) -> Optional[str]:
        """确保 CredDef 存在且可用，不存在则创建"""
        issuer_did = self._get_issuer_did()
        if not issuer_did:
            logger.error("  ✗ 无法获取 Issuer DID")
            return None

        # 构建预期的 CredDef ID
        # 格式: {did}:3:CL:{seq_no}:{tag}
        # 但我们不知道 seq_no，所以需要搜索

        # 先检查钱包中是否有匹配 schema 和 tag 的 CredDef
        cred_defs = self.list_cred_defs_in_wallet()
        for cred_def_id in cred_defs:
            # 检查是否匹配 schema 和 tag
            info = self.get_cred_def_info(cred_def_id)
            if info:
                cred_def = info.get('credential_definition', {})
                if cred_def.get('schema_id') == schema_id and cred_def.get('tag') == tag:
                    logger.info(f"  ✓ CredDef 已存在于钱包中: {cred_def_id}")
                    return cred_def_id

        # 钱包中没有，需要创建
        logger.info(f"  CredDef 不在钱包中，正在创建...")
        return self.create_cred_def(schema_id, tag, support_revocation)

    # ==================== 高级功能 ====================

    def check_status(self) -> Dict:
        """检查 ACA-Py 状态和所有资源"""
        result = {
            'issuer_url': self.issuer_admin_url,
            'issuer_did': None,
            'schemas': [],
            'cred_defs_in_wallet': [],
            'cred_defs_status': {}
        }

        logger.info("=" * 60)
        logger.info("  Credential Definition 状态检查")
        logger.info("=" * 60)

        # 检查服务状态
        try:
            resp = requests.get(f"{self.issuer_admin_url}/status", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"\n[服务状态]")
                logger.info(f"  ✓ ACA-Py 运行中 (版本 {data.get('version', 'unknown')})")
            else:
                logger.error(f"  ✗ ACA-Py 响应异常: {resp.status_code}")
                return result
        except Exception as e:
            logger.error(f"  ✗ 无法连接 ACA-Py: {e}")
            return result

        # 获取 Issuer DID
        result['issuer_did'] = self._get_issuer_did()
        logger.info(f"\n[Issuer DID]")
        if result['issuer_did']:
            logger.info(f"  {result['issuer_did']}")
        else:
            logger.warning(f"  未找到公共 DID")

        # 列出 Schema
        result['schemas'] = self.list_schemas_in_wallet()
        logger.info(f"\n[Schema 列表] (钱包中: {len(result['schemas'])}个)")
        for schema_id in result['schemas']:
            logger.info(f"  - {schema_id}")

        # 列出 CredDef
        result['cred_defs_in_wallet'] = self.list_cred_defs_in_wallet()
        logger.info(f"\n[CredDef 列表] (钱包中: {len(result['cred_defs_in_wallet'])}个)")
        for cred_def_id in result['cred_defs_in_wallet']:
            logger.info(f"  - {cred_def_id}")

        # 检查默认 Schema 的 CredDef 状态
        logger.info(f"\n[默认 Schema 的 CredDef 状态]")
        for schema_name, schema_def in self.default_schemas.items():
            schema_id = self.get_schema_by_name(schema_name, schema_def.get('schema_version'))
            if schema_id:
                # 检查是否有对应的 CredDef
                found = False
                for cred_def_id in result['cred_defs_in_wallet']:
                    info = self.get_cred_def_info(cred_def_id)
                    if info:
                        cred_def = info.get('credential_definition', {})
                        if cred_def.get('schema_id') == schema_id:
                            logger.info(f"  {schema_name}: ✓ {cred_def_id}")
                            result['cred_defs_status'][schema_name] = {
                                'status': 'available',
                                'cred_def_id': cred_def_id
                            }
                            found = True
                            break
                if not found:
                    logger.info(f"  {schema_name}: ⚠ Schema存在，但无可用CredDef")
                    result['cred_defs_status'][schema_name] = {
                        'status': 'no_cred_def',
                        'schema_id': schema_id
                    }
            else:
                logger.info(f"  {schema_name}: ✗ Schema不存在")
                result['cred_defs_status'][schema_name] = {
                    'status': 'no_schema'
                }

        logger.info("\n" + "=" * 60)
        return result

    def interactive_create(self, schema_name: str = None, tag: str = None):
        """交互式创建 Schema 和 CredDef"""
        logger.info("=" * 60)
        logger.info("  交互式创建 Schema 和 CredDef")
        logger.info("=" * 60)

        # 如果没有指定 schema_name，让用户选择
        if not schema_name:
            logger.info("\n可用的 Schema 类型:")
            for i, (name, defn) in enumerate(self.default_schemas.items(), 1):
                logger.info(f"  {i}. {name}")
            logger.info(f"  {len(self.default_schemas) + 1}. 自定义 Schema")

            try:
                choice = int(input("\n请选择 (输入数字): ").strip())
                if 1 <= choice <= len(self.default_schemas):
                    schema_name = list(self.default_schemas.keys())[choice - 1]
                elif choice == len(self.default_schemas) + 1:
                    schema_name = input("输入 Schema 名称: ").strip()
                else:
                    logger.error("无效选择")
                    return None
            except (ValueError, EOFError):
                logger.error("无效输入")
                return None

        # 获取 Schema 定义
        schema_def = self.default_schemas.get(schema_name, {})
        schema_version = schema_def.get('schema_version', '1.0')
        attributes = schema_def.get('attributes', [])

        if not attributes:
            logger.error(f"未找到 {schema_name} 的属性定义，请手动输入")
            attrs_input = input("输入属性 (逗号分隔): ").strip()
            attributes = [a.strip() for a in attrs_input.split(',') if a.strip()]

        # 确保 Schema 存在
        logger.info(f"\n[步骤1] 检查/创建 Schema")
        schema_id = self.ensure_schema_exists(schema_name, schema_version, attributes)
        if not schema_id:
            logger.error("Schema 创建失败")
            return None

        # 如果没有指定 tag，使用默认 tag 或让用户输入
        if not tag:
            default_tag = schema_name
            tag_input = input(f"\n输入 CredDef Tag (默认: {default_tag}): ").strip()
            tag = tag_input if tag_input else default_tag

        # 创建 CredDef
        logger.info(f"\n[步骤2] 创建 CredDef")
        cred_def_id = self.ensure_cred_def_exists(schema_id, tag)

        if cred_def_id:
            logger.info("\n" + "=" * 60)
            logger.info("  创建完成!")
            logger.info("=" * 60)
            logger.info(f"  Schema ID:  {schema_id}")
            logger.info(f"  CredDef ID: {cred_def_id}")
            logger.info("=" * 60)
            return cred_def_id

        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Credential Definition 管理程序',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 manage_cred_def.py                    # 交互式管理
  python3 manage_cred_def.py --check            # 仅检查状态
  python3 manage_cred_def.py --list             # 列出所有 CredDef
  python3 manage_cred_def.py --create           # 强制创建新 CredDef
  python3 manage_cred_def.py --create --schema InspectionReport --tag mytag
        """
    )
    parser.add_argument('--check', action='store_true', help='仅检查状态')
    parser.add_argument('--list', action='store_true', help='列出所有 CredDef')
    parser.add_argument('--create', action='store_true', help='创建 CredDef')
    parser.add_argument('--schema', type=str, help='Schema 名称')
    parser.add_argument('--tag', type=str, help='CredDef Tag')
    parser.add_argument('--config', type=str, help='配置文件路径')

    args = parser.parse_args()

    manager = CredDefManager(args.config)

    if args.check:
        manager.check_status()
    elif args.list:
        cred_defs = manager.list_cred_defs_in_wallet()
        logger.info("钱包中的 CredDef:")
        for cred_def_id in cred_defs:
            logger.info(f"  - {cred_def_id}")
    elif args.create:
        if args.schema:
            manager.interactive_create(args.schema, args.tag)
        else:
            manager.interactive_create()
    else:
        # 默认：显示状态并询问是否创建
        status = manager.check_status()

        # 检查是否有不可用的 CredDef
        need_create = []
        for schema_name, info in status.get('cred_defs_status', {}).items():
            if info.get('status') in ['no_cred_def', 'no_schema']:
                need_create.append(schema_name)

        if need_create:
            logger.info(f"\n以下 Schema 需要创建 CredDef: {', '.join(need_create)}")
            try:
                choice = input("是否创建? (y/n): ").strip().lower()
                if choice == 'y':
                    for schema_name in need_create:
                        manager.interactive_create(schema_name)
            except (EOFError, KeyboardInterrupt):
                logger.info("\n已取消")


if __name__ == "__main__":
    main()
