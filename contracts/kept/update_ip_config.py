#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP配置更新脚本
用于更新配置文件中的IP地址
"""

import json
import sys
import os

def update_ip_config(new_ip: str, config_file: str = "cross_chain_vc_config.json"):
    """更新配置文件中的IP地址"""
    try:
        # 读取现有配置
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            print(f"❌ 配置文件不存在: {config_file}")
            return False
        
        # 更新IP地址
        config['server_ip'] = new_ip
        
        # 更新所有URL中的IP地址
        if 'acapy_services' in config:
            if 'issuer' in config['acapy_services']:
                config['acapy_services']['issuer']['admin_url'] = f"http://{new_ip}:8000"
                config['acapy_services']['issuer']['endpoint'] = f"http://{new_ip}:8000"
            
            if 'holder' in config['acapy_services']:
                config['acapy_services']['holder']['admin_url'] = f"http://{new_ip}:8001"
                config['acapy_services']['holder']['endpoint'] = f"http://{new_ip}:8001"
        
        if 'genesis' in config:
            config['genesis']['url'] = f"http://{new_ip}/genesis"
        
        # 保存更新后的配置
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"✅ IP地址已更新为: {new_ip}")
        print(f"✅ 配置文件已保存: {config_file}")
        return True
        
    except Exception as e:
        print(f"❌ 更新IP配置失败: {e}")
        return False

def main():
    """主函数"""
    print("🔧 IP配置更新工具")
    print("=" * 40)
    
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("使用方法: python3 update_ip_config.py <新IP地址>")
        print("示例: python3 update_ip_config.py 192.168.230.178")
        sys.exit(1)
    
    new_ip = sys.argv[1]
    
    # 验证IP地址格式
    import re
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(ip_pattern, new_ip):
        print(f"❌ 无效的IP地址格式: {new_ip}")
        sys.exit(1)
    
    # 更新配置
    success = update_ip_config(new_ip)
    
    if success:
        print("\n🎉 IP配置更新完成！")
        print("现在可以运行跨链VC设置脚本了。")
    else:
        print("\n❌ IP配置更新失败！")
        sys.exit(1)

if __name__ == "__main__":
    main()
