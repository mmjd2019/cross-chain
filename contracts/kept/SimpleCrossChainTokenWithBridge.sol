pragma solidity ^0.5.16;

/**
 * @title SimpleCrossChainTokenWithBridge
 * @dev 支持跨链转账的简化代币合约
 */
contract SimpleCrossChainTokenWithBridge {
    string public name;
    string public symbol;
    uint8 public decimals;
    uint256 public totalSupply;
    
    mapping(address => uint256) public balances;
    mapping(address => mapping(address => uint256)) public allowances;
    
    // 跨链相关
    address public bridgeContract;
    address public owner;
    bool public crossChainEnabled;
    
    // 跨链锁定记录
    struct CrossChainLock {
        address user;
        uint256 amount;
        string targetChain;
        uint256 lockTime;
        bool isUnlocked;
    }
    
    mapping(bytes32 => CrossChainLock) public crossChainLocks;
    mapping(address => uint256) public lockedBalances;
    
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event CrossChainLocked(address indexed user, uint256 amount, string targetChain, bytes32 lockId);
    event CrossChainUnlocked(address indexed user, uint256 amount, string sourceChain, bytes32 lockId);
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function");
        _;
    }
    
    modifier onlyBridge() {
        require(msg.sender == bridgeContract, "Only bridge can call this function");
        _;
    }
    
    constructor(
        string memory _name,
        string memory _symbol,
        uint8 _decimals,
        uint256 _totalSupply
    ) public {
        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        totalSupply = _totalSupply;
        owner = msg.sender;
        crossChainEnabled = true;
        balances[msg.sender] = _totalSupply;
        
        emit Transfer(address(0), msg.sender, _totalSupply);
    }
    
    function setBridgeContract(address _bridgeContract) public onlyOwner {
        bridgeContract = _bridgeContract;
    }
    
    function setCrossChainEnabled(bool _enabled) public onlyOwner {
        crossChainEnabled = _enabled;
    }
    
    function balanceOf(address account) public view returns (uint256) {
        return balances[account];
    }
    
    function allowance(address owner, address spender) public view returns (uint256) {
        return allowances[owner][spender];
    }
    
    // 标准ERC20转账（同链）
    function transfer(address to, uint256 amount) public returns (bool) {
        require(to != address(0), "Transfer to zero address");
        require(amount > 0, "Transfer amount must be greater than 0");
        require(balances[msg.sender] >= amount, "Insufficient balance");
        
        balances[msg.sender] -= amount;
        balances[to] += amount;
        
        emit Transfer(msg.sender, to, amount);
        return true;
    }
    
    function approve(address spender, uint256 amount) public returns (bool) {
        require(spender != address(0), "Approve to zero address");
        
        allowances[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }
    
    function transferFrom(address from, address to, uint256 amount) public returns (bool) {
        require(from != address(0), "Transfer from zero address");
        require(to != address(0), "Transfer to zero address");
        require(amount > 0, "Transfer amount must be greater than 0");
        require(balances[from] >= amount, "Insufficient balance");
        
        uint256 currentAllowance = allowances[from][msg.sender];
        require(currentAllowance >= amount, "Insufficient allowance");
        
        allowances[from][msg.sender] = currentAllowance - amount;
        
        balances[from] -= amount;
        balances[to] += amount;
        
        emit Transfer(from, to, amount);
        return true;
    }
    
    // 跨链锁定（从当前链锁定代币）
    function crossChainLock(uint256 amount, string memory targetChain) public returns (bytes32) {
        require(crossChainEnabled, "Cross-chain is disabled");
        require(amount > 0, "Amount must be greater than 0");
        require(balances[msg.sender] >= amount, "Insufficient balance");
        require(bytes(targetChain).length > 0, "Invalid target chain");
        
        // 生成锁定ID
        bytes32 lockId = keccak256(abi.encodePacked(
            msg.sender, amount, targetChain, block.timestamp, block.number
        ));
        
        // 锁定代币
        balances[msg.sender] -= amount;
        lockedBalances[msg.sender] += amount;
        
        // 记录锁定信息
        crossChainLocks[lockId] = CrossChainLock({
            user: msg.sender,
            amount: amount,
            targetChain: targetChain,
            lockTime: block.timestamp,
            isUnlocked: false
        });
        
        emit CrossChainLocked(msg.sender, amount, targetChain, lockId);
        return lockId;
    }
    
    // 跨链解锁（在目标链上解锁代币）
    function crossChainUnlock(
        address user,
        uint256 amount,
        string memory sourceChain,
        bytes32 lockId
    ) public onlyBridge returns (bool) {
        require(crossChainEnabled, "Cross-chain is disabled");
        require(user != address(0), "Invalid user address");
        require(amount > 0, "Amount must be greater than 0");
        require(bytes(sourceChain).length > 0, "Invalid source chain");
        require(lockId != bytes32(0), "Invalid lock ID");
        
        // 检查锁定记录是否存在且未解锁
        require(crossChainLocks[lockId].user == address(0) || !crossChainLocks[lockId].isUnlocked, 
                "Lock already exists or already unlocked");
        
        // 解锁代币
        balances[user] += amount;
        
        // 记录解锁信息
        crossChainLocks[lockId] = CrossChainLock({
            user: user,
            amount: amount,
            targetChain: sourceChain,
            lockTime: block.timestamp,
            isUnlocked: true
        });
        
        emit CrossChainUnlocked(user, amount, sourceChain, lockId);
        return true;
    }
    
    // 查询锁定余额
    function getLockedBalance(address user) public view returns (uint256) {
        return lockedBalances[user];
    }
    
    // 查询可用余额（总余额 - 锁定余额）
    function getAvailableBalance(address user) public view returns (uint256) {
        return balances[user];
    }
    
    // 查询总余额（可用余额 + 锁定余额）
    function getTotalBalance(address user) public view returns (uint256) {
        return balances[user] + lockedBalances[user];
    }
    
    // 铸造代币（仅限跨链解锁时使用）
    function mint(address to, uint256 amount) public onlyBridge returns (bool) {
        require(to != address(0), "Mint to zero address");
        require(amount > 0, "Mint amount must be greater than 0");
        
        totalSupply += amount;
        balances[to] += amount;
        
        emit Transfer(address(0), to, amount);
        return true;
    }
    
    // 销毁代币（仅限跨链锁定时使用）
    function burn(address from, uint256 amount) public onlyBridge returns (bool) {
        require(from != address(0), "Burn from zero address");
        require(amount > 0, "Burn amount must be greater than 0");
        require(balances[from] >= amount, "Insufficient balance");
        
        balances[from] -= amount;
        totalSupply -= amount;
        
        emit Transfer(from, address(0), amount);
        return true;
    }
}

