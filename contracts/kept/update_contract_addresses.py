#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新合约地址配置
用新部署的合约地址替换配置文件中的旧地址
"""

import json
import shutil
from datetime import datetime

# 文件路径
CONFIG_DIR = "/home/manifold/cursor/cross-chain/config"
ADDRESS_JSON = f"{CONFIG_DIR}/address.json"
DID_ADDRESS_MAP_JSON = f"{CONFIG_DIR}/did_address_map.json"

# 新部署的合约地址映射
NEW_CONTRACT_ADDRESSES = {
    # Chain A
    "chain_a_cross_chain_bridge": "0xBE2f7922184ac214FCf6Eb81cbC169c2de9A2763",
    "chain_a_inspection_report": "0xf5573AA77552858d70384FCAC615EeDb4e05Ba7B",
    "chain_a_insurance_contract": "0xC1e2E535D3979F868455A82D208EfABdC3174aa5",
    "chain_a_certificate_of_origin": "0x8499286b6d3B9c4b9c15A8A855a8B4839026fD7C",
    "chain_a_bill_of_lading": "0xA9a4074B2A92E63e4c7DC440E80ea1f76a28F701",

    # Chain B
    "chain_b_cross_chain_bridge": "0x0B3c2d586e02e9CB9E1cE02fa2BB1B0CD71fDac6",
}

def backup_file(filepath):
    """备份文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{filepath}.backup_{timestamp}"
    shutil.copy2(filepath, backup_path)
    print(f"✅ 备份已创建: {backup_path}")
    return backup_path

def update_address_json():
    """更新address.json"""
    print("\n" + "="*70)
    print("📝 更新 address.json")
    print("="*70)

    # 备份
    backup_file(ADDRESS_JSON)

    # 读取
    with open(ADDRESS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 更新Chain A合约地址
    print("\n更新 Chain A 合约地址:")
    data['contracts']['chain_a']['cross_chain_bridge'] = NEW_CONTRACT_ADDRESSES['chain_a_cross_chain_bridge']
    print(f"  ✅ cross_chain_bridge: {data['contracts']['chain_a']['cross_chain_bridge']}")

    data['contracts']['chain_a']['vc_managers']['inspection_report'] = NEW_CONTRACT_ADDRESSES['chain_a_inspection_report']
    print(f"  ✅ inspection_report: {data['contracts']['chain_a']['vc_managers']['inspection_report']}")

    data['contracts']['chain_a']['vc_managers']['insurance_contract'] = NEW_CONTRACT_ADDRESSES['chain_a_insurance_contract']
    print(f"  ✅ insurance_contract: {data['contracts']['chain_a']['vc_managers']['insurance_contract']}")

    data['contracts']['chain_a']['vc_managers']['certificate_of_origin'] = NEW_CONTRACT_ADDRESSES['chain_a_certificate_of_origin']
    print(f"  ✅ certificate_of_origin: {data['contracts']['chain_a']['vc_managers']['certificate_of_origin']}")

    data['contracts']['chain_a']['vc_managers']['bill_of_lading'] = NEW_CONTRACT_ADDRESSES['chain_a_bill_of_lading']
    print(f"  ✅ bill_of_lading: {data['contracts']['chain_a']['vc_managers']['bill_of_lading']}")

    # 更新Chain B合约地址
    print("\n更新 Chain B 合约地址:")
    data['contracts']['chain_b']['cross_chain_bridge'] = NEW_CONTRACT_ADDRESSES['chain_b_cross_chain_bridge']
    print(f"  ✅ cross_chain_bridge: {data['contracts']['chain_b']['cross_chain_bridge']}")

    # 更新时间戳
    data['contracts']['last_updated'] = datetime.now().isoformat()

    # 保存
    with open(ADDRESS_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ address.json 已更新并保存")

def update_did_address_map_json():
    """更新did_address_map.json"""
    print("\n" + "="*70)
    print("📝 更新 did_address_map.json")
    print("="*70)

    # 备份
    backup_file(DID_ADDRESS_MAP_JSON)

    # 读取
    with open(DID_ADDRESS_MAP_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 需要更新的地址映射（旧地址 → 新地址）
    address_replacements = {
        # Chain A
        "0x9F89BEBF6b9A53Aa5D5323f0D22fE199357cbEca": NEW_CONTRACT_ADDRESSES['chain_a_cross_chain_bridge'],
        "0x53a73586bB0A57EA620cF2DbE212CBc47c18DEEe": NEW_CONTRACT_ADDRESSES['chain_a_inspection_report'],
        "0x5cbfFae650D8D6C0730270baF210D9E466Ce2cEd": NEW_CONTRACT_ADDRESSES['chain_a_insurance_contract'],
        "0xE313E8436b3f045C652EB4fea8C2Ca68F5805138": NEW_CONTRACT_ADDRESSES['chain_a_certificate_of_origin'],
        "0x8Ee25887BB373032b5F5277E15ea7876216c0801": NEW_CONTRACT_ADDRESSES['chain_a_bill_of_lading'],

        # Chain B
        "0x4675a1BD937363fe1E7b6fF2129F3f7f3ccB10Df": NEW_CONTRACT_ADDRESSES['chain_b_cross_chain_bridge'],
    }

    print("\n更新 mappings 数组:")
    updated_count = 0
    for mapping in data['mappings']:
        old_addr = mapping['address']
        if old_addr in address_replacements:
            new_addr = address_replacements[old_addr]
            mapping['address'] = new_addr
            print(f"  ✅ Index {mapping['index']} ({mapping['address_label']}):")
            print(f"     {old_addr}")
            print(f"     → {new_addr}")
            updated_count += 1

    print(f"\n共更新了 {updated_count} 个合约地址")

    # 更新indexes.by_address
    print("\n更新 indexes.by_address:")
    for old_addr, new_addr in address_replacements.items():
        if old_addr in data['indexes']['by_address']:
            # 保留DID映射
            did_list = data['indexes']['by_address'][old_addr]
            data['indexes']['by_address'][new_addr] = did_list
            del data['indexes']['by_address'][old_addr]
            print(f"  ✅ {old_addr} → {new_addr}")

    # 保存
    with open(DID_ADDRESS_MAP_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ did_address_map.json 已更新并保存")

def verify_updates():
    """验证更新结果"""
    print("\n" + "="*70)
    print("🔍 验证更新结果")
    print("="*70)

    # 读取更新后的文件
    with open(ADDRESS_JSON, 'r') as f:
        address_data = json.load(f)

    with open(DID_ADDRESS_MAP_JSON, 'r') as f:
        did_map_data = json.load(f)

    print("\n✅ address.json 验证:")
    print(f"  Chain A cross_chain_bridge: {address_data['contracts']['chain_a']['cross_chain_bridge']}")
    print(f"  Chain A inspection_report: {address_data['contracts']['chain_a']['vc_managers']['inspection_report']}")
    print(f"  Chain A insurance_contract: {address_data['contracts']['chain_a']['vc_managers']['insurance_contract']}")
    print(f"  Chain A certificate_of_origin: {address_data['contracts']['chain_a']['vc_managers']['certificate_of_origin']}")
    print(f"  Chain A bill_of_lading: {address_data['contracts']['chain_a']['vc_managers']['bill_of_lading']}")
    print(f"  Chain B cross_chain_bridge: {address_data['contracts']['chain_b']['cross_chain_bridge']}")

    print("\n✅ did_address_map.json 验证:")
    chain_a_bridge = None
    chain_b_bridge = None

    for mapping in did_map_data['mappings']:
        if mapping['address_label'] == 'Chain A Cross Chain Bridge':
            chain_a_bridge = mapping['address']
        elif mapping['address_label'] == 'Chain B Cross Chain Bridge':
            chain_b_bridge = mapping['address']

    print(f"  Chain A bridge: {chain_a_bridge}")
    print(f"  Chain B bridge: {chain_b_bridge}")

    # 检查一致性
    if chain_a_bridge == address_data['contracts']['chain_a']['cross_chain_bridge']:
        print("\n✅ Chain A 桥地址一致")
    else:
        print("\n❌ Chain A 桥地址不一致！")

    if chain_b_bridge == address_data['contracts']['chain_b']['cross_chain_bridge']:
        print("✅ Chain B 桥地址一致")
    else:
        print("❌ Chain B 桥地址不一致！")

    print("\n✅ 所有验证完成！")

def main():
    print("="*70)
    print("🚀 更新合约地址配置")
    print("="*70)
    print("\n将用以下新地址替换旧地址:")
    for key, value in NEW_CONTRACT_ADDRESSES.items():
        print(f"  {key}: {value}")

    try:
        # 更新address.json
        update_address_json()

        # 更新did_address_map.json
        update_did_address_map_json()

        # 验证更新
        verify_updates()

        print("\n" + "="*70)
        print("🎉 所有配置文件更新完成！")
        print("="*70)

        return True

    except Exception as e:
        print(f"\n❌ 更新失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
