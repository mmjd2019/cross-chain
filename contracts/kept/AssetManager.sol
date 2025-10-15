// SPDX-License-Identifier: MIT
pragma solidity ^0.5.16;

import "./CrossChainDIDVerifier.sol";
import "./CrossChainBridge.sol";
import "./IERC20.sol";

contract AssetManager {
    CrossChainDIDVerifier public verifier;
    CrossChainBridge public bridge;
    
    mapping(address => uint256) public balances;
    mapping(address => mapping(address => uint256)) public tokenBalances; // 用户代币余额
    
    // 添加消息字段
    string public deploymentMessage;
    
    // 跨链相关
    mapping(address => bool) public supportedTokens;
    mapping(address => TokenInfo) public tokenInfo;
    
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
    
    // 添加事件
    event AssetManagerDeployed(string message, address verifierAddress, address bridgeAddress);
    event Deposit(address indexed user, uint256 amount);
    event Withdraw(address indexed user, uint256 amount);
    event Transfer(address indexed from, address indexed to, uint256 amount);
    event TokenDeposit(address indexed user, address indexed token, uint256 amount);
    event TokenWithdraw(address indexed user, address indexed token, uint256 amount);
    event TokenTransfer(address indexed from, address indexed to, address indexed token, uint256 amount);
    event CrossChainTransferInitiated(address indexed user, address indexed token, uint256 amount, string targetChain);
    event CrossChainTransferCompleted(address indexed user, address indexed token, uint256 amount, string sourceChain);
    event TokenSupported(address indexed token, string name, string symbol);
    event BridgeOperatorUpdated(address indexed oldOperator, address indexed newOperator);
    
    constructor(address _verifierAddress, address _bridgeAddress) public {
        verifier = CrossChainDIDVerifier(_verifierAddress);
        bridge = CrossChainBridge(_bridgeAddress);
        deploymentMessage = "Cross-Chain Asset Manager";
        owner = msg.sender;
        bridgeOperator = msg.sender;
        
        // 发出部署事件
        emit AssetManagerDeployed(deploymentMessage, _verifierAddress, _bridgeAddress);
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
        
        emit TokenSupported(_tokenAddress, _name, _symbol);
    }
    
    /**
     * @dev 移除支持的代币
     * @param _tokenAddress 代币地址
     */
    function removeSupportedToken(address _tokenAddress) public onlyOwner {
        supportedTokens[_tokenAddress] = false;
        tokenInfo[_tokenAddress].isActive = false;
    }
    
    // 原生ETH功能
    function deposit() public payable onlyVerifiedUser {
        balances[msg.sender] += msg.value;
        emit Deposit(msg.sender, msg.value);
    }
    
    function withdraw(uint256 amount) public onlyVerifiedUser {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        
        balances[msg.sender] -= amount;
        msg.sender.transfer(amount);
        emit Withdraw(msg.sender, amount);
    }
    
    function transfer(address to, uint256 amount) public onlyVerifiedUser {
        require(verifier.isUserVerified(to), "Recipient identity not verified");
        require(balances[msg.sender] >= amount, "Insufficient balance");
        
        balances[msg.sender] -= amount;
        balances[to] += amount;
        emit Transfer(msg.sender, to, amount);
    }
    
    // ERC20代币功能
    function depositToken(address tokenAddress, uint256 amount) public onlyVerifiedUser {
        require(supportedTokens[tokenAddress], "Token not supported");
        require(amount > 0, "Amount must be greater than 0");
        
        IERC20 token = IERC20(tokenAddress);
        require(token.transferFrom(msg.sender, address(this), amount), "Transfer failed");
        
        tokenBalances[msg.sender][tokenAddress] += amount;
        emit TokenDeposit(msg.sender, tokenAddress, amount);
    }
    
    function withdrawToken(address tokenAddress, uint256 amount) public onlyVerifiedUser {
        require(supportedTokens[tokenAddress], "Token not supported");
        require(tokenBalances[msg.sender][tokenAddress] >= amount, "Insufficient token balance");
        
        tokenBalances[msg.sender][tokenAddress] -= amount;
        IERC20 token = IERC20(tokenAddress);
        require(token.transfer(msg.sender, amount), "Transfer failed");
        
        emit TokenWithdraw(msg.sender, tokenAddress, amount);
    }
    
    function transferToken(address tokenAddress, address to, uint256 amount) public onlyVerifiedUser {
        require(verifier.isUserVerified(to), "Recipient identity not verified");
        require(supportedTokens[tokenAddress], "Token not supported");
        require(tokenBalances[msg.sender][tokenAddress] >= amount, "Insufficient token balance");
        
        tokenBalances[msg.sender][tokenAddress] -= amount;
        tokenBalances[to][tokenAddress] += amount;
        emit TokenTransfer(msg.sender, to, tokenAddress, amount);
    }
    
    // 跨链功能
    function initiateCrossChainTransfer(
        address tokenAddress,
        uint256 amount,
        string memory targetChain
    ) public onlyVerifiedUser {
        require(supportedTokens[tokenAddress], "Token not supported");
        require(tokenBalances[msg.sender][tokenAddress] >= amount, "Insufficient token balance");
        require(bytes(targetChain).length > 0, "Invalid target chain");
        
        // 锁定代币
        tokenBalances[msg.sender][tokenAddress] -= amount;
        
        // 转移代币到桥合约
        IERC20 token = IERC20(tokenAddress);
        require(token.transfer(address(bridge), amount), "Transfer to bridge failed");
        
        // 调用桥合约的锁定功能
        bridge.lockAssets(amount, tokenAddress, targetChain);
        
        emit CrossChainTransferInitiated(msg.sender, tokenAddress, amount, targetChain);
    }
    
    function completeCrossChainTransfer(
        string memory userDID,
        address tokenAddress,
        uint256 amount,
        string memory sourceChain,
        bytes32 sourceTxHash
    ) public onlyVerifiedUser {
        require(supportedTokens[tokenAddress], "Token not supported");
        require(amount > 0, "Amount must be greater than 0");
        
        // 调用桥合约的解锁功能
        bridge.unlockAssets(userDID, amount, tokenAddress, sourceChain, sourceTxHash);
        
        // 更新用户代币余额
        tokenBalances[msg.sender][tokenAddress] += amount;
        
        emit CrossChainTransferCompleted(msg.sender, tokenAddress, amount, sourceChain);
    }
    
    // 查询函数
    function getDeploymentMessage() public view returns (string memory) {
        return deploymentMessage;
    }
    
    function setDeploymentMessage(string memory _newMessage) public onlyVerifiedUser {
        deploymentMessage = _newMessage;
        emit DeploymentMessageUpdated(_newMessage, msg.sender);
    }
    
    function getTokenBalance(address user, address tokenAddress) public view returns (uint256) {
        return tokenBalances[user][tokenAddress];
    }
    
    function getETHBalance(address user) public view returns (uint256) {
        return balances[user];
    }
    
    function isTokenSupported(address tokenAddress) public view returns (bool) {
        return supportedTokens[tokenAddress] && tokenInfo[tokenAddress].isActive;
    }
    
    function getTokenInfo(address tokenAddress) public view returns (
        string memory name,
        string memory symbol,
        uint8 decimals,
        bool isActive
    ) {
        TokenInfo memory info = tokenInfo[tokenAddress];
        return (info.name, info.symbol, info.decimals, info.isActive);
    }
    
    function getUserDID(address user) public view returns (string memory) {
        return verifier.getUserDID(user);
    }
    
    function isUserVerified(address user) public view returns (bool) {
        return verifier.isUserVerified(user);
    }
    
    // 添加事件
    event DeploymentMessageUpdated(string newMessage, address updater);
}