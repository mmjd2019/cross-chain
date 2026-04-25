#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量创建Schema和CredDef

使用方法:
    python3 create_all_creddefs.py              # 创建所有Schema和CredDef V6
    python3 create_all_creddefs.py --version V7 # 指定版本号
"""

import argparse
import json
import time
import requests

ISSUER_URL = "http://localhost:8080"
ISSUER_DID = "DPvobytTtKvmyeRTJZYjsg"

# Schema定义
SCHEMAS = {
    "InspectionReport": {
        "version": "2.0.0",
        "attributes": ["exporter", "contractName", "productName", "productQuantity",
                       "productBatch", "inspectionPassed", "Date"]
    },
    "InsuranceContract": {
        "version": "1.0.0",
        "attributes": ["exporter", "importer", "contractName", "productName",
                       "productQuantity", "productBatch", "insuranceAmount",
                       "insuranceCompany", "isInsured", "Date"]
    },
    "CertificateOfOrigin": {
        "version": "1.0.0",
        "attributes": ["exporter", "importer", "certifier", "contractName",
                       "productName", "productQuantity", "productBatch",
                       "placeOfOrigin", "Date"]
    },
    "BillOfLadingCertificate": {
        "version": "1.0.0",
        "attributes": ["exporter", "shippingCompany", "contractName", "productName",
                       "productQuantity", "productBatch", "portOfDeparture",
                       "portOfArrival", "departureDate", "scheduledArrivalDate"]
    }
}


def create_schema(schema_name: str, schema_def: dict) -> str:
    """创建Schema"""
    print(f"  创建Schema: {schema_name} v{schema_def['version']}")

    payload = {
        "schema_name": schema_name,
        "schema_version": schema_def["version"],
        "attributes": schema_def["attributes"]
    }

    resp = requests.post(
        f"{ISSUER_URL}/schemas",
        json=payload,
        timeout=30
    )

    if resp.status_code in [200, 201]:
        data = resp.json()
        schema_id = data.get("schema_id")
        print(f"    ✅ Schema ID: {schema_id}")
        return schema_id
    else:
        print(f"    ❌ 创建失败: {resp.status_code} - {resp.text}")
        return None


def get_existing_schema(schema_name: str) -> str:
    """尝试获取现有Schema"""
    # 尝试不同的版本号
    for version in ["2.0.0", "1.0.0"]:
        schema_id = f"{ISSUER_DID}:2:{schema_name}:{version}"
        resp = requests.get(f"{ISSUER_URL}/schemas/{schema_id}", timeout=10)
        if resp.status_code == 200:
            print(f"    找到现有Schema: {schema_id}")
            return schema_id
    return None


def create_cred_def(schema_id: str, tag: str) -> str:
    """创建CredDef"""
    print(f"  创建CredDef: {tag}")

    payload = {
        "schema_id": schema_id,
        "tag": tag
    }

    resp = requests.post(
        f"{ISSUER_URL}/credential-definitions",
        json=payload,
        timeout=30
    )

    if resp.status_code in [200, 201]:
        data = resp.json()
        cred_def_id = data.get("credential_definition_id")
        print(f"    ✅ CredDef ID: {cred_def_id}")
        return cred_def_id
    else:
        print(f"    ❌ 创建失败: {resp.status_code} - {resp.text}")
        return None


def get_existing_creddef(schema_id: str, tag: str) -> str:
    """检查CredDef是否已存在"""
    resp = requests.get(f"{ISSUER_URL}/credential-definitions/created", timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        for cred_def_id in data.get("credential_definition_ids", []):
            if tag in cred_def_id and schema_id.split(":")[3] in cred_def_id:
                print(f"    找到现有CredDef: {cred_def_id}")
                return cred_def_id
    return None


def main():
    parser = argparse.ArgumentParser(description='批量创建Schema和CredDef')
    parser.add_argument('--version', '-v', type=str, default='V6',
                        help='CredDef版本标签 (默认: V6)')
    parser.add_argument('--skip-schema', action='store_true',
                        help='跳过Schema创建，只创建CredDef')

    args = parser.parse_args()

    print("=" * 60)
    print(f" 批量创建Schema和CredDef (版本: {args.version})")
    print("=" * 60)

    results = {}

    for schema_name, schema_def in SCHEMAS.items():
        print(f"\n[{schema_name}]")

        # 获取或创建Schema
        if args.skip_schema:
            schema_id = get_existing_schema(schema_name)
            if not schema_id:
                print(f"    ⚠️ 跳过Schema创建但未找到现有Schema，尝试创建...")
                schema_id = create_schema(schema_name, schema_def)
        else:
            schema_id = create_schema(schema_name, schema_def)

        if not schema_id:
            print(f"    ❌ 跳过 {schema_name}")
            continue

        time.sleep(1)

        # 创建CredDef
        tag = f"{schema_name}_{args.version}"
        cred_def_id = get_existing_creddef(schema_id, tag)
        if not cred_def_id:
            cred_def_id = create_cred_def(schema_id, tag)

        results[schema_name] = {
            "schema_id": schema_id,
            "cred_def_id": cred_def_id
        }

        time.sleep(1)

    # 输出结果汇总
    print("\n" + "=" * 60)
    print(" 创建结果汇总")
    print("=" * 60)

    for schema_name, info in results.items():
        print(f"\n{schema_name}:")
        print(f"  Schema ID:  {info['schema_id']}")
        print(f"  CredDef ID: {info['cred_def_id']}")

    # 保存到JSON文件
    output_file = f"creddef_{args.version.lower()}_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n结果已保存到: {output_file}")


if __name__ == "__main__":
    main()
