#!/usr/bin/env python3
"""
大宗货物跨境交易智能合约状态读取工具
读取所有合约的属性、映射和状态，输出为JSON格式
"""

import json
import sys
from datetime import datetime
from web3 import Web3
from pathlib import Path
from typing import Dict, List, Any, Optional
import inspect

# 配置路径
CONFIG_DIR = Path("/home/manifold/cursor/cross-chain/config")
CONTRACTS_DIR = Path("/home/manifold/cursor/cross-chain/contracts/kept")
ADDRESSES_FILE = CONFIG_DIR / "address.json"
DID_ADDRESS_MAP_FILE = CONFIG_DIR / "did_address_map.json"
OUTPUT_FILE = CONTRACTS_DIR / "contract_state" / "all_contract_states.json"

# 颜色输出
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"


def load_json(filepath):
    """加载JSON文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"{RED}❌ 加载 {filepath} 失败: {e}{RESET}")
        return None


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
        print(f"{GREEN}✅ 连接到 {chain_name} (区块: {block_number}){RESET}")
        return w3
    except Exception as e:
        print(f"{RED}❌ 连接 {chain_name} 失败: {e}{RESET}")
        return None


def get_contract_instance(w3, contract_name, address):
    """获取合约实例"""
    try:
        # 加载合约ABI
        abi_file = CONTRACTS_DIR / f"{contract_name}.json"
        if not abi_file.exists():
            print(f"{YELLOW}⚠️  ABI文件不存在: {abi_file}{RESET}")
            return None

        with open(abi_file, 'r') as f:
            contract_data = json.load(f)
            abi = contract_data.get("abi", contract_data)

        # 创建合约实例
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(address),
            abi=abi
        )

        return contract
    except Exception as e:
        print(f"{RED}❌ 加载合约 {contract_name} 失败: {e}{RESET}")
        return None


def get_view_functions(contract):
    """获取合约的所有view和pure函数"""
    view_functions = []

    for abi_item in contract.abi:
        if abi_item.get('type') == 'function':
            state_mutability = abi_item.get('stateMutability', 'nonpayable')
            if state_mutability in ['view', 'pure']:
                view_functions.append(abi_item)

    return view_functions


def execute_view_function(contract, func_abi, test_data=None):
    """执行view函数并返回结果，支持批量读取mapping"""
    func_name = func_abi['name']
    inputs = func_abi.get('inputs', [])

    try:
        # 准备参数
        if not inputs:
            # 无参数函数，直接调用
            contract_func = getattr(contract.functions, func_name)
            result = contract_func().call()
            processed_result = process_result(result, func_abi.get('outputs', []))

            return {
                "status": "success",
                "value": processed_result,
                "is_batch": False
            }
        else:
            # 有参数的函数，需要从test_data获取
            if test_data and func_name in test_data:
                test_values = test_data[func_name]

                if not test_values or len(test_values) == 0:
                    return {
                        "status": "skipped",
                        "reason": "测试数据为空",
                        "required_params": [{"name": inp.get('name'), "type": inp.get('type')} for inp in inputs]
                    }

                # 批量调用函数
                results = []
                all_errors = []

                for test_value in test_values[:100]:  # 限制最多100个
                    args = []
                    kwargs = {}

                    # 准备单个参数
                    for i, input_param in enumerate(inputs):
                        param_type = input_param.get('type', '')
                        value = test_value

                        # 类型转换
                        if 'address' in param_type.lower():
                            value = Web3.to_checksum_address(value)
                        elif 'uint256' in param_type.lower() or 'uint' in param_type.lower():
                            value = int(value)
                        elif 'bool' in param_type.lower():
                            value = bool(value)
                        elif 'bytes32' in param_type.lower():
                            if isinstance(value, str) and value.startswith('0x'):
                                value = Web3.to_bytes(hexstr=value)
                            else:
                                value = Web3.to_bytes(hexstr=str(value))

                        args.append(value)

                    # 调用函数
                    try:
                        contract_func = getattr(contract.functions, func_name)
                        result = contract_func(*args, **kwargs).call()
                        processed_result = process_result(result, func_abi.get('outputs', []))

                        # 只记录非空结果
                        if processed_result and processed_result != "0x0000000000000000000000000000000000000000" and processed_result != "" and processed_result != []:
                            results.append({
                                "input": test_value,
                                "result": processed_result
                            })
                    except Exception as e:
                        # 忽略个别错误，继续处理其他值
                        all_errors.append(str(e))

                return {
                    "status": "success",
                    "value": results,
                    "is_batch": True,
                    "total_tested": len(test_values[:100]),
                    "non_empty_results": len(results),
                    "errors_count": len(all_errors)
                }
            else:
                # 没有测试数据，跳过此函数
                return {
                    "status": "skipped",
                    "reason": "需要参数但未提供测试数据",
                    "required_params": [{"name": inp.get('name'), "type": inp.get('type')} for inp in inputs]
                }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }


def process_result(result, outputs):
    """处理函数返回结果"""
    if result is None:
        return None

    # 处理元组
    if isinstance(result, tuple):
        processed = []
        for i, item in enumerate(result):
            output_type = outputs[i].get('type', '') if i < len(outputs) else ''
            processed.append(process_value(item, output_type))
        return processed

    # 处理单个值
    output_type = outputs[0].get('type', '') if outputs else ''
    return process_value(result, output_type)


def process_value(value, value_type):
    """处理单个值"""
    if value is None:
        return None

    # 转换bytes为hex字符串
    if isinstance(value, bytes):
        try:
            return '0x' + value.hex()
        except:
            return str(value)

    # 转换address
    if 'address' in value_type.lower():
        return str(value)

    # 转换整数
    if isinstance(value, int) and 'uint' in value_type.lower():
        return int(value)

    # 转换布尔值
    if isinstance(value, bool):
        return bool(value)

    # 默认返回字符串
    try:
        return str(value)
    except:
        return repr(value)


def read_contract_state(w3, contract_name, address, chain_name, test_data=None):
    """读取合约状态"""
    print(f"\n{BLUE}📖 读取合约: {contract_name}{RESET}")
    print(f"   地址: {address}")

    # 获取合约实例
    contract = get_contract_instance(w3, contract_name, address)
    if not contract:
        return None

    # 获取所有view函数
    view_functions = get_view_functions(contract)
    print(f"   发现 {len(view_functions)} 个view函数")

    # 读取合约状态
    contract_state = {
        "name": contract_name,
        "address": address,
        "chain": chain_name,
        "functions": {}
    }

    for func_abi in view_functions:
        func_name = func_abi['name']
        inputs = func_abi.get('inputs', [])
        outputs = func_abi.get('outputs', [])

        func_info = {
            "name": func_name,
            "inputs": [{"name": inp.get('name', ''), "type": inp.get('type', '')} for inp in inputs],
            "outputs": [{"type": out.get('type', '')} for out in outputs],
            "stateMutability": func_abi.get('stateMutability', 'view')
        }

        # 执行函数
        result = execute_view_function(contract, func_abi, test_data)

        if result['status'] == 'success':
            func_info["result"] = result['value']

            # 保存批量读取的统计信息
            if result.get('is_batch', False):
                func_info["is_batch"] = True
                func_info["total_tested"] = result.get('total_tested', 0)
                func_info["non_empty_results"] = result.get('non_empty_results', 0)

                # 批量读取的结果
                total_tested = result.get('total_tested', 0)
                non_empty = result.get('non_empty_results', 0)
                print(f"   {GREEN}✅ {func_name}{RESET}: 批量读取 {total_tested} 个，非空结果 {non_empty} 个")
            else:
                func_info["is_batch"] = False
                # 单个结果
                print(f"   {GREEN}✅ {func_name}{RESET}: {result['value']}")
        elif result['status'] == 'skipped':
            func_info["skip_reason"] = result['reason']
            func_info["required_params"] = result.get('required_params', [])
            print(f"   {YELLOW}⏭️  {func_name}{RESET}: {result['reason']}")
        else:
            func_info["error"] = result['error']
            func_info["error_type"] = result['error_type']
            print(f"   {RED}❌ {func_name}{RESET}: {result['error']}")

        contract_state["functions"][func_name] = func_info

    return contract_state


def generate_test_data(addresses, did_map):
    """生成完整的测试数据，用于读取所有mapping"""
    test_data = {}

    # 获取所有地址
    all_addresses = []

    # 添加Besu节点地址
    for node_key in ['node1', 'node2', 'node3', 'node4']:
        node_data = addresses.get("besu_nodes", {}).get(node_key, {})
        if node_data.get("address"):
            all_addresses.append(node_data["address"])

    # 添加用户账户地址
    user_accounts = addresses.get("user_accounts", {}).get("accounts", [])
    for acc in user_accounts:
        if acc.get("address"):
            all_addresses.append(acc["address"])

    # 添加合约地址
    chain_a_contracts = addresses.get("contracts", {}).get("chain_a", {})
    for contract_name, contract_addr in chain_a_contracts.items():
        if isinstance(contract_addr, str) and contract_addr.startswith("0x"):
            all_addresses.append(contract_addr)
        elif isinstance(contract_addr, dict):
            for sub_name, sub_addr in contract_addr.items():
                if isinstance(sub_addr, str) and sub_addr.startswith("0x"):
                    all_addresses.append(sub_addr)

    chain_b_contracts = addresses.get("contracts", {}).get("chain_b", {})
    for contract_name, contract_addr in chain_b_contracts.items():
        if isinstance(contract_addr, str) and contract_addr.startswith("0x"):
            all_addresses.append(contract_addr)

    # 添加Oracle服务地址
    oracle_addr = addresses.get("oracle_services", {}).get("chain_a_oracle")
    if oracle_addr:
        all_addresses.append(oracle_addr)

    # 获取所有DID
    all_dids = []
    if did_map and "mappings" in did_map:
        for mapping in did_map["mappings"]:
            if mapping.get("did"):
                all_dids.append(mapping["did"])

    # DIDVerifier测试数据 - 读取所有mapping
    test_data["DIDVerifier"] = {}

    # isVerified mapping - 遍历所有地址
    test_data["DIDVerifier"]["isVerified"] = all_addresses
    test_data["DIDVerifier"]["didOfAddress"] = all_addresses
    test_data["DIDVerifier"]["isAdmin"] = all_addresses
    test_data["DIDVerifier"]["checkUserVerified"] = all_addresses
    test_data["DIDVerifier"]["getUserDID"] = all_addresses

    # addressOfDid mapping - 遍历所有DID
    test_data["DIDVerifier"]["addressOfDid"] = all_dids
    test_data["DIDVerifier"]["getAddressByDID"] = all_dids
    test_data["DIDVerifier"]["getDIDHash"] = all_dids
    test_data["DIDVerifier"]["verifyDIDAddress"] = []  # 需要配对，后面处理

    # ContractManager测试数据
    test_data["ContractManager"] = {}
    test_data["ContractManager"]["isAdmin"] = all_addresses
    test_data["ContractManager"]["contractExists"] = ["contract_001", "contract_002"]
    # 对于所有DID作为exporter/importer查询
    test_data["ContractManager"]["getContractsByExporter"] = all_dids[:5]  # 限制数量
    test_data["ContractManager"]["getContractsByImporter"] = all_dids[:5]

    # VCCrossChainBridge测试数据
    test_data["VCCrossChainBridge"] = {}
    test_data["VCCrossChainBridge"]["isAdmin"] = all_addresses
    test_data["VCCrossChainBridge"]["isOracleService"] = all_addresses
    test_data["VCCrossChainBridge"]["allowedVCManagers"] = all_addresses
    test_data["VCCrossChainBridge"]["oracleAllowedDIDs"] = all_dids

    # VCManager测试数据 (所有4个VCManager)
    vc_manager_tests = {}
    vc_manager_tests["isAdmin"] = all_addresses
    vc_manager_tests["crossChainAllowedDIDs"] = all_dids
    vc_manager_tests["oracleAllowedDIDs"] = all_dids

    # 对于所有DID作为holder查询
    vc_manager_tests["getVCHashesByHolder"] = all_dids[:5]  # 限制数量

    test_data["VCManager"] = vc_manager_tests

    return test_data


def read_all_contracts():
    """读取所有合约状态"""
    print("=" * 80)
    print("🔍 大宗货物跨境交易智能合约状态读取工具")
    print("=" * 80)

    # 加载配置
    addresses = load_json(ADDRESSES_FILE)
    did_map = load_json(DID_ADDRESS_MAP_FILE)

    if not addresses or not did_map:
        print(f"{RED}❌ 加载配置文件失败{RESET}")
        return

    # 生成测试数据
    test_data = generate_test_data(addresses, did_map)

    # 初始化结果
    all_states = {
        "timestamp": datetime.now().isoformat(),
        "version": "1.0",
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
        chain_a_states = []
        for contract_name, address in chain_a_contracts:
            if address:
                # 确定使用哪个测试数据
                if "VCManager" in contract_name:
                    contract_test_data = test_data.get("VCManager", {})
                else:
                    contract_test_data = test_data.get(contract_name, {})

                state = read_contract_state(
                    w3_a,
                    contract_name,
                    address,
                    "chain_a",
                    contract_test_data
                )
                if state:
                    chain_a_states.append(state)

        all_states["chains"]["chain_a"] = {
            "name": "Chain A (源链)",
            "rpc_url": rpc_url,
            "contracts": chain_a_states
        }

    # 读取Chain B
    print(f"\n{BLUE}{'=' * 80}{RESET}")
    print(f"{BLUE}🔗 读取 Chain B (目标链){RESET}")
    print(f"{BLUE}{'=' * 80}{RESET}")

    rpc_url = "http://localhost:8555"
    w3_b = connect_to_chain(rpc_url, "Chain B")

    if w3_b:
        chain_b_states = []
        for contract_name, address in chain_b_contracts:
            if address:
                # 确定使用哪个测试数据
                if "VCManager" in contract_name:
                    contract_test_data = test_data.get("VCManager", {})
                else:
                    contract_test_data = test_data.get(contract_name, {})

                state = read_contract_state(
                    w3_b,
                    contract_name,
                    address,
                    "chain_b",
                    contract_test_data
                )
                if state:
                    chain_b_states.append(state)

        all_states["chains"]["chain_b"] = {
            "name": "Chain B (目标链)",
            "rpc_url": rpc_url,
            "contracts": chain_b_states
        }

    # 统计信息
    total_contracts = 0
    total_functions = 0
    successful_reads = 0
    batch_reads = 0
    total_mapping_queries = 0
    non_empty_mappings = 0

    for chain_data in all_states["chains"].values():
        for contract in chain_data["contracts"]:
            total_contracts += 1
            for func_name, func_data in contract["functions"].items():
                total_functions += 1
                if func_data.get("result") is not None:
                    successful_reads += 1

                    # 统计批量读取
                    if func_data.get("is_batch", False):
                        batch_reads += 1
                        total_mapping_queries += func_data.get("total_tested", 0)
                        non_empty_mappings += func_data.get("non_empty_results", 0)

    all_states["summary"] = {
        "total_contracts": total_contracts,
        "total_functions": total_functions,
        "successful_reads": successful_reads,
        "batch_reads": batch_reads,
        "total_mapping_queries": total_mapping_queries,
        "non_empty_mappings": non_empty_mappings,
        "skipped_functions": total_functions - successful_reads
    }

    # 保存结果
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_states, f, indent=2, ensure_ascii=False)

    print(f"\n{GREEN}{'=' * 80}{RESET}")
    print(f"{GREEN}📊 读取完成{RESET}")
    print(f"{GREEN}{'=' * 80}{RESET}")
    print(f"总合约数: {total_contracts}")
    print(f"总函数数: {total_functions}")
    print(f"成功读取: {successful_reads}")
    print(f"批量读取函数: {batch_reads}")
    print(f"  - 总查询次数: {total_mapping_queries}")
    print(f"  - 非空结果数: {non_empty_mappings}")
    print(f"跳过函数: {total_functions - successful_reads}")
    print(f"\n{GREEN}✅ 结果已保存到: {OUTPUT_FILE}{RESET}")


if __name__ == "__main__":
    read_all_contracts()
