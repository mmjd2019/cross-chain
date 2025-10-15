// SPDX-License-Identifier: MIT
pragma solidity ^0.5.16;

/**
 * @title CrossChainDIDVerifier
 * @dev 增强版DID验证器，支持跨链交易验证
 * @author 跨链交易系统
 */
contract CrossChainDIDVerifier {
    // 基础DID映射
    mapping(address => bool) public isVerified;
    mapping(address => string) public didOfAddress;
    mapping(string => address) public addressOfDid;
    
    // 跨链状态记录
    mapping(string => CrossChainProof) public crossChainProofs; // did -> proof
    mapping(bytes32 => bool) public usedProofs; // 防止重放攻击
    mapping(string => bool) public supportedChains; // 支持的链ID
    
    // 跨链证明结构
    struct CrossChainProof {
        string sourceChain;
        string targetChain;
        bytes32 transactionHash;
        uint256 amount;
        address tokenAddress;
        uint256 timestamp;
        bool isValid;
        address userAddress;
    }
    
    // 权限管理
    address public owner;
    address public crossChainOracle;
    mapping(address => bool) public authorizedOracles;
    
    // 配置参数
    uint256 public proofValidityPeriod = 24 hours; // 证明有效期
    uint256 public maxSupportedChains = 10; // 最大支持链数
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }
    
    modifier onlyCrossChainOracle() {
        require(msg.sender == crossChainOracle || authorizedOracles[msg.sender], "Only cross-chain oracle");
        _;
    }
    
    modifier onlyAuthorizedOracle() {
        require(authorizedOracles[msg.sender], "Only authorized oracle");
        _;
    }
    
    // 事件定义
    event IdentityVerified(address indexed user, string did, uint256 timestamp);
    event IdentityRevoked(address indexed user, string did, uint256 timestamp);
    event CrossChainProofRecorded(
        string indexed did,
        string sourceChain,
        string targetChain,
        bytes32 transactionHash,
        uint256 amount,
        address tokenAddress
    );
    event CrossChainProofVerified(
        string indexed did,
        string sourceChain,
        string targetChain,
        bool success
    );
    event ChainSupportUpdated(string chainId, bool supported);
    event OracleAuthorized(address oracle, bool authorized);
    
    constructor() public {
        owner = msg.sender;
    }
    
    /**
     * @dev 设置跨链Oracle地址
     * @param _oracle Oracle地址
     */
    function setCrossChainOracle(address _oracle) public onlyOwner {
        crossChainOracle = _oracle;
    }
    
    /**
     * @dev 授权/取消授权Oracle
     * @param _oracle Oracle地址
     * @param _authorized 是否授权
     */
    function setAuthorizedOracle(address _oracle, bool _authorized) public onlyOwner {
        authorizedOracles[_oracle] = _authorized;
        emit OracleAuthorized(_oracle, _authorized);
    }
    
    /**
     * @dev 验证用户身份（基础功能）
     * @param _user 用户地址
     * @param _did 用户DID
     */
    function verifyIdentity(address _user, string memory _did) public onlyAuthorizedOracle {
        isVerified[_user] = true;
        didOfAddress[_user] = _did;
        addressOfDid[_did] = _user;
        
        emit IdentityVerified(_user, _did, block.timestamp);
    }
    
    /**
     * @dev 撤销身份验证
     * @param _user 用户地址
     */
    function revokeVerification(address _user) public onlyAuthorizedOracle {
        string memory did = didOfAddress[_user];
        isVerified[_user] = false;
        delete didOfAddress[_user];
        delete addressOfDid[did];
        
        emit IdentityRevoked(_user, did, block.timestamp);
    }
    
    /**
     * @dev 添加支持的链
     * @param _chainId 链ID
     */
    function addSupportedChain(string memory _chainId) public onlyOwner {
        require(bytes(_chainId).length > 0, "Invalid chain ID");
        supportedChains[_chainId] = true;
        emit ChainSupportUpdated(_chainId, true);
    }
    
    /**
     * @dev 移除支持的链
     * @param _chainId 链ID
     */
    function removeSupportedChain(string memory _chainId) public onlyOwner {
        supportedChains[_chainId] = false;
        emit ChainSupportUpdated(_chainId, false);
    }
    
    /**
     * @dev 记录跨链证明
     * @param _did 用户DID
     * @param _sourceChain 源链ID
     * @param _targetChain 目标链ID
     * @param _transactionHash 交易哈希
     * @param _amount 金额
     * @param _tokenAddress 代币地址
     * @param _userAddress 用户地址
     */
    function recordCrossChainProof(
        string memory _did,
        string memory _sourceChain,
        string memory _targetChain,
        bytes32 _transactionHash,
        uint256 _amount,
        address _tokenAddress,
        address _userAddress
    ) public onlyCrossChainOracle {
        require(!usedProofs[_transactionHash], "Proof already used");
        require(supportedChains[_sourceChain], "Source chain not supported");
        require(supportedChains[_targetChain], "Target chain not supported");
        require(bytes(_did).length > 0, "Invalid DID");
        
        crossChainProofs[_did] = CrossChainProof({
            sourceChain: _sourceChain,
            targetChain: _targetChain,
            transactionHash: _transactionHash,
            amount: _amount,
            tokenAddress: _tokenAddress,
            timestamp: block.timestamp,
            isValid: true,
            userAddress: _userAddress
        });
        
        usedProofs[_transactionHash] = true;
        
        emit CrossChainProofRecorded(
            _did,
            _sourceChain,
            _targetChain,
            _transactionHash,
            _amount,
            _tokenAddress
        );
    }
    
    /**
     * @dev 验证跨链证明
     * @param _did 用户DID
     * @param _sourceChain 源链ID
     * @return 验证是否成功
     */
    function verifyCrossChainProof(
        string memory _did,
        string memory _sourceChain
    ) public view returns (bool) {
        CrossChainProof memory proof = crossChainProofs[_did];
        
        if (!proof.isValid) {
            return false;
        }
        
        // 检查源链是否匹配
        if (keccak256(abi.encodePacked(proof.sourceChain)) != 
            keccak256(abi.encodePacked(_sourceChain))) {
            return false;
        }
        
        // 检查证明是否在有效期内
        if (proof.timestamp + proofValidityPeriod < block.timestamp) {
            return false;
        }
        
        return true;
    }
    
    /**
     * @dev 获取跨链证明详情
     * @param _did 用户DID
     * @return 证明详情
     */
    function getCrossChainProof(string memory _did) public view returns (
        string memory sourceChain,
        string memory targetChain,
        bytes32 transactionHash,
        uint256 amount,
        address tokenAddress,
        uint256 timestamp,
        bool isValid,
        address userAddress
    ) {
        CrossChainProof memory proof = crossChainProofs[_did];
        return (
            proof.sourceChain,
            proof.targetChain,
            proof.transactionHash,
            proof.amount,
            proof.tokenAddress,
            proof.timestamp,
            proof.isValid,
            proof.userAddress
        );
    }
    
    /**
     * @dev 使跨链证明失效
     * @param _did 用户DID
     */
    function invalidateCrossChainProof(string memory _did) public onlyCrossChainOracle {
        crossChainProofs[_did].isValid = false;
    }
    
    /**
     * @dev 设置证明有效期
     * @param _period 有效期（秒）
     */
    function setProofValidityPeriod(uint256 _period) public onlyOwner {
        require(_period > 0, "Invalid period");
        proofValidityPeriod = _period;
    }
    
    /**
     * @dev 检查链是否支持
     * @param _chainId 链ID
     * @return 是否支持
     */
    function isChainSupported(string memory _chainId) public view returns (bool) {
        return supportedChains[_chainId];
    }
    
    /**
     * @dev 获取用户DID（兼容性函数）
     * @param _user 用户地址
     * @return 用户DID
     */
    function getUserDID(address _user) public view returns (string memory) {
        return didOfAddress[_user];
    }
    
    /**
     * @dev 检查用户是否已验证
     * @param _user 用户地址
     * @return 是否已验证
     */
    function isUserVerified(address _user) public view returns (bool) {
        return isVerified[_user];
    }
}
