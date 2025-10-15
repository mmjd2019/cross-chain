// SPDX-License-Identifier: MIT
pragma solidity ^0.5.16;

import "./IERC20.sol";
import "./CrossChainDIDVerifier.sol";

/**
 * @title CrossChainToken
 * @dev 支持跨链的ERC20代币合约
 * @author 跨链交易系统
 */
contract CrossChainToken is IERC20 {
    string public name;
    string public symbol;
    uint8 public decimals;
    uint256 public totalSupply;
    
    mapping(address => uint256) public balances;
    mapping(address => mapping(address => uint256)) public allowances;
    
    // 权限管理
    address public owner;
    address public minter; // 铸造权限
    CrossChainDIDVerifier public verifier;
    
    // 跨链相关
    mapping(address => bool) public isCrossChainBridge;
    mapping(address => uint256) public crossChainBalances; // 跨链锁定余额
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }
    
    modifier onlyMinter() {
        require(msg.sender == minter || msg.sender == owner, "Only minter");
        _;
    }
    
    modifier onlyCrossChainBridge() {
        require(isCrossChainBridge[msg.sender], "Only cross-chain bridge");
        _;
    }
    
    modifier onlyVerifiedUser() {
        require(verifier.isUserVerified(msg.sender), "User not verified");
        _;
    }
    
    // 事件定义
    event TokensMinted(address indexed to, uint256 amount);
    event TokensBurned(address indexed from, uint256 amount);
    event CrossChainLocked(address indexed user, uint256 amount);
    event CrossChainUnlocked(address indexed user, uint256 amount);
    event MinterUpdated(address indexed oldMinter, address indexed newMinter);
    event BridgeAuthorized(address indexed bridge, bool authorized);
    
    constructor(
        string memory _name,
        string memory _symbol,
        uint8 _decimals,
        uint256 _initialSupply,
        address _verifierAddress
    ) public {
        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        totalSupply = _initialSupply;
        owner = msg.sender;
        minter = msg.sender;
        verifier = CrossChainDIDVerifier(_verifierAddress);
        
        balances[msg.sender] = _initialSupply;
        emit Transfer(address(0), msg.sender, _initialSupply);
    }
    
    /**
     * @dev 设置铸造者
     * @param _minter 铸造者地址
     */
    function setMinter(address _minter) public onlyOwner {
        address oldMinter = minter;
        minter = _minter;
        emit MinterUpdated(oldMinter, _minter);
    }
    
    /**
     * @dev 授权/取消授权跨链桥
     * @param _bridge 桥地址
     * @param _authorized 是否授权
     */
    function setCrossChainBridge(address _bridge, bool _authorized) public onlyOwner {
        isCrossChainBridge[_bridge] = _authorized;
        emit BridgeAuthorized(_bridge, _authorized);
    }
    
    /**
     * @dev 铸造代币
     * @param _to 接收地址
     * @param _amount 铸造数量
     */
    function mint(address _to, uint256 _amount) public onlyMinter {
        require(_to != address(0), "Mint to zero address");
        require(_amount > 0, "Mint amount must be greater than 0");
        
        totalSupply += _amount;
        balances[_to] += _amount;
        
        emit TokensMinted(_to, _amount);
        emit Transfer(address(0), _to, _amount);
    }
    
    /**
     * @dev 销毁代币
     * @param _from 销毁地址
     * @param _amount 销毁数量
     */
    function burn(address _from, uint256 _amount) public onlyMinter {
        require(_from != address(0), "Burn from zero address");
        require(_amount > 0, "Burn amount must be greater than 0");
        require(balances[_from] >= _amount, "Insufficient balance");
        
        balances[_from] -= _amount;
        totalSupply -= _amount;
        
        emit TokensBurned(_from, _amount);
        emit Transfer(_from, address(0), _amount);
    }
    
    /**
     * @dev 跨链锁定代币
     * @param _user 用户地址
     * @param _amount 锁定数量
     */
    function crossChainLock(address _user, uint256 _amount) public onlyCrossChainBridge {
        require(_user != address(0), "Lock for zero address");
        require(_amount > 0, "Lock amount must be greater than 0");
        require(balances[_user] >= _amount, "Insufficient balance");
        
        balances[_user] -= _amount;
        crossChainBalances[_user] += _amount;
        
        emit CrossChainLocked(_user, _amount);
    }
    
    /**
     * @dev 跨链解锁代币
     * @param _user 用户地址
     * @param _amount 解锁数量
     */
    function crossChainUnlock(address _user, uint256 _amount) public onlyCrossChainBridge {
        require(_user != address(0), "Unlock for zero address");
        require(_amount > 0, "Unlock amount must be greater than 0");
        require(crossChainBalances[_user] >= _amount, "Insufficient cross-chain balance");
        
        crossChainBalances[_user] -= _amount;
        balances[_user] += _amount;
        
        emit CrossChainUnlocked(_user, _amount);
    }
    
    /**
     * @dev 获取用户跨链锁定余额
     * @param _user 用户地址
     * @return 跨链锁定余额
     */
    function getCrossChainBalance(address _user) public view returns (uint256) {
        return crossChainBalances[_user];
    }
    
    // ERC20标准函数实现
    function balanceOf(address account) public view returns (uint256) {
        return balances[account];
    }
    
    function transfer(address to, uint256 amount) public returns (bool) {
        require(verifier.isUserVerified(msg.sender), "Sender not verified");
        require(verifier.isUserVerified(to), "Recipient not verified");
        
        _transfer(msg.sender, to, amount);
        return true;
    }
    
    function allowance(address _owner, address spender) public view returns (uint256) {
        return allowances[_owner][spender];
    }
    
    function approve(address spender, uint256 amount) public returns (bool) {
        require(verifier.isUserVerified(msg.sender), "Sender not verified");
        require(verifier.isUserVerified(spender), "Spender not verified");
        
        allowances[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }
    
    function transferFrom(address from, address to, uint256 amount) public returns (bool) {
        require(verifier.isUserVerified(from), "From not verified");
        require(verifier.isUserVerified(to), "To not verified");
        require(verifier.isUserVerified(msg.sender), "Spender not verified");
        
        uint256 currentAllowance = allowances[from][msg.sender];
        require(currentAllowance >= amount, "Insufficient allowance");
        
        allowances[from][msg.sender] = currentAllowance - amount;
        _transfer(from, to, amount);
        
        return true;
    }
    
    function _transfer(address from, address to, uint256 amount) internal {
        require(from != address(0), "Transfer from zero address");
        require(to != address(0), "Transfer to zero address");
        require(amount > 0, "Transfer amount must be greater than 0");
        require(balances[from] >= amount, "Insufficient balance");
        
        balances[from] -= amount;
        balances[to] += amount;
        
        emit Transfer(from, to, amount);
    }
}
