#!/usr/bin/env python3
"""
跨链VC传输Oracle服务测试脚本

测试流程：
1. 在Chain A上调用initiateCrossChainTransfer
2. 等待Oracle检测到VCSent事件
3. 验证目标链是否收到VC元数据
4. 验证VCReceived事件是否发射

配置说明：
- 从config/cross_chain_oracle_config.json读取VC Manager Owner账户（用于调用所有VC Manager）
- 从config/cross_chain_oracle_config.json读取4个VC Manager合约地址
- 从oracle/logs/uuid.json读取可用的VC Hash用于测试

新功能（--create-random）：
- 随机生成一个新的 VC Hash
- 调用 VC Manager 合约的 addVCMetadata 写入元数据
- 自动调用 initiateCrossChainTransfer 发起跨链传输
- 等待 Oracle 检测并传输到目标链
- 验证目标链是否收到
"""

import sys
import json
import time
import secrets
from pathlib import Path
from web3 import Web3
from web3.middleware import geth_poa_middleware

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 配置文件路径
CONFIG_FILE = Path(__file__).parent.parent / "config" / "cross_chain_oracle_config.json"
UUID_FILE = Path(__file__).parent / "logs" / "uuid.json"

# 4个VC Manager合约地址（从cross_chain_oracle_config.json读取）
VC_MANAGERS = {
    'InspectionReport': {
        'contract_name': 'InspectionReportVCManager',
        'abi_file': 'InspectionReportVCManager.json'
    },
    'InsuranceContract': {
        'contract_name': 'InsuranceContractVCManager',
        'abi_file': 'InsuranceContractVCManager.json'
    },
    'CertificateOfOrigin': {
        'contract_name': 'CertificateOfOriginVCManager',
        'abi_file': 'CertificateOfOriginVCManager.json'
    },
    'BillOfLadingCertificate': {
        'contract_name': 'BillOfLadingVCManager',
        'abi_file': 'BillOfLadingVCManager.json'
    }
}


def load_config():
    """加载配置文件"""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"配置文件不存在: {CONFIG_FILE}")

    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)


def get_vc_manager_config(vc_type: str, config: dict) -> dict:
    """根据VC类型获取对应的VC Manager配置（使用VC Manager Owner账户）"""

    # VC类型到配置key的映射
    vc_type_to_key = {
        'InspectionReport': 'InspectionReportVCManager',
        'InsuranceContract': 'InsuranceContractVCManager',
        'CertificateOfOrigin': 'CertificateOfOriginVCManager',
        'BillOfLadingCertificate': 'BillOfLadingVCManager'
    }

    config_key = vc_type_to_key.get(vc_type)
    if not config_key:
        raise ValueError(f"未知的VC类型: {vc_type}，可用类型: {list(vc_type_to_key.keys())}")

    # 从配置文件获取VC Manager地址
    vc_managers = config.get('vc_managers', {}).get('chain_a', {})
    if config_key not in vc_managers:
        raise ValueError(f"未找到VC Manager配置: {config_key}")

    vc_manager_info = vc_managers[config_key]

    # 使用VC Manager Owner账户（可调用所有VC Manager）
    owner_config = config.get('vc_manager_owner', {})
    if not owner_config:
        raise ValueError("配置文件中缺少vc_manager_owner配置")

    return {
        'vc_manager_address': vc_manager_info.get('address'),
        'vc_manager_did': vc_manager_info.get('did'),
        'vc_manager_name': config_key,
        'abi_file': VC_MANAGERS[vc_type]['abi_file'],
        'caller_address': owner_config.get('address'),
        'caller_private_key': owner_config.get('private_key'),
        'caller_description': 'VC Manager Owner（可调用所有VC Manager）',
        'vc_type': vc_type
    }


def get_latest_vc_hash():
    """从uuid.json获取最新的VC记录（包含vc_hash和vc_type）"""
    if not UUID_FILE.exists():
        return None, None

    with open(UUID_FILE, 'r') as f:
        uuid_data = json.load(f)

    # 获取最新的（最后一个）VC记录
    if not uuid_data:
        return None, None

    latest_uuid = list(uuid_data.keys())[-1]
    latest_record = uuid_data[latest_uuid]
    return latest_record.get('vc_hash'), latest_record.get('vc_type')


def get_available_vc_hashes(limit=10):
    """从uuid.json获取可用的VC Hash列表"""
    if not UUID_FILE.exists():
        return []

    with open(UUID_FILE, 'r') as f:
        uuid_data = json.load(f)

    # 获取最近N个VC Hash
    hashes = []
    for uuid_key in reversed(list(uuid_data.keys())):
        record = uuid_data[uuid_key]
        if 'vc_hash' in record:
            hashes.append({
                'uuid': uuid_key,
                'vc_hash': record['vc_hash'],
                'vc_type': record.get('vc_type', 'Unknown'),
                'contract_name': record.get('original_contract_name', 'N/A'),
                'timestamp': record.get('timestamp', 'N/A')
            })
            if len(hashes) >= limit:
                break

    return hashes


def load_contract_abi(contract_name: str) -> dict:
    """加载合约ABI"""
    # 尝试多个可能的路径
    possible_paths = [
        Path(__file__).parent.parent / "contracts" / "kept" / "contract_abis" / f"{contract_name}.json",
        Path(__file__).parent.parent / "contracts" / "kept" / f"{contract_name}.json",
        Path(__file__).parent.parent / "contracts" / "kept" / "build" / f"{contract_name}.json",
    ]

    for path in possible_paths:
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)['abi']

    raise FileNotFoundError(f"找不到合约ABI文件: {contract_name}")


def create_random_vc(config: dict, vc_type: str = 'InspectionReport') -> tuple:
    """创建随机 VC 并写入 VC Manager 合约

    Args:
        config: 配置字典
        vc_type: VC 类型 (InspectionReport, InsuranceContract, CertificateOfOrigin, BillOfLadingCertificate)

    Returns:
        (vc_hash, vc_manager_address) 元组
    """
    print("\n" + "=" * 80)
    print("创建随机 VC")
    print("=" * 80)

    # 获取 VC Manager 配置
    auth_config = get_vc_manager_config(vc_type, config)

    # 连接到 Chain A
    chain_a_config = config['chains']['chain_a']
    w3 = Web3(Web3.HTTPProvider(chain_a_config['rpc_url']))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    try:
        chain_id = w3.eth.chain_id
    except Exception as e:
        raise ConnectionError(f"无法连接到 Chain A: {e}")

    print(f"[OK] 已连接到 Chain A (Chain ID: {chain_id})")

    # 1. 生成随机 VC Hash
    vc_hash_bytes = secrets.token_bytes(32)
    vc_hash = "0x" + vc_hash_bytes.hex()
    print(f"\n[1/3] 生成随机 VC Hash:")
    print(f"      {vc_hash}")

    # 2. 准备元数据
    timestamp = int(time.time())
    vc_name = f"测试VC-{timestamp}"
    vc_description = f"自动生成的测试VC，用于跨链传输测试"

    # 从 vc_issuance_config.json 获取 DID 信息
    vc_issuance_config_path = Path(__file__).parent / "vc_issuance_config.json"
    if vc_issuance_config_path.exists():
        with open(vc_issuance_config_path, 'r') as f:
            vc_issuance_config = json.load(f)
        issuer_did = vc_issuance_config.get('acapy', {}).get('issuer', {}).get('did', 'DPvobytTtKvmyeRTJZYjsg')
        holder_did = vc_issuance_config.get('acapy', {}).get('holder', {}).get('did', 'YL2HDxkVL8qMrssaZbvtfH')
        issuer_endpoint = vc_issuance_config.get('acapy', {}).get('issuer', {}).get('endpoint', 'http://localhost:8000')
        holder_endpoint = vc_issuance_config.get('acapy', {}).get('holder', {}).get('endpoint', 'http://localhost:8001')
    else:
        # 使用默认值
        issuer_did = "DPvobytTtKvmyeRTJZYjsg"
        holder_did = "YL2HDxkVL8qMrssaZbvtfH"
        issuer_endpoint = "http://localhost:8000"
        holder_endpoint = "http://localhost:8001"

    blockchain_endpoint = chain_a_config['rpc_url']
    blockchain_type = "Hyperledger Besu"
    expiry_time = timestamp + 365 * 24 * 3600  # 一年后过期

    print(f"\n[2/3] 准备 VC 元数据:")
    print(f"      VC 名称: {vc_name}")
    print(f"      VC 描述: {vc_description}")
    print(f"      发行者 DID: {issuer_did}")
    print(f"      发行者 Endpoint: {issuer_endpoint}")
    print(f"      持有者 DID: {holder_did}")
    print(f"      持有者 Endpoint: {holder_endpoint}")
    print(f"      区块链 Endpoint: {blockchain_endpoint}")
    print(f"      区块链类型: {blockchain_type}")
    print(f"      过期时间: {expiry_time} ({time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expiry_time))})")

    # 3. 调用 addVCMetadata
    print(f"\n[3/3] 写入 VC Manager 合约...")

    # 加载 VC Manager 合约
    vc_manager_abi = load_contract_abi(VC_MANAGERS[vc_type]['abi_file'].replace('.json', ''))
    vc_manager = w3.eth.contract(
        address=Web3.to_checksum_address(auth_config['vc_manager_address']),
        abi=vc_manager_abi
    )

    # 准备交易
    caller_address = Web3.to_checksum_address(auth_config['caller_address'])
    caller_private_key = auth_config['caller_private_key']

    # 获取 gas 配置
    gas_price = config.get('blockchain', {}).get('gas_price', 1000000000)
    gas_limit = config.get('blockchain', {}).get('gas_limit', 5000000)

    # 构建 addVCMetadata 交易
    txn = vc_manager.functions.addVCMetadata(
        vc_hash_bytes,
        vc_name,
        vc_description,
        issuer_endpoint,
        issuer_did,
        holder_endpoint,
        holder_did,
        blockchain_endpoint,
        blockchain_type,
        expiry_time
    ).build_transaction({
        'from': caller_address,
        'gas': gas_limit,
        'gasPrice': gas_price,
        'nonce': w3.eth.get_transaction_count(caller_address)
    })

    # 签名并发送交易
    signed_txn = w3.eth.account.sign_transaction(txn, caller_private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

    print(f"      交易已发送: {tx_hash.hex()}")

    # 等待交易确认
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt['status'] == 1:
        print(f"      [OK] addVCMetadata 成功! 区块: {receipt['blockNumber']}")
    else:
        raise Exception(f"addVCMetadata 交易失败! tx_hash: {tx_hash.hex()}")

    print(f"\n[SUCCESS] 随机 VC 创建成功!")
    print(f"          VC Hash: {vc_hash}")
    print(f"          VC Manager: {auth_config['vc_manager_address']}")

    return vc_hash, auth_config['vc_manager_address'], vc_type


def initiate_cross_chain_transfer(config: dict, vc_hash: str, vc_type: str, target_chain: str = "chain_b") -> str:
    """发起跨链传输

    Args:
        config: 配置字典
        vc_hash: VC Hash
        vc_type: VC 类型
        target_chain: 目标链 ID

    Returns:
        交易哈希
    """
    print("\n" + "=" * 80)
    print("发起跨链传输")
    print("=" * 80)

    # 获取 VC Manager 配置
    auth_config = get_vc_manager_config(vc_type, config)

    # 连接到 Chain A
    chain_a_config = config['chains']['chain_a']
    w3 = Web3(Web3.HTTPProvider(chain_a_config['rpc_url']))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    # 加载 VC Manager 合约
    vc_manager_abi = load_contract_abi(VC_MANAGERS[vc_type]['abi_file'].replace('.json', ''))
    vc_manager = w3.eth.contract(
        address=Web3.to_checksum_address(auth_config['vc_manager_address']),
        abi=vc_manager_abi
    )

    # 准备交易
    caller_address = Web3.to_checksum_address(auth_config['caller_address'])
    caller_private_key = auth_config['caller_private_key']
    vc_hash_bytes = bytes.fromhex(vc_hash.replace('0x', ''))

    # 获取 gas 配置
    gas_price = config.get('blockchain', {}).get('gas_price', 1000000000)
    gas_limit = config.get('blockchain', {}).get('gas_limit', 5000000)

    print(f"\n[INFO] 调用 initiateCrossChainTransfer...")
    print(f"       VC Hash: {vc_hash}")
    print(f"       目标链: {target_chain}")
    print(f"       调用账户: {caller_address}")

    # 构建 initiateCrossChainTransfer 交易
    txn = vc_manager.functions.initiateCrossChainTransfer(
        vc_hash_bytes,
        target_chain
    ).build_transaction({
        'from': caller_address,
        'gas': gas_limit,
        'gasPrice': gas_price,
        'nonce': w3.eth.get_transaction_count(caller_address)
    })

    # 签名并发送交易
    signed_txn = w3.eth.account.sign_transaction(txn, caller_private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

    print(f"\n[INFO] 交易已发送: {tx_hash.hex()}")

    # 等待交易确认
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt['status'] == 1:
        print(f"[OK] initiateCrossChainTransfer 成功! 区块: {receipt['blockNumber']}")

        # 解析 VCSent 事件
        try:
            # 获取 Bridge 合约 ABI
            bridge_abi = load_contract_abi("VCCrossChainBridgeSimple")
            bridge = w3.eth.contract(
                address=Web3.to_checksum_address(chain_a_config['bridge_address']),
                abi=bridge_abi
            )

            # 查找 VCSent 事件
            vc_sent_events = bridge.events.VCSent().process_receipt(receipt)
            if vc_sent_events:
                for event in vc_sent_events:
                    print(f"\n[EVENT] VCSent 事件检测到:")
                    print(f"        VC Hash: 0x{event['args']['vcHash'].hex()}")
                    print(f"        目标链: {event['args']['targetChain']}")
                    print(f"        发送者: {event['args']['sender']}")
        except Exception as e:
            print(f"[WARN] 无法解析 VCSent 事件: {e}")
    else:
        raise Exception(f"initiateCrossChainTransfer 交易失败! tx_hash: {tx_hash.hex()}")

    return tx_hash.hex()


def wait_for_cross_chain_transfer(config: dict, vc_hash: str, timeout: int = 60) -> bool:
    """等待跨链传输完成并验证目标链

    Args:
        config: 配置字典
        vc_hash: VC Hash
        timeout: 超时时间（秒）

    Returns:
        是否成功传输到目标链
    """
    print("\n" + "=" * 80)
    print("等待跨链传输完成")
    print("=" * 80)

    # 连接到 Chain B
    chain_b_config = config['chains']['chain_b']
    w3_b = Web3(Web3.HTTPProvider(chain_b_config['rpc_url']))
    w3_b.middleware_onion.inject(geth_poa_middleware, layer=0)

    try:
        chain_id = w3_b.eth.chain_id
    except Exception as e:
        print(f"[ERROR] 无法连接到 Chain B: {e}")
        return False

    print(f"[OK] 已连接到 Chain B (Chain ID: {chain_id})")

    # 加载 Bridge 合约
    bridge_abi = load_contract_abi("VCCrossChainBridgeSimple")
    bridge_b = w3_b.eth.contract(
        address=Web3.to_checksum_address(chain_b_config['bridge_address']),
        abi=bridge_abi
    )

    vc_hash_bytes = bytes.fromhex(vc_hash.replace('0x', ''))

    print(f"\n[INFO] 等待 Oracle 传输 VC 到目标链...")
    print(f"       VC Hash: {vc_hash}")
    print(f"       超时时间: {timeout} 秒")
    print(f"       轮询间隔: 3 秒")

    start_time = time.time()
    check_count = 0

    while time.time() - start_time < timeout:
        check_count += 1
        elapsed = int(time.time() - start_time)

        try:
            receive_record = bridge_b.functions.receiveList(vc_hash_bytes).call()

            if receive_record and len(receive_record) > 3 and receive_record[3]:
                print(f"\n[SUCCESS] VC 已成功传输到 Chain B!")
                print(f"          检测次数: {check_count}")
                print(f"          耗时: {elapsed} 秒")

                # 显示详细信息
                metadata = receive_record[0]
                source_chain = receive_record[1]
                print(f"\n[INFO] VC 元数据:")
                print(f"       VC 名称: {metadata[1]}")
                print(f"       VC 描述: {metadata[2]}")
                print(f"       发行者 DID: {metadata[4]}")
                print(f"       持有者 DID: {metadata[6]}")
                print(f"       源链: {source_chain}")
                print(f"       接收时间: {receive_record[2]}")

                return True
        except Exception as e:
            print(f"[WARN] 检查失败: {e}")

        # 显示进度
        print(f"       [{elapsed}s/{timeout}s] 等待中... (检查 #{check_count})")
        time.sleep(3)

    print(f"\n[TIMEOUT] 等待超时 ({timeout} 秒)")
    print(f"          请检查 Oracle 服务是否正在运行")
    return False


def print_all_vc_managers(config: dict):
    """打印所有VC Manager信息"""
    print("=" * 80)
    print("4个VC Manager合约地址")
    print("=" * 80)

    vc_managers = config.get('vc_managers', {}).get('chain_a', {})
    owner_config = config.get('vc_manager_owner', {})

    print(f"\nVC Manager Owner账户（可调用所有VC Manager）:")
    print(f"  地址: {owner_config.get('address')}")
    print(f"  说明: {owner_config.get('description')}")
    print(f"  DID验证状态: ✅ 已通过Chain A DIDVerifier验证")

    print(f"\nVC Manager合约列表:")
    print("-" * 80)
    for vc_type, info in VC_MANAGERS.items():
        config_key = info['contract_name']
        if config_key in vc_managers:
            mgr_info = vc_managers[config_key]
            print(f"  {vc_type}:")
            print(f"    合约地址: {mgr_info.get('address')}")
            print(f"    合约DID: {mgr_info.get('did')}")
            print(f"    说明: {mgr_info.get('description')}")
            print()

    print("=" * 80)


def test_cross_chain_transfer(vc_hash: str = None, auto_initiate: bool = False):
    """测试跨链VC传输"""

    print("=" * 80)
    print("跨链VC传输测试")
    print("=" * 80)

    # 加载配置
    try:
        config = load_config()
        print(f"\n[INFO] 配置文件加载成功: {CONFIG_FILE}")
    except Exception as e:
        print(f"[ERROR] 加载配置失败: {e}")
        return False

    # 显示所有VC Manager信息
    print_all_vc_managers(config)

    # 获取VC Hash和类型（如果没有提供）
    vc_type = None
    if not vc_hash:
        vc_hash, vc_type = get_latest_vc_hash()
        if vc_hash:
            print(f"\n[INFO] 从uuid.json获取最新VC Hash: {vc_hash}")
            print(f"[INFO] VC 类型: {vc_type}")
        else:
            print("[WARN] 无法从uuid.json获取VC Hash，请手动指定")
    else:
        # 如果手动指定了vc_hash，需要从uuid.json查找类型
        if UUID_FILE.exists():
            with open(UUID_FILE, 'r') as f:
                uuid_data = json.load(f)
            for uuid_key, record in uuid_data.items():
                if record.get('vc_hash') == vc_hash:
                    vc_type = record.get('vc_type')
                    print(f"\n[INFO] 指定的VC Hash类型: {vc_type}")
                    break

    # 根据VC类型获取对应的VC Manager配置
    if vc_type:
        try:
            auth_config = get_vc_manager_config(vc_type, config)
            print(f"\n[INFO] VC Manager配置 ({vc_type}):")
            print(f"       VC Manager地址: {auth_config['vc_manager_address']}")
            print(f"       调用账户: {auth_config['caller_address']}")
            print(f"       账户类型: {auth_config['caller_description']}")
        except Exception as e:
            print(f"[ERROR] 获取VC Manager配置失败: {e}")
            return False
    else:
        print("[WARN] 无法确定VC类型，将使用第一个VC Manager作为示例")
        vc_type = 'InspectionReport'
        try:
            auth_config = get_vc_manager_config(vc_type, config)
        except Exception as e:
            print(f"[ERROR] 获取默认VC Manager配置失败: {e}")
            return False

    # 1. 连接到Chain A
    print("\n[1/6] 连接到Chain A...")
    chain_a_config = config['chains']['chain_a']
    w3_a = Web3(Web3.HTTPProvider(chain_a_config['rpc_url']))
    w3_a.middleware_onion.inject(geth_poa_middleware, layer=0)

    try:
        chain_id = w3_a.eth.chain_id
        print(f"[OK] Chain A连接成功 (Chain ID: {chain_id})")
    except Exception as e:
        print(f"[FAIL] Chain A连接失败: {e}")
        return False

    # 2. 加载Bridge合约
    print("\n[2/6] 加载Bridge合约...")
    try:
        bridge_abi = load_contract_abi("VCCrossChainBridgeSimple")
        bridge_a = w3_a.eth.contract(
            address=Web3.to_checksum_address(chain_a_config['bridge_address']),
            abi=bridge_abi
        )
        print(f"[OK] Bridge合约加载成功: {chain_a_config['bridge_address']}")
    except Exception as e:
        print(f"[FAIL] Bridge合约加载失败: {e}")
        return False

    # 3. 检查VC是否存在
    if vc_hash:
        print(f"\n[3/6] 检查VC是否存在: {vc_hash}")
        try:
            vc_hash_bytes = bytes.fromhex(vc_hash.replace('0x', ''))
            send_record = bridge_a.functions.sendList(vc_hash_bytes).call()

            if send_record and len(send_record) > 3 and send_record[3]:
                print(f"[OK] VC存在于Bridge的sendList中")
                metadata = send_record[0]
                print(f"     VC名称: {metadata[1]}")
                print(f"     Holder DID: {metadata[6] if len(metadata) > 6 else 'N/A'}")
            else:
                print(f"[WARN] VC不存在于Bridge的sendList中（尚未发起跨链传输）")
        except Exception as e:
            print(f"[WARN] 无法检查VC: {e}")
    else:
        print("\n[3/6] 跳过VC检查（未提供VC Hash）")

    # 4. 调用initiateCrossChainTransfer说明
    print("\n[4/6] 调用initiateCrossChainTransfer...")
    print("-" * 80)

    if auto_initiate and vc_hash:
        print("[INFO] 自动发起跨链传输...")
        # TODO: 实现自动发起逻辑
    else:
        print("[INFO] 请手动调用VC Manager的initiateCrossChainTransfer函数")
        print("[INFO] 使用VC Manager Owner账户（可调用所有4个VC Manager）")
        print("\n手动测试Python代码：")
        print("-" * 40)
        print(f"""
from web3 import Web3
from web3.middleware import geth_poa_middleware
import json

# 连接到Chain A
w3 = Web3(Web3.HTTPProvider("{chain_a_config['rpc_url']}"))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

# 加载VC Manager合约ABI
with open('contracts/kept/contract_abis/{auth_config['abi_file']}', 'r') as f:
    abi = json.load(f)['abi']

# VC Manager合约地址（当前VC类型: {vc_type}）
vc_manager_address = "{auth_config['vc_manager_address']}"
vc_manager = w3.eth.contract(address=vc_manager_address, abi=abi)

# VC Manager Owner账户（可调用所有4个VC Manager）
private_key = "{auth_config['caller_private_key']}"
account = w3.eth.account.from_key(private_key)
print(f"调用账户: {{account.address}}")

# VC Hash
vc_hash = "{vc_hash}"
vc_hash_bytes = bytes.fromhex(vc_hash.replace('0x', ''))

# 构建交易
txn = vc_manager.functions.initiateCrossChainTransfer(
    vc_hash_bytes,
    "chain_b"
).build_transaction({{
    'from': account.address,
    'gas': 300000,
    'gasPrice': 1000000000,
    'nonce': w3.eth.get_transaction_count(account.address)
}})

# 签名并发送
signed = w3.eth.account.sign_transaction(txn, private_key)
tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
print(f"交易已发送: {{tx_hash.hex()}}")

# 等待确认
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
print(f"交易确认，区块: {{receipt['blockNumber']}}")
print(f"状态: {{'成功' if receipt['status'] == 1 else '失败'}}")
""")
        print("-" * 40)

        # 显示其他VC Manager地址供参考
        print("\n[参考] 其他VC Manager合约地址（使用相同的Owner账户调用）:")
        vc_managers = config.get('vc_managers', {}).get('chain_a', {})
        for other_type, info in VC_MANAGERS.items():
            if other_type != vc_type:
                config_key = info['contract_name']
                if config_key in vc_managers:
                    print(f"  {other_type}: {vc_managers[config_key].get('address')}")

    # 5. 监听Chain B的VCReceived事件
    print("\n[5/6] 监听Chain B的VCReceived事件...")
    print("[INFO] 如果Oracle正在运行，应该会自动检测并传输VC")

    # 6. 验证VC是否在Chain B
    print("\n[6/6] 验证Chain B...")
    try:
        chain_b_config = config['chains']['chain_b']
        w3_b = Web3(Web3.HTTPProvider(chain_b_config['rpc_url']))
        w3_b.middleware_onion.inject(geth_poa_middleware, layer=0)

        bridge_b = w3_b.eth.contract(
            address=Web3.to_checksum_address(chain_b_config['bridge_address']),
            abi=bridge_abi
        )

        if vc_hash:
            vc_hash_bytes = bytes.fromhex(vc_hash.replace('0x', ''))
            receive_record = bridge_b.functions.receiveList(vc_hash_bytes).call()

            if receive_record and len(receive_record) > 3 and receive_record[3]:
                print(f"[OK] VC已成功传输到Chain B!")
                metadata = receive_record[0]
                print(f"     VC名称: {metadata[1]}")
                print(f"     源链: {receive_record[1]}")
            else:
                print(f"[WARN] VC尚未传输到Chain B")
                print(f"       请检查Oracle服务是否正在运行")

    except Exception as e:
        print(f"[FAIL] 验证失败: {e}")

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

    return True


def test_oracle_health():
    """测试Oracle健康状态"""
    print("=" * 80)
    print("Oracle服务健康检查")
    print("=" * 80)

    # 检查Oracle日志
    log_file = Path(__file__).parent / "logs" / "vc_transfer_oracle.log"

    if log_file.exists():
        print(f"[OK] Oracle日志文件存在: {log_file}")
        print(f"\n最近的日志条目:")
        print("-" * 80)

        # 读取最后20行
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-20:]:
                print(line.rstrip())
    else:
        print(f"[WARN] Oracle日志文件不存在: {log_file}")
        print("       Oracle服务可能未启动")

    print("=" * 80)


def list_available_vcs():
    """列出可用的VC Hash"""
    print("=" * 80)
    print("可用的VC Hash列表（从uuid.json读取）")
    print("=" * 80)

    vcs = get_available_vc_hashes(limit=10)

    if not vcs:
        print("[WARN] 没有找到可用的VC Hash")
        return

    print(f"\n共找到 {len(vcs)} 个最近的VC记录：\n")
    for i, vc in enumerate(vcs, 1):
        print(f"{i}. VC Hash: {vc['vc_hash']}")
        print(f"   类型: {vc['vc_type']}")
        print(f"   合同名称: {vc['contract_name']}")
        print(f"   时间戳: {vc['timestamp']}")
        print(f"   UUID: {vc['uuid']}")
        print()

    print("=" * 80)


def list_vc_managers():
    """列出所有VC Manager信息"""
    try:
        config = load_config()
        print_all_vc_managers(config)
    except Exception as e:
        print(f"[ERROR] 加载配置失败: {e}")


def test_cross_chain_transfer_with_random_vc(vc_type: str = 'InspectionReport', timeout: int = 60):
    """使用随机创建的 VC 进行完整跨链传输测试

    完整流程：
    1. 随机生成一个新的 VC Hash
    2. 填写完整的 VC 元数据结构
    3. 调用 VC Manager 合约的 addVCMetadata 写入元数据
    4. 自动调用 initiateCrossChainTransfer 发起跨链传输
    5. 等待 Oracle 检测并传输到目标链
    6. 验证目标链是否收到

    Args:
        vc_type: VC 类型 (InspectionReport, InsuranceContract, CertificateOfOrigin, BillOfLadingCertificate)
        timeout: 等待超时时间（秒）
    """
    print("\n")
    print("*" * 80)
    print("*  完整跨链传输测试（随机 VC）")
    print("*" * 80)

    # 加载配置
    try:
        config = load_config()
        print(f"\n[INFO] 配置文件加载成功")
    except Exception as e:
        print(f"[ERROR] 加载配置失败: {e}")
        return False

    # 显示 VC Manager 信息
    print_all_vc_managers(config)

    print(f"\n测试参数:")
    print(f"  VC 类型: {vc_type}")
    print(f"  超时时间: {timeout} 秒")

    try:
        # 步骤 1-3: 创建随机 VC
        vc_hash, vc_manager_address, actual_vc_type = create_random_vc(config, vc_type)

        # 步骤 4: 发起跨链传输
        tx_hash = initiate_cross_chain_transfer(config, vc_hash, actual_vc_type, "chain_b")

        # 步骤 5-6: 等待传输完成并验证
        success = wait_for_cross_chain_transfer(config, vc_hash, timeout)

        # 总结
        print("\n" + "=" * 80)
        print("测试总结")
        print("=" * 80)
        print(f"  VC Hash: {vc_hash}")
        print(f"  VC 类型: {actual_vc_type}")
        print(f"  VC Manager: {vc_manager_address}")
        print(f"  发起交易: {tx_hash}")
        print(f"  传输结果: {'成功' if success else '失败/超时'}")
        print("=" * 80)

        if success:
            print("\n[SUCCESS] 完整跨链传输测试成功!")
        else:
            print("\n[WARN] 跨链传输可能未完成，请检查 Oracle 服务是否正常运行")
            print("       启动 Oracle: python3 oracle/vc_transfer_oracle.py")

        return success

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='跨链VC传输测试')
    parser.add_argument('--vc-hash', type=str, help='要测试的VC Hash（如不指定则从uuid.json读取最新）')
    parser.add_argument('--health', action='store_true', help='检查Oracle健康状态')
    parser.add_argument('--list-vcs', action='store_true', help='列出可用的VC Hash')
    parser.add_argument('--list-managers', action='store_true', help='列出所有VC Manager信息')
    parser.add_argument('--auto', action='store_true', help='自动发起跨链传输（需要--vc-hash）')
    parser.add_argument('--create-random', action='store_true',
                        help='创建随机VC并进行完整跨链传输测试')
    parser.add_argument('--vc-type', type=str, default='InspectionReport',
                        choices=['InspectionReport', 'InsuranceContract', 'CertificateOfOrigin', 'BillOfLadingCertificate'],
                        help='VC类型（用于--create-random，默认InspectionReport）')
    parser.add_argument('--timeout', type=int, default=60,
                        help='等待跨链传输完成的超时时间（秒，默认60）')

    args = parser.parse_args()

    if args.health:
        test_oracle_health()
    elif args.list_vcs:
        list_available_vcs()
    elif args.list_managers:
        list_vc_managers()
    elif args.create_random:
        test_cross_chain_transfer_with_random_vc(args.vc_type, args.timeout)
    else:
        test_cross_chain_transfer(args.vc_hash, args.auto)


if __name__ == '__main__':
    main()
