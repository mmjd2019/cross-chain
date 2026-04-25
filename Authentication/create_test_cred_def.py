#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速创建InspectionReport的Schema和CredDef
在当前的ACA-Py 1.2.0实例上创建
"""

import requests
import json
import time

# 配置
ISSUER_ADMIN_URL = "http://localhost:8080"
SCHEMA_NAME = "InspectionReport"
SCHEMA_VERSION = "1.0.1"  # 使用新版本避免冲突
ATTRIBUTES = ["exporter", "contractName", "productName", "productQuantity", "productBatch", "inspectionPassed", "Date"]

# 获取Issuer DID
print("1. 获取Issuer DID...")
resp = requests.get(f"{ISSUER_ADMIN_URL}/wallet/did", timeout=10)
dids = resp.json().get('results', [])
issuer_did = None
for did_info in dids:
    if did_info.get('posture') == 'posted':
        issuer_did = did_info['did']
        break

if not issuer_did:
    # 使用第一个DID并发布
    issuer_did = dids[0]['did']
    print(f"  发布DID: {issuer_did}")
    resp = requests.post(
        f"{ISSUER_ADMIN_URL}/ledger/register-nym",
        params={"did": issuer_did, "verkey": dids[0]['verkey']},
        timeout=30
    )
    if resp.status_code in [200, 201]:
        print(f"  ✓ DID发布成功")
    time.sleep(2)

print(f"  ✓ Issuer DID: {issuer_did}")

# 创建Schema
print(f"\n2. 创建Schema: {SCHEMA_NAME} v{SCHEMA_VERSION}")
schema_payload = {
    "schema_name": SCHEMA_NAME,
    "schema_version": SCHEMA_VERSION,
    "attributes": ATTRIBUTES
}

resp = requests.post(
    f"{ISSUER_ADMIN_URL}/schemas",
    json=schema_payload,
    timeout=60
)

if resp.status_code in [200, 201]:
    schema_data = resp.json()
    schema_id = schema_data.get('schema_id')
    print(f"  ✓ Schema创建成功: {schema_id}")
else:
    print(f"  ✗ Schema创建失败: {resp.status_code} - {resp.text}")
    exit(1)

# 等待Schema上链
print("  等待Schema上链...")
time.sleep(5)

# 创建CredDef
print(f"\n3. 创建Credential Definition...")
cred_def_payload = {
    "schema_id": schema_id,
    "tag": SCHEMA_NAME,
    "support_revocation": False
}

resp = requests.post(
    f"{ISSUER_ADMIN_URL}/credential-definitions",
    json=cred_def_payload,
    timeout=60
)

if resp.status_code in [200, 201]:
    cred_def_data = resp.json()
    cred_def_id = cred_def_data.get('credential_definition_id')
    print(f"  ✓ Credential Definition创建成功!")
    print(f"     Schema ID: {schema_id}")
    print(f"     CredDef ID: {cred_def_id}")

    # 保存到文件
    result = {
        "schema_id": schema_id,
        "cred_def_id": cred_def_id,
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "attributes": ATTRIBUTES
    }

    with open("test_cred_def_result.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n  ✓ 结果已保存到 test_cred_def_result.json")
    print(f"\n请更新simple_vc_issuance_test.py中的cred_def_id:")
    print(f'  self.cred_def_id = "{cred_def_id}"')

else:
    print(f"  ✗ Credential Definition创建失败: {resp.status_code} - {resp.text}")
    exit(1)
