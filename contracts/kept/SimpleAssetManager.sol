// SPDX-License-Identifier: MIT
pragma solidity ^0.5.16;

/**
 * @title SimpleAssetManager
 * @dev 简化版资产管理合约，无复杂依赖
 */
contract SimpleAssetManager {
    address public owner;
    string public deploymentMessage;
    
    // 用户余额映射
    mapping(address => uint256) public balances;
    
    // 支持的事件
    event AssetManagerDeployed(string message, address owner);
    event Deposit(address indexed user, uint256 amount);
    event Withdraw(address indexed user, uint256 amount);
    event Transfer(address indexed from, address indexed to, uint256 amount);
    
    constructor() public {
        owner = msg.sender;
        deploymentMessage = "Simple Cross-Chain Asset Manager";
        
        emit AssetManagerDeployed(deploymentMessage, owner);
    }
    
    /**
     * @dev 存款
     */
    function deposit() public payable {
        require(msg.value > 0, "Deposit amount must be greater than 0");
        
        balances[msg.sender] += msg.value;
        emit Deposit(msg.sender, msg.value);
    }
    
    /**
     * @dev 取款
     */
    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        require(amount > 0, "Withdraw amount must be greater than 0");
        
        balances[msg.sender] -= amount;
        msg.sender.transfer(amount);
        emit Withdraw(msg.sender, amount);
    }
    
    /**
     * @dev 转账
     */
    function transfer(address to, uint256 amount) public {
        require(to != address(0), "Transfer to zero address");
        require(balances[msg.sender] >= amount, "Insufficient balance");
        require(amount > 0, "Transfer amount must be greater than 0");
        
        balances[msg.sender] -= amount;
        balances[to] += amount;
        
        emit Transfer(msg.sender, to, amount);
    }
    
    /**
     * @dev 获取用户余额
     */
    function getBalance(address user) public view returns (uint256) {
        return balances[user];
    }
    
    /**
     * @dev 获取合约信息
     */
    function getContractInfo() public view returns (address, string memory, uint256) {
        return (owner, deploymentMessage, address(this).balance);
    }
    
    /**
     * @dev 获取部署消息
     */
    function getDeploymentMessage() public view returns (string memory) {
        return deploymentMessage;
    }
}
