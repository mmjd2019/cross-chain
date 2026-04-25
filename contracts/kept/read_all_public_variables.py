#!/usr/bin/env python3
"""
智能合约Public变量和Mapping完整读取工具
读取所有合约的public变量和mapping，通过getter方法获取所有值
"""

import json
import sys
from datetime import datetime
from web3 import Web3
from pathlib import Path
from typing import Dict, List, Any, Optional
import re


class BytesEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理bytes类型"""
    def default(self, obj):
        if isinstance(obj, bytes):
            return obj.hex()
        return super().default(obj)

# 配置路径
CONFIG_DIR = Path("/home/manifold/cursor/cross-chain-new/config")
CONTRACTS_DIR = Path("/home/manifold/cursor/cross-chain-new/contracts/kept")
ADDRESSES_FILE = CONFIG_DIR / "address.json"
DID_ADDRESS_MAP_FILE = CONFIG_DIR / "did_address_map.json"
OUTPUT_FILE = CONTRACTS_DIR / "contract_state" / "all_public_variables.json"
VC_HASH_FILE = CONTRACTS_DIR / "哈希.txt"

# 颜色输出
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"


def load_json(filepath):
    """加载JSON文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"{RED}❌ 加载 {filepath} 失败: {e}{RESET}")
        return None


def load_vc_hashes():
    """从哈希.txt加载VC哈希值"""
    vc_hashes = []
    try:
        if VC_HASH_FILE.exists():
            with open(VC_HASH_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and line.startswith('0x'):
                        vc_hashes.append(line)
            if vc_hashes:
                print(f"{GREEN}✅ 从 {VC_HASH_FILE} 加载了 {len(vc_hashes)} 个VC哈希{RESET}")
            else:
                print(f"{YELLOW}⚠️  {VC_HASH_FILE} 文件为空{RESET}")
        else:
            print(f"{YELLOW}⚠️  {VC_HASH_FILE} 文件不存在{RESET}")
    except Exception as e:
        print(f"{RED}❌ 读取 {VC_HASH_FILE} 失败: {e}{RESET}")
    return vc_hashes


def connect_to_chain(rpc_url, chain_name):
    """连接到区块链"""
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    try:
        from web3.middleware.geth_poa import geth_poa_middleware
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    except:
        pass

    try:
        block_number = w3.eth.get_block('latest')['number']
        print(f"{GREEN}✅ 连接到 {chain_name} (区块: {block_number}){RESET}")
        return w3
    except Exception as e:
        print(f"{RED}❌ 连接 {chain_name} 失败: {e}{RESET}")
        return None


def get_contract_instance(w3, contract_name, address):
    """获取合约实例"""
    try:
        # 尝试多个可能的 ABI 文件位置
        abi_paths = [
            CONTRACTS_DIR / "contract_abis" / f"{contract_name}.json",
            CONTRACTS_DIR / f"{contract_name}.json",
            CONTRACTS_DIR / "build" / f"{contract_name}.abi",
        ]

        # 特殊处理：VCCrossChainBridge -> VCCrossChainBridgeSimple
        if contract_name == "VCCrossChainBridge":
            abi_paths.insert(0, CONTRACTS_DIR / "contract_abis" / "VCCrossChainBridgeSimple.json")
            abi_paths.insert(1, CONTRACTS_DIR / "build" / "VCCrossChainBridgeSimple.abi")

        abi_file = None
        for path in abi_paths:
            if path.exists():
                abi_file = path
                break

        if not abi_file:
            print(f"    {YELLOW}⚠️  未找到 {contract_name} 的 ABI 文件{RESET}")
            print(f"       尝试的路径: {[str(p) for p in abi_paths[:3]]}")
            return None

        with open(abi_file, 'r') as f:
            contract_data = json.load(f)
            abi = contract_data.get("abi", contract_data)

        contract = w3.eth.contract(
            address=Web3.to_checksum_address(address),
            abi=abi
        )

        return contract
    except Exception as e:
        print(f"{RED}❌ 加载合约 {contract_name} 失败: {e}{RESET}")
        return None


def analyze_function_type(func_abi):
    """分析函数类型，识别public变量getter"""
    name = func_abi.get('name', '')
    inputs = func_abi.get('inputs', [])
    outputs = func_abi.get('outputs', [])
    state_mutability = func_abi.get('stateMutability', 'nonpayable')

    # 只处理view/pure函数
    if state_mutability not in ['view', 'pure']:
        return None

    # 判断是否是public变量的getter
    # public变量的getter特征：
    # 1. 函数名与变量名相同
    # 2. 返回单个值或tuple
    # 3. 无参数或参数为mapping的key

    func_info = {
        'name': name,
        'inputs': inputs,
        'outputs': outputs,
        'stateMutability': state_mutability,
        'type': 'unknown'
    }

    # 判断类型
    if len(inputs) == 0:
        # 无参数，可能是简单public变量
        func_info['type'] = 'simple_variable'
        func_info['category'] = 'state_variable'
    elif len(inputs) == 1:
        # 单个参数，可能是mapping
        param_type = inputs[0].get('type', '')
        func_info['type'] = 'mapping'
        func_info['mapping_key_type'] = param_type
        func_info['category'] = 'mapping'
    elif len(inputs) > 1:
        # 多个参数，可能是嵌套mapping或数组
        func_info['type'] = 'complex_mapping'
        func_info['category'] = 'mapping'

    return func_info


def get_all_test_keys(addresses, did_map):
    """获取所有可能的测试key，并返回带有性质标记的地址列表"""
    test_keys = {
        'address': [],
        'string': [],
        'uint256': [],
        'bool': [],
        'bytes32': []
    }

    # 收集所有地址及其性质
    all_addresses_with_type = []

    # Besu节点
    for node_key in ['node1', 'node2', 'node3', 'node4']:
        node_data = addresses.get("besu_nodes", {}).get(node_key, {})
        addr = node_data.get("address")
        if addr:
            all_addresses_with_type.append({
                "address": addr,
                "type": "besu_node",
                "subtype": node_key,
                "description": f"Besu验证节点 {node_key}",
                "enode": node_data.get("enode", "")
            })

    # 用户账户
    accounts = addresses.get("user_accounts", {}).get("accounts", [])
    for i, acc in enumerate(accounts):
        addr = acc.get("address")
        if addr:
            all_addresses_with_type.append({
                "address": addr,
                "type": "user_account",
                "subtype": "user",
                "index": i,
                "description": f"用户账户 #{i+1}",
                "private_key_preview": acc.get("private_key", "")[:10] + "..." if acc.get("private_key") else ""
            })

    # 合约地址 - Chain A
    chain_a = addresses.get("contracts", {}).get("chain_a", {})
    if isinstance(chain_a, dict):
        for key, value in chain_a.items():
            if isinstance(value, str) and value.startswith('0x') and len(value) == 42:
                all_addresses_with_type.append({
                    "address": value,
                    "type": "contract",
                    "subtype": "chain_a",
                    "contract_name": key,
                    "description": f"Chain A 合约: {key}",
                    "chain": "chain_a"
                })
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, str) and sub_value.startswith('0x') and len(sub_value) == 42:
                        all_addresses_with_type.append({
                            "address": sub_value,
                            "type": "contract",
                            "subtype": "chain_a",
                            "contract_category": key,
                            "contract_name": sub_key,
                            "description": f"Chain A 合约: {key}.{sub_key}",
                            "chain": "chain_a"
                        })

    # 合约地址 - Chain B
    chain_b = addresses.get("contracts", {}).get("chain_b", {})
    if isinstance(chain_b, dict):
        for key, value in chain_b.items():
            if isinstance(value, str) and value.startswith('0x') and len(value) == 42:
                all_addresses_with_type.append({
                    "address": value,
                    "type": "contract",
                    "subtype": "chain_b",
                    "contract_name": key,
                    "description": f"Chain B 合约: {key}",
                    "chain": "chain_b"
                })

    # Oracle地址
    oracle_addr = addresses.get("oracle_services", {}).get("chain_a_oracle")
    if oracle_addr:
        all_addresses_with_type.append({
            "address": oracle_addr,
            "type": "oracle",
            "subtype": "chain_a_oracle",
            "description": "Chain A Oracle 服务地址",
            "chain": "chain_a"
        })

    # 去重（保留第一次出现的）
    seen = {}
    unique_addresses = []
    for addr_info in all_addresses_with_type:
        addr = addr_info["address"]
        if addr not in seen:
            seen[addr] = True
            unique_addresses.append(addr_info)

    all_addresses_with_type = unique_addresses

    # 提取纯地址列表用于测试
    all_addresses = [addr_info["address"] for addr_info in all_addresses_with_type]
    test_keys['address'] = all_addresses[:100]  # 限制100个

    # 收集所有DID
    all_dids = []
    if did_map and "mappings" in did_map:
        for mapping in did_map["mappings"]:
            did = mapping.get("did")
            if did:
                all_dids.append(did)

    test_keys['string'] = all_dids[:100]

    # uint256测试值
    test_keys['uint256'] = [0, 1, 100, 1000, 10000, 1000000]

    # bool测试值
    test_keys['bool'] = [True, False]

    # bytes32测试值
    test_keys['bytes32'] = [
        Web3.to_bytes(hexstr="0" * 64),
        Web3.to_bytes(hexstr="1" * 64),
        Web3.to_bytes(hexstr="a" * 64)
    ]

    # 返回测试keys和地址详细信息
    return test_keys, all_addresses_with_type

def read_simple_variable(contract, func_name):
    """读取简单public变量"""
    try:
        contract_func = getattr(contract.functions, func_name)
        result = contract_func().call()
        return {
            "status": "success",
            "value": str(result) if not isinstance(result, (list, tuple)) else result
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def read_mapping(contract, func_abi, test_keys, vc_hashes=None):
    """读取mapping的所有值"""
    func_name = func_abi['name']
    inputs = func_abi.get('inputs', [])

    if len(inputs) == 0:
        return {"status": "error", "error": "Not a mapping"}

    # 获取参数类型
    param_type = inputs[0].get('type', '')

    # 根据参数类型选择测试keys
    if 'address' in param_type:
        test_values = test_keys.get('address', [])
    elif 'string' in param_type:
        test_values = test_keys.get('string', [])
    elif 'uint' in param_type or 'int' in param_type:
        test_values = test_keys.get('uint256', [])
    elif 'bool' in param_type:
        test_values = test_keys.get('bool', [])
    elif 'bytes' in param_type:
        test_values = test_keys.get('bytes32', [])
        # 如果是bytes32类型（VC hash），额外添加VC hash文件中的哈希值
        if vc_hashes and len(vc_hashes) > 0:
            # 将VC hash转换为bytes32并添加到测试列表
            for vc_hash in vc_hashes:
                # 去重
                if vc_hash not in [str(v) if isinstance(v, str) else v.hex() if isinstance(v, bytes) else str(v)
                                 for v in test_values]:
                    # 将字符串hash转换为bytes
                    if vc_hash.startswith('0x'):
                        vc_hash_bytes = bytes.fromhex(vc_hash[2:])
                    else:
                        vc_hash_bytes = bytes.fromhex(vc_hash)
                    test_values.insert(0, vc_hash_bytes)  # 插入到开头
            print(f"      {GREEN}📝 使用 {len(vc_hashes)} 个VC哈希作为测试key{RESET}")
    else:
        return {"status": "skipped", "reason": f"Unsupported type: {param_type}"}

    if not test_values:
        return {"status": "skipped", "reason": "No test values available"}

    # 批量读取mapping
    results = []
    errors = []

    contract_func = getattr(contract.functions, func_name)

    for test_value in test_values[:100]:
        try:
            # 类型转换
            converted_value = test_value
            if 'address' in param_type:
                converted_value = Web3.to_checksum_address(test_value)
            elif 'uint' in param_type or 'int' in param_type:
                converted_value = int(test_value)
            elif 'bytes' in param_type:
                if isinstance(test_value, str):
                    converted_value = Web3.to_bytes(hexstr=test_value)
                else:
                    converted_value = test_value

            # 调用函数
            result = contract_func(converted_value).call()

            # 处理返回值
            if isinstance(result, tuple):
                processed = [str(r) if not isinstance(r, bytes) else r.hex() for r in result]
            elif isinstance(result, bytes):
                processed = result.hex()
            else:
                processed = str(result) if result is not None else None

            # 保存所有结果（包括空值）
            results.append({
                "key": str(test_value) if isinstance(test_value, str) else test_value.hex() if isinstance(test_value, bytes) else str(test_value),
                "value": processed,
                "raw_type": type(result).__name__,
                "is_empty": (
                    result is None or
                    result == '' or
                    processed == '0x0000000000000000000000000000000000000000' or
                    (isinstance(result, bool) and result == False)
                )
            })

        except Exception as e:
            errors.append({
                "key": str(test_value) if isinstance(test_value, str) else test_value.hex() if isinstance(test_value, bytes) else str(test_value),
                "error": str(e),
                "error_type": type(e).__name__
            })

    return {
        "status": "success",
        "mapping_type": param_type,
        "total_tested": len(test_values[:100]),
        "total_results": len(results),
        "non_empty_results": len([r for r in results if not r['is_empty']]),
        "empty_results": len([r for r in results if r['is_empty']]),
        "all_entries": results,
        "errors_count": len(errors),
        "errors": errors
    }


def read_contract_public_variables(w3, contract_name, address, chain_name, test_keys, vc_hashes=None):
    """读取合约的所有public变量和mapping"""
    print(f"\n{CYAN}📖 读取合约: {contract_name}{RESET}")
    print(f"   地址: {address}")

    # 获取合约实例
    contract = get_contract_instance(w3, contract_name, address)
    if not contract:
        return None

    # 分析所有函数
    public_vars = {
        "contract_name": contract_name,
        "address": address,
        "chain": chain_name,
        "simple_variables": {},
        "mappings": {}
    }

    for abi_item in contract.abi:
        if abi_item.get('type') != 'function':
            continue

        func_info = analyze_function_type(abi_item)
        if not func_info:
            continue

        func_name = func_info['name']

        if func_info['type'] == 'simple_variable':
            # 读取简单public变量
            result = read_simple_variable(contract, func_name)
            public_vars['simple_variables'][func_name] = {
                "value": result.get('value'),
                "status": result['status']
            }
            if result['status'] == 'success':
                print(f"   {GREEN}✅ {func_name}{RESET}: {result['value']}")
            else:
                print(f"   {RED}❌ {func_name}{RESET}: {result['error']}")

        elif func_info['type'] in ['mapping', 'complex_mapping']:
            # 读取mapping
            result = read_mapping(contract, abi_item, test_keys, vc_hashes)

            mapping_info = {
                "key_type": func_info.get('mapping_key_type', 'unknown'),
                "status": result['status']
            }

            if result['status'] == 'success':
                mapping_info.update({
                    "total_tested": result['total_tested'],
                    "total_results": result['total_results'],
                    "non_empty_results": result['non_empty_results'],
                    "empty_results": result['empty_results'],
                    "all_entries": result['all_entries'],
                    "errors_count": result['errors_count']
                })
                print(f"   {GREEN}✅ {func_name}{RESET}: mapping({func_info.get('mapping_key_type', '?')} => ?)")
                print(f"      测试 {result['total_tested']} 个key")
                print(f"      总结果: {result['total_results']}, 非空: {result['non_empty_results']}, 空: {result['empty_results']}")
                if result['errors_count'] > 0:
                    print(f"      错误: {result['errors_count']} 个")
            elif result['status'] == 'skipped':
                mapping_info['skip_reason'] = result['reason']
                print(f"   {YELLOW}⏭️  {func_name}{RESET}: {result['reason']}")
            else:
                mapping_info['error'] = result.get('error')
                print(f"   {RED}❌ {func_name}{RESET}: {result.get('error')}")

            public_vars['mappings'][func_name] = mapping_info

    return public_vars


def read_all_public_variables():
    """读取所有合约的public变量和mapping"""
    print("=" * 80)
    print("🔍 智能合约Public变量和Mapping完整读取工具")
    print("=" * 80)

    # 加载配置
    addresses = load_json(ADDRESSES_FILE)
    did_map = load_json(DID_ADDRESS_MAP_FILE)

    if not addresses or not did_map:
        print(f"{RED}❌ 加载配置文件失败{RESET}")
        return

    # 加载VC哈希
    vc_hashes = load_vc_hashes()

    # 生成测试keys和地址详细信息
    test_keys, all_addresses_with_type = get_all_test_keys(addresses, did_map)
    print(f"\n{BLUE}📊 测试数据准备完成:{RESET}")
    print(f"  • 地址数量: {len(test_keys['address'])}")
    print(f"  • DID数量: {len(test_keys['string'])}")
    print(f"  • VC哈希: {len(vc_hashes) if vc_hashes else 0}")
    print(f"  • 其他类型: uint, bool, bytes32")

    # 统计地址类型
    address_types = {}
    for addr_info in all_addresses_with_type:
        addr_type = addr_info['type']
        if addr_type not in address_types:
            address_types[addr_type] = []
        address_types[addr_type].append(addr_info)

    print(f"\n{CYAN}📋 地址类型统计:{RESET}")
    for addr_type, addr_list in address_types.items():
        print(f"  • {addr_type}: {len(addr_list)} 个")

    # 保存地址详细信息到单独的JSON文件
    addresses_output_file = CONTRACTS_DIR / "deployment_results" / "all_addresses_with_types.json"
    addresses_data = {
        "timestamp": datetime.now().isoformat(),
        "description": "所有测试地址及其性质标记",
        "total_addresses": len(all_addresses_with_type),
        "address_types_summary": {
            addr_type: len(addr_list) for addr_type, addr_list in address_types.items()
        },
        "addresses": all_addresses_with_type
    }

    with open(addresses_output_file, 'w', encoding='utf-8') as f:
        json.dump(addresses_data, f, indent=2, ensure_ascii=False)

    print(f"\n{GREEN}✅ 地址详细信息已保存到: {addresses_output_file}{RESET}")

    # 初始化结果
    all_vars = {
        "timestamp": datetime.now().isoformat(),
        "version": "2.1",
        "description": "智能合约所有public变量和mapping的完整读取结果（支持VC哈希）",
        "test_data_info": {
            "total_addresses": len(test_keys['address']),
            "total_dids": len(test_keys['string']),
            "vc_hashes_count": len(vc_hashes) if vc_hashes else 0,
            "addresses_detail_file": str(addresses_output_file)
        },
        "chains": {}
    }

    # Chain A合约配置
    chain_a_contracts = [
        ("DIDVerifier", addresses.get("contracts", {}).get("chain_a", {}).get("did_verifier", "")),
        ("ContractManager", addresses.get("contracts", {}).get("chain_a", {}).get("contract_manager", "")),
        ("VCCrossChainBridge", addresses.get("contracts", {}).get("chain_a", {}).get("cross_chain_bridge", "")),
        ("InspectionReportVCManager", addresses.get("contracts", {}).get("chain_a", {}).get("vc_managers", {}).get("inspection_report", "")),
        ("InsuranceContractVCManager", addresses.get("contracts", {}).get("chain_a", {}).get("vc_managers", {}).get("insurance_contract", "")),
        ("CertificateOfOriginVCManager", addresses.get("contracts", {}).get("chain_a", {}).get("vc_managers", {}).get("certificate_of_origin", "")),
        ("BillOfLadingVCManager", addresses.get("contracts", {}).get("chain_a", {}).get("vc_managers", {}).get("bill_of_lading", "")),
    ]

    # Chain B合约配置
    chain_b_contracts = [
        ("DIDVerifier", addresses.get("contracts", {}).get("chain_b", {}).get("did_verifier", "")),
        ("VCCrossChainBridge", addresses.get("contracts", {}).get("chain_b", {}).get("cross_chain_bridge", "")),
    ]

    # 读取Chain A
    print(f"\n{BLUE}{'=' * 80}{RESET}")
    print(f"{BLUE}🔗 读取 Chain A (源链){RESET}")
    print(f"{BLUE}{'=' * 80}{RESET}")

    rpc_url = "http://localhost:8545"
    w3_a = connect_to_chain(rpc_url, "Chain A")

    if w3_a:
        chain_a_vars = []
        for contract_name, address in chain_a_contracts:
            if address:
                vars_data = read_contract_public_variables(
                    w3_a,
                    contract_name,
                    address,
                    "chain_a",
                    test_keys,
                    vc_hashes
                )
                if vars_data:
                    chain_a_vars.append(vars_data)

        all_vars["chains"]["chain_a"] = {
            "name": "Chain A (源链)",
            "rpc_url": rpc_url,
            "contracts": chain_a_vars
        }

    # 读取Chain B
    print(f"\n{BLUE}{'=' * 80}{RESET}")
    print(f"{BLUE}🔗 读取 Chain B (目标链){RESET}")
    print(f"{BLUE}{'=' * 80}{RESET}")

    rpc_url = "http://localhost:8555"
    w3_b = connect_to_chain(rpc_url, "Chain B")

    if w3_b:
        chain_b_vars = []
        for contract_name, address in chain_b_contracts:
            if address:
                vars_data = read_contract_public_variables(
                    w3_b,
                    contract_name,
                    address,
                    "chain_b",
                    test_keys,
                    vc_hashes
                )
                if vars_data:
                    chain_b_vars.append(vars_data)

        all_vars["chains"]["chain_b"] = {
            "name": "Chain B (目标链)",
            "rpc_url": rpc_url,
            "contracts": chain_b_vars
        }

    # 统计信息
    total_contracts = 0
    total_simple_vars = 0
    total_mappings = 0
    total_mapping_entries = 0
    total_empty_entries = 0

    for chain_data in all_vars["chains"].values():
        for contract in chain_data["contracts"]:
            total_contracts += 1
            total_simple_vars += len(contract["simple_variables"])
            total_mappings += len(contract["mappings"])
            for mapping_name, mapping_data in contract["mappings"].items():
                if mapping_data.get("status") == "success":
                    total_mapping_entries += mapping_data.get("total_results", 0)
                    total_empty_entries += mapping_data.get("empty_results", 0)

    all_vars["summary"] = {
        "total_contracts": total_contracts,
        "total_simple_variables": total_simple_vars,
        "total_mappings": total_mappings,
        "total_mapping_entries": total_mapping_entries,
        "total_empty_entries": total_empty_entries,
        "total_non_empty_entries": total_mapping_entries - total_empty_entries
    }

    # 保存结果
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_vars, f, indent=2, ensure_ascii=False, cls=BytesEncoder)

    print(f"\n{GREEN}{'=' * 80}{RESET}")
    print(f"{GREEN}📊 读取完成{RESET}")
    print(f"{GREEN}{'=' * 80}{RESET}")
    print(f"总合约数: {total_contracts}")
    print(f"简单public变量: {total_simple_vars}")
    print(f"Mapping数量: {total_mappings}")
    print(f"总Mapping条目: {total_mapping_entries}")
    print(f"  • 非空条目: {total_mapping_entries - total_empty_entries}")
    print(f"  • 空条目: {total_empty_entries}")
    print(f"\n{GREEN}✅ 结果已保存到: {OUTPUT_FILE}{RESET}")


if __name__ == "__main__":
    read_all_public_variables()
