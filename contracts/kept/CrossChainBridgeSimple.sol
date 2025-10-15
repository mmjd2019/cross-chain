// SPDX-License-Identifier: MIT
pragma solidity ^0.5.16;

/**
 * @title CrossChainBridgeSimple
 * @dev 简化版跨链桥合约，无构造函数参数
 */
contract CrossChainBridgeSimple {
    address public owner;
    address public verifier;
    string public chainId;
    uint256 public chainType;
    address public bridgeOperator;
    
    // 统计信息
    uint256 public totalLocks;
    uint256 public totalUnlocks;
    
    // 事件
    event AssetLocked(
        address indexed user,
        uint256 amount,
        address indexed token,
        string targetChain,
        bytes32 indexed lockId
    );
    
    event AssetUnlocked(
        address indexed user,
        uint256 amount,
        address indexed token,
        string sourceChain,
        bytes32 indexed sourceTxHash
    );
    
    event BridgeOperatorUpdated(
        address indexed oldOperator,
        address indexed newOperator
    );
    
    constructor() public {
        owner = msg.sender;
        bridgeOperator = msg.sender;
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
     * @dev 设置桥操作员
     * @param _operator 操作员地址
     */
    function setBridgeOperator(address _operator) public {
        require(msg.sender == owner, "Only owner can set bridge operator");
        address oldOperator = bridgeOperator;
        bridgeOperator = _operator;
        emit BridgeOperatorUpdated(oldOperator, _operator);
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
        
        bytes32 lockId = keccak256(abi.encodePacked(
            msg.sender,
            _amount,
            _token,
            _targetChain,
            block.timestamp
        ));
        
        totalLocks++;
        
        emit AssetLocked(msg.sender, _amount, _token, _targetChain, lockId);
    }
    
    /**
     * @dev 解锁资产
     * @param _amount 数量
     * @param _token 代币地址
     * @param _sourceChain 源链
     * @param _sourceTxHash 源交易哈希
     */
    function unlockAsset(
        uint256 _amount,
        address _token,
        string memory _sourceChain,
        bytes32 _sourceTxHash
    ) public {
        require(_amount > 0, "Amount must be greater than 0");
        require(bytes(_sourceChain).length > 0, "Source chain cannot be empty");
        require(_sourceTxHash != bytes32(0), "Source transaction hash cannot be empty");
        
        totalUnlocks++;
        
        emit AssetUnlocked(msg.sender, _amount, _token, _sourceChain, _sourceTxHash);
    }
    
    /**
     * @dev 获取桥信息
     */
    function getBridgeInfo() public view returns (
        address,
        address,
        string memory,
        uint256,
        uint256,
        uint256
    ) {
        return (owner, verifier, chainId, chainType, totalLocks, totalUnlocks);
    }
    
    /**
     * @dev 获取桥统计信息
     */
    function getBridgeStats() public view returns (uint256, uint256) {
        return (totalLocks, totalUnlocks);
    }
}
