pragma solidity ^0.5.16;

/**
 * @title SimpleCrossChainToken
 * @dev 简化的跨链代币合约，不强制要求DID验证
 */
contract SimpleCrossChainToken {
    string public name;
    string public symbol;
    uint8 public decimals;
    uint256 public totalSupply;
    
    mapping(address => uint256) public balances;
    mapping(address => mapping(address => uint256)) public allowances;
    
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    
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
        balances[msg.sender] = _totalSupply;
        
        emit Transfer(address(0), msg.sender, _totalSupply);
    }
    
    function balanceOf(address account) public view returns (uint256) {
        return balances[account];
    }
    
    function allowance(address owner, address spender) public view returns (uint256) {
        return allowances[owner][spender];
    }
    
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
    
    function mint(address to, uint256 amount) public returns (bool) {
        require(to != address(0), "Mint to zero address");
        require(amount > 0, "Mint amount must be greater than 0");
        
        totalSupply += amount;
        balances[to] += amount;
        
        emit Transfer(address(0), to, amount);
        return true;
    }
    
    function burn(address from, uint256 amount) public returns (bool) {
        require(from != address(0), "Burn from zero address");
        require(amount > 0, "Burn amount must be greater than 0");
        require(balances[from] >= amount, "Insufficient balance");
        
        balances[from] -= amount;
        totalSupply -= amount;
        
        emit Transfer(from, address(0), amount);
        return true;
    }
}
