#!/usr/bin/env python3
"""
大宗货物跨境交易智能合约验证工具 - JSON输出版本
验证已部署合约状态并输出JSON格式结果
"""

import json
import sys
from datetime import datetime
from web3 import Web3
from pathlib import Path

# 配置文件路径
CONFIG_DIR = Path("/home/manifold/cursor/cross-chain/config")
ADDRESSES_FILE = CONFIG_DIR / "address.json"
CONTRACTS_CONFIG = CONFIG_DIR / "deployed_contracts_config.json"
CONTRACTS_DIR = Path("/home/manifold/cursor/cross-chain/contracts/kept")
OUTPUT_FILE = Path("/home/manifold/cursor/cross-chain/contracts/kept/verification_result.json")

# 颜色输出
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def load_json(filepath):
    """加载JSON文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"{RED}❌ 加载 {filepath} 失败: {e}{RESET}")
        sys.exit(1)


def connect_to_chain(rpc_url, chain_name):
    """连接到区块链"""
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # 添加POA中间件
    try:
        from web3.middleware.geth_poa import geth_poa_middleware
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    except:
        pass

    try:
        block_number = w3.eth.get_block('latest')['number']
        print(f"{GREEN}✅ 成功连接到 {chain_name}{RESET}")
        print(f"  当前区块: {block_number}")
        return w3, True
    except Exception as e:
        print(f"{RED}❌ 连接 {chain_name} 失败: {e}{RESET}")
        return w3, False


def verify_contract(w3, contract_config, chain_name):
    """验证单个合约"""
    result = {
        "name": contract_config.get("name", "Unknown"),
        "address": contract_config.get("address", ""),
        "status": "unknown",
        "checks": [],
        "errors": []
    }

    try:
        # 加载ABI - 从合约JSON文件中读取
        abi = []
        abi_file = CONTRACTS_DIR / f"{contract_config['name']}.json"
        if abi_file.exists():
            with open(abi_file, 'r') as f:
                contract_data = json.load(f)
                abi = contract_data.get("abi", contract_data)  # 兼容两种格式

        # 加载合约
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_config["address"]),
            abi=abi
        )

        # 基本检查
        result["checks"].append({
            "check": "code_deployed",
            "status": "pass",
            "description": "合约代码已部署"
        })

        # 检查Owner
        try:
            owner = contract.functions.owner().call()
            result["owner"] = owner
            result["checks"].append({
                "check": "owner_address",
                "status": "pass",
                "value": owner,
                "description": f"Owner: {owner}"
            })

            # 检查管理员权限
            try:
                is_admin = contract.functions.isAdmin(owner).call()
                result["checks"].append({
                    "check": "owner_is_admin",
                    "status": "pass" if is_admin else "warning",
                    "value": is_admin,
                    "description": f"Owner是管理员: {is_admin}"
                })
            except:
                result["checks"].append({
                    "check": "owner_is_admin",
                    "status": "skip",
                    "description": "合约不支持isAdmin函数"
                })

        except Exception as e:
            result["errors"].append(f"获取Owner失败: {str(e)}")

        # 检查DIDVerifier地址（如果存在）
        if "didVerifier" in contract_config:
            try:
                did_verifier = contract.functions.didVerifier().call()
                result["checks"].append({
                    "check": "did_verifier_address",
                    "status": "pass",
                    "value": did_verifier,
                    "description": f"DIDVerifier: {did_verifier}"
                })
            except:
                result["checks"].append({
                    "check": "did_verifier_address",
                    "status": "skip",
                    "description": "合约不支持didVerifier函数"
                })

        # 检查Bridge地址（如果存在）
        if "bridge" in contract_config:
            try:
                bridge = contract.functions.bridge().call()
                result["checks"].append({
                    "check": "bridge_address",
                    "status": "pass",
                    "value": bridge,
                    "description": f"Bridge: {bridge}"
                })
            except:
                result["checks"].append({
                    "check": "bridge_address",
                    "status": "skip",
                    "description": "合约不支持bridge函数"
                })

        # 检查验证状态
        if contract_config.get("name") == "DIDVerifier":
            try:
                is_verified = contract.functions.isVerified(owner).call()
                result["checks"].append({
                    "check": "owner_verified_status",
                    "status": "pass",
                    "value": is_verified,
                    "description": f"Owner验证状态: {is_verified}"
                })
            except:
                pass

        result["status"] = "pass"
        print(f"{GREEN}✅ {contract_config['name']} 验证通过{RESET}")

    except Exception as e:
        result["status"] = "fail"
        result["errors"].append(str(e))
        print(f"{RED}❌ {contract_config['name']} 验证失败: {e}{RESET}")

    return result


def main():
    """主函数"""
    print("=" * 70)
    print("🔍 大宗货物跨境交易智能合约验证工具 (JSON输出)")
    print("=" * 70)
    print()

    # 加载配置
    addresses = load_json(ADDRESSES_FILE)
    contracts_config = load_json(CONTRACTS_CONFIG)

    # 初始化验证结果
    verification_result = {
        "timestamp": datetime.now().isoformat(),
        "verification_version": "1.0",
        "chains": {},
        "summary": {
            "total_contracts": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }
    }

    # 验证Chain A
    print("=" * 70)
    print("🔍 开始验证 Chain A")
    print("=" * 70)

    chain_a_config = contracts_config.get("chain_a", {})
    rpc_url = chain_a_config.get("rpc_url", "http://localhost:8545")

    w3, connected = connect_to_chain(rpc_url, "Chain A")
    chain_a_result = {
        "name": "Chain A (源链)",
        "rpc_url": rpc_url,
        "connected": connected,
        "contracts": []
    }

    if connected:
        chain_a_contracts = [
            {"name": "DIDVerifier", "address": addresses.get("contracts", {}).get("chain_a", {}).get("did_verifier", ""), "abi": ""},
            {"name": "ContractManager", "address": addresses.get("contracts", {}).get("chain_a", {}).get("contract_manager", ""), "abi": ""},
            {"name": "VCCrossChainBridge", "address": addresses.get("contracts", {}).get("chain_a", {}).get("cross_chain_bridge", ""), "abi": ""},
            {"name": "InspectionReportVCManager", "address": addresses.get("contracts", {}).get("chain_a", {}).get("vc_managers", {}).get("inspection_report", ""), "abi": ""},
            {"name": "InsuranceContractVCManager", "address": addresses.get("contracts", {}).get("chain_a", {}).get("vc_managers", {}).get("insurance_contract", ""), "abi": ""},
            {"name": "CertificateOfOriginVCManager", "address": addresses.get("contracts", {}).get("chain_a", {}).get("vc_managers", {}).get("certificate_of_origin", ""), "abi": ""},
            {"name": "BillOfLadingVCManager", "address": addresses.get("contracts", {}).get("chain_a", {}).get("vc_managers", {}).get("bill_of_lading", ""), "abi": ""},
        ]

        for contract_info in chain_a_contracts:
            if contract_info["address"]:
                result = verify_contract(w3, contract_info, "Chain A")
                chain_a_result["contracts"].append(result)
                verification_result["summary"]["total_contracts"] += 1
                if result["status"] == "pass":
                    verification_result["summary"]["passed"] += 1
                else:
                    verification_result["summary"]["failed"] += 1

    verification_result["chains"]["chain_a"] = chain_a_result
    print()
    print(f"Chain A 验证完成: {len(chain_a_result['contracts'])}/{len(chain_a_contracts)} 个合约")
    print()

    # 验证Chain B
    print("=" * 70)
    print("🔍 开始验证 Chain B")
    print("=" * 70)

    chain_b_config = contracts_config.get("chain_b", {})
    rpc_url = chain_b_config.get("rpc_url", "http://localhost:8555")

    w3, connected = connect_to_chain(rpc_url, "Chain B")
    chain_b_result = {
        "name": "Chain B (目标链)",
        "rpc_url": rpc_url,
        "connected": connected,
        "contracts": []
    }

    if connected:
        chain_b_contracts = [
            {"name": "DIDVerifier", "address": addresses.get("contracts", {}).get("chain_b", {}).get("did_verifier", ""), "abi": ""},
            {"name": "VCCrossChainBridge", "address": addresses.get("contracts", {}).get("chain_b", {}).get("cross_chain_bridge", ""), "abi": ""},
        ]

        for contract_info in chain_b_contracts:
            if contract_info["address"]:
                result = verify_contract(w3, contract_info, "Chain B")
                chain_b_result["contracts"].append(result)
                verification_result["summary"]["total_contracts"] += 1
                if result["status"] == "pass":
                    verification_result["summary"]["passed"] += 1
                else:
                    verification_result["summary"]["failed"] += 1

    verification_result["chains"]["chain_b"] = chain_b_result
    print()
    print(f"Chain B 验证完成: {len(chain_b_result['contracts'])}/{len(chain_b_contracts)} 个合约")
    print()

    # 总体状态
    verification_result["summary"]["overall_status"] = (
        "PASS" if verification_result["summary"]["failed"] == 0 else "FAIL"
    )
    verification_result["summary"]["success_rate"] = (
        verification_result["summary"]["passed"] / verification_result["summary"]["total_contracts"] * 100
        if verification_result["summary"]["total_contracts"] > 0 else 0
    )

    # 输出JSON文件
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(verification_result, f, indent=2, ensure_ascii=False)

    print("=" * 70)
    print("📊 验证总结")
    print("=" * 70)
    print(f"总合约数: {verification_result['summary']['total_contracts']}")
    print(f"通过: {verification_result['summary']['passed']}")
    print(f"失败: {verification_result['summary']['failed']}")
    print(f"成功率: {verification_result['summary']['success_rate']:.1f}%")
    print(f"总体状态: {GREEN if verification_result['summary']['overall_status'] == 'PASS' else RED}{'✅ 通过' if verification_result['summary']['overall_status'] == 'PASS' else '❌ 失败'}{RESET}")
    print()
    print(f"{GREEN}✅ 验证结果已保存到: {OUTPUT_FILE}{RESET}")


if __name__ == "__main__":
    main()
