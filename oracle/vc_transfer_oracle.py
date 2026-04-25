#!/usr/bin/env python3
"""
跨链VC元数据传输Oracle服务

功能：
1. 监听源链上VCCrossChainBridgeSimple合约的VCSent事件
2. 从源链Bridge合约的sendList获取VC元数据
3. 将VC元数据写入目标链的VCCrossChainBridgeSimple合约

配置文件：config/cross_chain_oracle_config.json
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime

from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from oracle.web3_fixed_connection import FixedWeb3

# 配置日志
def setup_logging(config: Dict) -> logging.Logger:
    """设置日志系统"""
    log_dir = Path(config['logging']['log_dir'])
    log_dir.mkdir(parents=True, exist_ok=True)

    # 创建logger
    logger = logging.getLogger('VCTransferOracle')
    logger.setLevel(getattr(logging, config['logging'].get('level', 'INFO')))

    # 清除现有handlers
    logger.handlers.clear()

    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )

    # 主日志文件
    main_handler = logging.FileHandler(log_dir / config['logging']['log_file'], encoding='utf-8')
    main_handler.setFormatter(formatter)
    logger.addHandler(main_handler)

    # 成功日志文件
    success_handler = logging.FileHandler(
        log_dir / config['logging']['success_log'],
        encoding='utf-8'
    )
    success_handler.setFormatter(formatter)
    success_handler.setLevel(logging.INFO)
    logger.addHandler(success_handler)

    # 错误日志文件
    error_handler = logging.FileHandler(
        log_dir / config['logging']['error_log'],
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    logger.addHandler(error_handler)

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


class VCTransferOracle:
    """跨链VC元数据传输Oracle服务"""

    def __init__(self, config_path: str):
        """初始化Oracle服务"""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.logger = setup_logging(self.config)

        # 运行状态
        self.running = False
        self.connections = {}
        self.last_blocks = {}

        # 去重缓存
        self.processed_cache = {}

        # 状态文件
        self.state_file = Path(self.config['state']['state_file'])
        self._load_state()

        self.logger.info("=" * 80)
        self.logger.info("跨链VC元数据传输Oracle服务初始化")
        self.logger.info(f"Oracle DID: {self.config['oracle']['did']}")
        self.logger.info(f"Oracle地址: {self.config['oracle']['address']}")
        self.logger.info("=" * 80)

    def _load_config(self) -> Dict:
        """加载配置文件"""
        try:
            config_path = self.config_path
            if not config_path.exists():
                # 尝试相对于项目根目录的路径
                project_root = Path(__file__).parent.parent
                config_path = project_root / config_path

            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            print(f"✅ 配置文件加载成功: {config_path}")
            return config
        except Exception as e:
            print(f"❌ 配置文件加载失败: {e}")
            sys.exit(1)

    def _load_state(self):
        """加载持久化状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.processed_cache = {k: True for k in state.get('processed_vcs', [])}
                    self.last_blocks = state.get('last_blocks', {})
                self.logger.info(f"状态文件加载成功: {len(self.processed_cache)} 条已处理记录")
            except Exception as e:
                self.logger.warning(f"状态文件加载失败: {e}")

    def _save_state(self):
        """保存持久化状态"""
        try:
            state = {
                'processed_vcs': list(self.processed_cache.keys()),
                'last_blocks': self.last_blocks,
                'last_saved': datetime.now().isoformat()
            }
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"保存状态文件失败: {e}")

    def _initialize_chain_connections(self):
        """初始化所有链的连接"""
        self.logger.info("初始化区块链连接...")

        for chain_key, chain_config in self.config['chains'].items():
            try:
                self.logger.info(f"连接 {chain_config['name']}...")

                # 使用FixedWeb3
                fixed_web3 = FixedWeb3(
                    chain_config['rpc_url'],
                    chain_config['name']
                )

                if not fixed_web3.is_connected():
                    raise Exception(f"连接失败: {chain_config['rpc_url']}")

                # 加载Bridge合约ABI
                bridge_abi_path = Path(chain_config['bridge_abi'])
                if not bridge_abi_path.is_absolute():
                    bridge_abi_path = Path(__file__).parent.parent / bridge_abi_path

                with open(bridge_abi_path, 'r', encoding='utf-8') as f:
                    bridge_abi = json.load(f)['abi']

                # 创建合约实例
                bridge_contract = fixed_web3.w3.eth.contract(
                    address=Web3.to_checksum_address(chain_config['bridge_address']),
                    abi=bridge_abi
                )

                self.connections[chain_key] = {
                    'config': chain_config,
                    'web3': fixed_web3,
                    'bridge': bridge_contract
                }

                # 获取当前区块
                current_block = fixed_web3.w3.eth.block_number
                self.last_blocks[chain_key] = current_block

                self.logger.info(
                    f"✅ {chain_config['name']} 连接成功 "
                    f"(Chain ID: {fixed_web3.get_chain_id()}, "
                    f"当前区块: {current_block})"
                )

            except Exception as e:
                self.logger.error(f"❌ {chain_config['name']} 连接失败: {e}")
                raise

    def _is_processed(self, vc_hash: bytes, source_chain: str) -> bool:
        """检查VC是否已处理"""
        key = f"{vc_hash.hex()}_{source_chain}"
        return self.processed_cache.get(key, False)

    def _mark_as_processed(self, vc_hash: bytes, source_chain: str):
        """标记VC为已处理"""
        key = f"{vc_hash.hex()}_{source_chain}"
        self.processed_cache[key] = True

    async def _get_vc_metadata(self, chain_name: str, vc_hash: bytes) -> Optional[Dict]:
        """从Bridge合约的sendList获取VC元数据"""
        try:
            chain_data = self.connections[chain_name]
            bridge = chain_data['bridge']

            self.logger.info(f"从 {chain_name} Bridge合约获取VC元数据: {vc_hash.hex()}")

            # 直接访问sendList这个public mapping
            send_record = bridge.functions.sendList(vc_hash).call()

            # 检查返回的数据结构
            if len(send_record) < 4:
                self.logger.error(f"sendList返回数据格式不正确: 长度={len(send_record)}")
                return None

            # send_record结构: (VCMetadataSimple_tuple, targetChain, status, timestamp, exists)
            # VCMetadataSimple: (vcHash, vcName, holderEndpoint, holderDID, vcManagerAddress, expiryTime, exists)
            exists = send_record[3]  # 最后的exists字段

            if not exists:
                self.logger.error(f"VC在Bridge中不存在: {vc_hash.hex()}")
                return None

            # 解析数据
            metadata_simple = send_record[0]  # VCMetadataSimple tuple
            target_chain = send_record[1]      # string

            vc_metadata = {
                'vcHash': metadata_simple[0],           # bytes32
                'vcName': metadata_simple[1],            # string
                'holderEndpoint': metadata_simple[2],    # string
                'holderDID': metadata_simple[3],         # string
                'vcManagerAddress': metadata_simple[4],  # address
                'expiryTime': metadata_simple[5],        # uint256
                'exists': metadata_simple[6],            # bool
                'targetChain': target_chain              # string
            }

            self.logger.info(
                f"✅ 获取VC元数据成功: "
                f"名称={vc_metadata['vcName']}, "
                f"目标链={vc_metadata['targetChain']}"
            )

            return vc_metadata

        except Exception as e:
            self.logger.error(f"从Bridge获取VC元数据失败: {e}")
            return None

    async def _write_vc_to_target_chain(
        self,
        target_chain: str,
        vc_metadata: Dict,
        source_chain: str
    ) -> bool:
        """将VC元数据写入目标链"""
        try:
            chain_data = self.connections[target_chain]
            w3 = chain_data['web3'].w3
            bridge = chain_data['bridge']

            oracle_address = Web3.to_checksum_address(self.config['oracle']['address'])
            oracle_private_key = self.config['oracle']['private_key']

            self.logger.info(f"写入VC元数据到 {target_chain}...")

            # 构建交易
            nonce = w3.eth.get_transaction_count(oracle_address)
            gas_price = self.config['blockchain']['gas_price']

            # 准备参数（7个字段）
            vc_hash_bytes = vc_metadata['vcHash']
            vc_name = vc_metadata['vcName']
            holder_endpoint = vc_metadata['holderEndpoint']
            holder_did = vc_metadata['holderDID']
            vc_manager_address = Web3.to_checksum_address(vc_metadata['vcManagerAddress'])
            expiry_time = vc_metadata['expiryTime']

            self.logger.info(f"调用 receiveFromCrossChain: vcHash={vc_hash_bytes.hex()}")

            # 构建交易
            transaction = bridge.functions.receiveFromCrossChain(
                vc_hash_bytes,
                vc_name,
                holder_endpoint,
                holder_did,
                vc_manager_address,
                expiry_time,
                source_chain
            ).build_transaction({
                'from': oracle_address,
                'gas': self.config['blockchain']['gas_limit'],
                'gasPrice': gas_price,
                'nonce': nonce
            })

            # 签名交易
            signed_txn = w3.eth.account.sign_transaction(transaction, oracle_private_key)

            # 发送交易
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            self.logger.info(f"交易已发送: {tx_hash.hex()}")

            # 等待确认
            receipt = w3.eth.wait_for_transaction_receipt(
                tx_hash,
                timeout=self.config['blockchain']['tx_timeout']
            )

            if receipt['status'] == 1:
                self.logger.info(
                    f"✅ 写入目标链成功: "
                    f"tx={tx_hash.hex()}, "
                    f"block={receipt['blockNumber']}, "
                    f"gas_used={receipt['gasUsed']}"
                )
                return True
            else:
                self.logger.error(f"❌ 写入目标链失败: tx={tx_hash.hex()}")
                return False

        except Exception as e:
            self.logger.error(f"写入目标链异常: {e}")
            return False

    async def _handle_vc_sent_event(self, event, source_chain: str):
        """处理VCSent事件"""
        try:
            args = event['args']
            vc_hash = args['vcHash']
            target_chain_name = args['targetChain']
            sender = args['sender']
            holder_endpoint = args.get('holderEndpoint', '')

            # 检查是否已处理
            if self._is_processed(vc_hash, source_chain):
                self.logger.info(f"VC {vc_hash.hex()} 已处理，跳过")
                return

            self.logger.info(
                f"🔔 检测到跨链传输请求: "
                f"VC={vc_hash.hex()}, "
                f"{source_chain} -> {target_chain_name}, "
                f"sender={sender}"
            )

            # 获取VC元数据
            vc_metadata = await self._get_vc_metadata(source_chain, vc_hash)
            if not vc_metadata:
                self.logger.error(f"无法获取VC元数据: {vc_hash.hex()}")
                return

            # 验证目标链
            if vc_metadata['targetChain'] != target_chain_name:
                self.logger.warning(
                    f"目标链不匹配: 事件中={target_chain_name}, "
                    f"元数据中={vc_metadata['targetChain']}, 使用事件中的值"
                )
                target_chain_name = vc_metadata['targetChain']

            # 检查目标链是否存在
            target_chain_key = None
            for key, chain_config in self.config['chains'].items():
                if chain_config['name'] == target_chain_name or key == target_chain_name:
                    target_chain_key = key
                    break

            if not target_chain_key:
                self.logger.error(f"找不到目标链配置: {target_chain_name}")
                return

            # 写入目标链
            success = await self._write_vc_to_target_chain(
                target_chain_key, vc_metadata, source_chain
            )

            if success:
                self._mark_as_processed(vc_hash, source_chain)
                self.logger.info(
                    f"✅ VC跨链传输完成: "
                    f"{vc_hash.hex()}, "
                    f"{source_chain} -> {target_chain_key}"
                )
            else:
                self.logger.error(f"❌ VC跨链传输失败: {vc_hash.hex()}")

        except Exception as e:
            self.logger.error(f"处理VCSent事件失败: {e}")

    async def _monitor_chain_events(self, chain_name: str):
        """监听指定链的VCSent事件"""
        chain_data = self.connections[chain_name]
        w3 = chain_data['web3'].w3
        bridge = chain_data['bridge']

        poll_interval = self.config['monitoring']['poll_interval']

        # 确定起始区块
        if chain_name in self.last_blocks:
            # 从状态文件恢复
            last_block = self.last_blocks[chain_name]
        elif self.config['monitoring']['start_block'] != 'latest':
            # 使用配置的start_block
            last_block = int(self.config['monitoring']['start_block'])
        else:
            # 使用当前区块
            last_block = w3.eth.block_number

        self.logger.info(f"开始监听 {chain_name} 的VCSent事件 (从区块 {last_block})")

        while self.running:
            try:
                current_block = w3.eth.block_number

                if current_block > last_block:
                    # 计算批次大小
                    batch_size = self.config['monitoring']['batch_size']
                    from_block = last_block + 1
                    to_block = min(from_block + batch_size - 1, current_block)

                    self.logger.debug(
                        f"扫描 {chain_name} 区块: {from_block} -> {to_block}"
                    )

                    # 获取VCSent事件
                    try:
                        events = bridge.events.VCSent.get_logs(
                            fromBlock=from_block,
                            toBlock=to_block
                        )

                        if events:
                            self.logger.info(
                                f"发现 {len(events)} 个VCSent事件 "
                                f"({chain_name} 区块 {from_block}-{to_block})"
                            )

                            for event in events:
                                await self._handle_vc_sent_event(event, chain_name)

                        last_block = to_block
                        self.last_blocks[chain_name] = last_block

                    except Exception as e:
                        self.logger.error(f"获取事件失败: {e}")

                # 等待下次轮询
                await asyncio.sleep(poll_interval)

            except Exception as e:
                self.logger.error(f"监听 {chain_name} 事件失败: {e}")
                await asyncio.sleep(10)

    async def _auto_save_state(self):
        """定期保存状态"""
        save_interval = self.config['state'].get('auto_save_interval', 60)
        while self.running:
            await asyncio.sleep(save_interval)
            if self.running:
                self._save_state()
                self.logger.debug("状态已自动保存")

    async def _scan_pending_vcs(self, chain_name: str):
        """启动时扫描未传输的历史遗留 VC

        此方法检查源链 sendList 中的所有 VC，找出尚未传输到目标链的 VC，
        并触发跨链传输。这解决了 Oracle 启动时错过历史事件的问题。
        """
        try:
            chain_data = self.connections[chain_name]
            bridge = chain_data['bridge']

            self.logger.info(f"开始扫描 {chain_name} 的历史遗留 VC...")

            # 获取源链 sendList 中的所有 VC 哈希
            send_list_indexes = bridge.functions.getSendListIndexes().call()
            send_count = len(send_list_indexes)

            if send_count == 0:
                self.logger.info(f"{chain_name} sendList 为空，无需扫描")
                return

            self.logger.info(f"{chain_name} sendList 中有 {send_count} 个 VC")

            # 检查每个 VC 是否需要传输
            pending_count = 0
            for vc_hash_bytes in send_list_indexes:
                vc_hash_hex = vc_hash_bytes.hex()

                # 检查是否已在 processed_cache 中
                if self._is_processed(vc_hash_bytes, chain_name):
                    self.logger.debug(f"VC {vc_hash_hex} 已在处理缓存中，跳过")
                    continue

                # 获取 VC 元数据（包含目标链信息）
                vc_metadata = await self._get_vc_metadata(chain_name, vc_hash_bytes)
                if not vc_metadata:
                    self.logger.error(f"无法获取 VC {vc_hash_hex} 的元数据，跳过")
                    continue

                target_chain_name = vc_metadata['targetChain']

                # 检查目标链是否存在
                target_chain_key = None
                for key, cfg in self.config['chains'].items():
                    if cfg['name'] == target_chain_name or key == target_chain_name:
                        target_chain_key = key
                        break

                if not target_chain_key:
                    self.logger.warning(f"找不到目标链配置: {target_chain_name}，跳过 VC {vc_hash_hex}")
                    continue

                target_bridge = self.connections[target_chain_key]['bridge']

                # 检查目标链是否已接收
                try:
                    receive_record = target_bridge.functions.receiveList(vc_hash_bytes).call()
                    # receive_record 结构: (metadata_tuple, sourceChain, timestamp, exists)
                    already_received = receive_record[3]  # exists 字段
                    if already_received:
                        self.logger.debug(f"VC {vc_hash_hex} 已在目标链 {target_chain_key} 中，跳过")
                        self._mark_as_processed(vc_hash_bytes, chain_name)
                        continue
                except Exception as e:
                    self.logger.debug(f"检查目标链接收状态失败: {e}，继续处理")

                # 需要传输的 VC
                pending_count += 1
                self.logger.info(f"发现未传输的 VC: {vc_hash_hex} -> {target_chain_key}")

                # 写入目标链
                success = await self._write_vc_to_target_chain(
                    target_chain_key, vc_metadata, chain_name
                )

                if success:
                    self._mark_as_processed(vc_hash_bytes, chain_name)
                    self.logger.info(
                        f"✅ 历史遗留 VC 传输完成: "
                        f"{vc_hash_hex}, "
                        f"{chain_name} -> {target_chain_key}"
                    )
                else:
                    self.logger.error(f"❌ 历史遗留 VC 传输失败: {vc_hash_hex}")

            if pending_count == 0:
                self.logger.info(f"✅ {chain_name} 没有需要传输的历史遗留 VC")
            else:
                self.logger.info(f"✅ {chain_name} 历史遗留 VC 扫描完成，处理了 {pending_count} 个未传输的 VC")

        except Exception as e:
            self.logger.error(f"扫描 {chain_name} 历史遗留 VC 失败: {e}")

    async def _run_async(self):
        """异步运行主逻辑"""
        # 首先扫描所有链的历史遗留 VC
        self.logger.info("=" * 80)
        self.logger.info("开始扫描历史遗留 VC...")
        self.logger.info("=" * 80)

        for chain_name in self.config['chains'].keys():
            await self._scan_pending_vcs(chain_name)

        self.logger.info("=" * 80)
        self.logger.info("历史遗留 VC 扫描完成，启动事件监听...")
        self.logger.info("=" * 80)

        # 创建异步任务
        self.logger.info("启动事件监听任务...")
        tasks = []

        # 为每个链创建监听任务
        for chain_name in self.config['chains'].keys():
            task = asyncio.create_task(self._monitor_chain_events(chain_name))
            tasks.append(task)

        # 添加状态自动保存任务
        save_task = asyncio.create_task(self._auto_save_state())
        tasks.append(save_task)

        self.logger.info("=" * 80)
        self.logger.info("🚀 跨链VC元数据传输Oracle服务已启动")
        self.logger.info(f"监听链: {list(self.config['chains'].keys())}")
        self.logger.info(f"轮询间隔: {self.config['monitoring']['poll_interval']} 秒")
        self.logger.info("=" * 80)

        # 等待所有任务完成
        await asyncio.gather(*tasks)

    def start(self):
        """启动Oracle服务"""
        try:
            # 初始化连接
            self._initialize_chain_connections()

            # 设置运行标志
            self.running = True

            # 运行异步主逻辑
            try:
                asyncio.run(self._run_async())
            except KeyboardInterrupt:
                self.logger.info("收到停止信号...")
            finally:
                self.stop()

        except Exception as e:
            self.logger.error(f"启动失败: {e}")
            self.stop()
            sys.exit(1)

    def stop(self):
        """停止Oracle服务"""
        self.logger.info("正在停止Oracle服务...")
        self.running = False

        # 保存状态
        self._save_state()

        self.logger.info("=" * 80)
        self.logger.info("👋 跨链VC元数据传输Oracle服务已停止")
        self.logger.info("=" * 80)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='跨链VC元数据传输Oracle服务')
    parser.add_argument(
        '--config',
        type=str,
        default='config/cross_chain_oracle_config.json',
        help='配置文件路径'
    )

    args = parser.parse_args()

    # 创建并启动Oracle服务
    oracle = VCTransferOracle(args.config)
    oracle.start()


if __name__ == '__main__':
    main()
