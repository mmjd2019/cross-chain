// SPDX-License-Identifier: MIT
pragma solidity ^0.5.16;

import "./CrossChainDIDVerifier.sol";
import "./IERC20.sol";

/**
 * @title CrossChainBridge
 * @dev 跨链桥合约，处理资产锁定和解锁
 * @author 跨链交易系统
 */
contract CrossChainBridge {
    CrossChainDIDVerifier public verifier;
    
    // 链信息
    string public chainId;
    uint256 public chainType; // 0=source, 1=destination, 2=both
    
    // 资产锁定记录
    mapping(bytes32 => LockInfo) public lockRecords;
    mapping(bytes32 => bool) public processedLocks; // 防止重复处理
    
    // 支持的代币
    mapping(address => bool) public supportedTokens;
    mapping(address => TokenInfo) public tokenInfo;
    
    // 跨链统计
    uint256 public totalLocks;
    uint256 public totalUnlocks;
    uint256 public totalVolume;
    
    struct LockInfo {
        address user;
        uint256 amount;
        address tokenAddress;
        string targetChain;
        uint256 lockTime;
        bool unlocked;
        string userDID;
    }
    
    struct TokenInfo {
        string name;
        string symbol;
        uint8 decimals;
        bool isActive;
    }
    
    // 权限管理
    address public owner;
    address public bridgeOperator;
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }
    
    modifier onlyBridgeOperator() {
        require(msg.sender == bridgeOperator || msg.sender == owner, "Only bridge operator");
        _;
    }
    
    modifier onlyVerifiedUser() {
        require(verifier.isUserVerified(msg.sender), "User not verified");
        _;
    }
    
    // 事件定义
    event AssetLocked(
        address indexed user,
        uint256 amount,
        address tokenAddress,
        string targetChain,
        bytes32 lockId,
        string userDID
    );
    
    event AssetUnlocked(
        address indexed user,
        uint256 amount,
        address tokenAddress,
        string sourceChain,
        bytes32 lockId,
        string userDID
    );
    
    event TokenSupported(
        address indexed tokenAddress,
        string name,
        string symbol,
        uint8 decimals
    );
    
    event TokenUnsupported(
        address indexed tokenAddress
    );
    
    event BridgeOperatorUpdated(
        address indexed oldOperator,
        address indexed newOperator
    );
    
    constructor(
        address _verifierAddress,
        string memory _chainId,
        uint256 _chainType
    ) public {
        verifier = CrossChainDIDVerifier(_verifierAddress);
        chainId = _chainId;
        chainType = _chainType;
        owner = msg.sender;
        bridgeOperator = msg.sender;
    }
    
    /**
     * @dev 设置桥操作员
     * @param _operator 操作员地址
     */
    function setBridgeOperator(address _operator) public onlyOwner {
        address oldOperator = bridgeOperator;
        bridgeOperator = _operator;
        emit BridgeOperatorUpdated(oldOperator, _operator);
    }
    
    /**
     * @dev 添加支持的代币
     * @param _tokenAddress 代币地址
     * @param _name 代币名称
     * @param _symbol 代币符号
     * @param _decimals 代币精度
     */
    function addSupportedToken(
        address _tokenAddress,
        string memory _name,
        string memory _symbol,
        uint8 _decimals
    ) public onlyOwner {
        supportedTokens[_tokenAddress] = true;
        tokenInfo[_tokenAddress] = TokenInfo({
            name: _name,
            symbol: _symbol,
            decimals: _decimals,
            isActive: true
        });
        
        emit TokenSupported(_tokenAddress, _name, _symbol, _decimals);
    }
    
    /**
     * @dev 移除支持的代币
     * @param _tokenAddress 代币地址
     */
    function removeSupportedToken(address _tokenAddress) public onlyOwner {
        supportedTokens[_tokenAddress] = false;
        tokenInfo[_tokenAddress].isActive = false;
        emit TokenUnsupported(_tokenAddress);
    }
    
    /**
     * @dev 锁定资产（源链功能）
     * @param _amount 锁定数量
     * @param _tokenAddress 代币地址
     * @param _targetChain 目标链ID
     */
    function lockAssets(
        uint256 _amount,
        address _tokenAddress,
        string memory _targetChain
    ) public onlyVerifiedUser {
        require(chainType == 0 || chainType == 2, "Chain cannot lock assets");
        require(supportedTokens[_tokenAddress], "Token not supported");
        require(_amount > 0, "Amount must be greater than 0");
        require(bytes(_targetChain).length > 0, "Invalid target chain");
        require(verifier.isChainSupported(_targetChain), "Target chain not supported");
        
        // 获取用户DID
        string memory userDID = verifier.getUserDID(msg.sender);
        require(bytes(userDID).length > 0, "User DID not found");
        
        // 转移代币到桥合约
        IERC20 token = IERC20(_tokenAddress);
        require(token.transferFrom(msg.sender, address(this), _amount), "Transfer failed");
        
        // 生成锁定ID
        bytes32 lockId = keccak256(abi.encodePacked(
            msg.sender,
            _amount,
            _tokenAddress,
            _targetChain,
            block.timestamp,
            block.number
        ));
        
        // 记录锁定信息
        lockRecords[lockId] = LockInfo({
            user: msg.sender,
            amount: _amount,
            tokenAddress: _tokenAddress,
            targetChain: _targetChain,
            lockTime: block.timestamp,
            unlocked: false,
            userDID: userDID
        });
        
        totalLocks++;
        totalVolume += _amount;
        
        emit AssetLocked(msg.sender, _amount, _tokenAddress, _targetChain, lockId, userDID);
    }
    
    /**
     * @dev 解锁资产（目标链功能）
     * @param _userDID 用户DID
     * @param _amount 解锁数量
     * @param _tokenAddress 代币地址
     * @param _sourceChain 源链ID
     * @param _sourceTxHash 源链交易哈希
     */
    function unlockAssets(
        string memory _userDID,
        uint256 _amount,
        address _tokenAddress,
        string memory _sourceChain,
        bytes32 _sourceTxHash
    ) public onlyVerifiedUser {
        require(chainType == 1 || chainType == 2, "Chain cannot unlock assets");
        require(supportedTokens[_tokenAddress], "Token not supported");
        require(_amount > 0, "Amount must be greater than 0");
        require(bytes(_userDID).length > 0, "Invalid user DID");
        require(bytes(_sourceChain).length > 0, "Invalid source chain");
        
        // 验证跨链证明
        require(verifier.verifyCrossChainProof(_userDID, _sourceChain), "Invalid cross-chain proof");
        
        // 验证用户DID与地址匹配
        require(keccak256(abi.encodePacked(verifier.getUserDID(msg.sender))) == 
                keccak256(abi.encodePacked(_userDID)), "DID-address mismatch");
        
        // 检查是否已处理过此交易
        require(!processedLocks[_sourceTxHash], "Transaction already processed");
        
        // 铸造或转移等效资产
        IERC20 token = IERC20(_tokenAddress);
        
        // 这里需要根据代币合约的实现来决定是mint还是transfer
        // 假设代币合约有mint函数，如果没有则使用transfer
        // 注意：实际部署时需要确保代币合约有mint函数
        require(token.transfer(msg.sender, _amount), "Transfer failed");
        
        processedLocks[_sourceTxHash] = true;
        totalUnlocks++;
        
        emit AssetUnlocked(msg.sender, _amount, _tokenAddress, _sourceChain, _sourceTxHash, _userDID);
    }
    
    /**
     * @dev 紧急解锁（仅限操作员）
     * @param _user 用户地址
     * @param _amount 解锁数量
     * @param _tokenAddress 代币地址
     * @param _reason 解锁原因
     */
    function emergencyUnlock(
        address _user,
        uint256 _amount,
        address _tokenAddress,
        string memory _reason
    ) public onlyBridgeOperator {
        require(supportedTokens[_tokenAddress], "Token not supported");
        require(_amount > 0, "Amount must be greater than 0");
        require(bytes(_reason).length > 0, "Reason required");
        
        IERC20 token = IERC20(_tokenAddress);
        require(token.transfer(_user, _amount), "Transfer failed");
        
        emit AssetUnlocked(_user, _amount, _tokenAddress, "EMERGENCY", bytes32(0), "");
    }
    
    /**
     * @dev 获取锁定信息
     * @param _lockId 锁定ID
     * @return 锁定信息
     */
    function getLockInfo(bytes32 _lockId) public view returns (
        address user,
        uint256 amount,
        address tokenAddress,
        string memory targetChain,
        uint256 lockTime,
        bool unlocked,
        string memory userDID
    ) {
        LockInfo memory lock = lockRecords[_lockId];
        return (
            lock.user,
            lock.amount,
            lock.tokenAddress,
            lock.targetChain,
            lock.lockTime,
            lock.unlocked,
            lock.userDID
        );
    }
    
    /**
     * @dev 获取代币信息
     * @param _tokenAddress 代币地址
     * @return 代币信息
     */
    function getTokenInfo(address _tokenAddress) public view returns (
        string memory name,
        string memory symbol,
        uint8 decimals,
        bool isActive
    ) {
        TokenInfo memory info = tokenInfo[_tokenAddress];
        return (info.name, info.symbol, info.decimals, info.isActive);
    }
    
    /**
     * @dev 获取桥统计信息
     * @return 总锁定数、总解锁数、总交易量
     */
    function getBridgeStats() public view returns (
        uint256 _totalLocks,
        uint256 _totalUnlocks,
        uint256 _totalVolume
    ) {
        return (totalLocks, totalUnlocks, totalVolume);
    }
    
    /**
     * @dev 检查代币是否支持
     * @param _tokenAddress 代币地址
     * @return 是否支持
     */
    function isTokenSupported(address _tokenAddress) public view returns (bool) {
        return supportedTokens[_tokenAddress] && tokenInfo[_tokenAddress].isActive;
    }
    
    /**
     * @dev 获取链类型
     * @return 链类型字符串
     */
    function getChainTypeString() public view returns (string memory) {
        if (chainType == 0) return "SOURCE";
        if (chainType == 1) return "DESTINATION";
        if (chainType == 2) return "BOTH";
        return "UNKNOWN";
    }
}
