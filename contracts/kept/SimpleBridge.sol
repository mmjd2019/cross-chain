// SPDX-License-Identifier: MIT
pragma solidity ^0.5.16;

/**
 * @title SimpleBridge
 * @dev 简化版跨链桥合约，用于测试
 */
contract SimpleBridge {
    address public owner;
    address public verifier;
    string public chainId;
    uint256 public chainType;
    
    // 事件
    event AssetLocked(address indexed user, uint256 amount, address indexed token, string targetChain);
    event AssetUnlocked(address indexed user, uint256 amount, address indexed token, string sourceChain);
    event BridgeOperatorUpdated(address indexed oldOperator, address indexed newOperator);
    
    constructor() public {
        owner = msg.sender;
        chainId = "test_chain";
        chainType = 2; // 支持锁定和解锁
    }
    
    /**
     * @dev 设置验证器地址
     * @param _verifier 验证器地址
     */
    function setVerifier(address _verifier) public {
        require(msg.sender == owner, "Only owner can set verifier");
        verifier = _verifier;
    }
    
    /**
     * @dev 设置链ID
     * @param _chainId 链ID
     */
    function setChainId(string memory _chainId) public {
        require(msg.sender == owner, "Only owner can set chain ID");
        chainId = _chainId;
    }
    
    /**
     * @dev 锁定资产
     * @param _amount 数量
     * @param _token 代币地址
     * @param _targetChain 目标链
     */
    function lockAsset(uint256 _amount, address _token, string memory _targetChain) public {
        require(_amount > 0, "Amount must be greater than 0");
        require(bytes(_targetChain).length > 0, "Target chain cannot be empty");
        
        emit AssetLocked(msg.sender, _amount, _token, _targetChain);
    }
    
    /**
     * @dev 解锁资产
     * @param _amount 数量
     * @param _token 代币地址
     * @param _sourceChain 源链
     */
    function unlockAsset(uint256 _amount, address _token, string memory _sourceChain) public {
        require(_amount > 0, "Amount must be greater than 0");
        require(bytes(_sourceChain).length > 0, "Source chain cannot be empty");
        
        emit AssetUnlocked(msg.sender, _amount, _token, _sourceChain);
    }
    
    /**
     * @dev 获取桥信息
     */
    function getBridgeInfo() public view returns (address, address, string memory, uint256) {
        return (owner, verifier, chainId, chainType);
    }
}
