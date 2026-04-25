// SPDX-License-Identifier: MIT
pragma solidity ^0.5.16;
pragma experimental ABIEncoderV2;

/**
 * @title IVCCrossChainBridgeSimple
 * @dev 新的简化跨链桥接口
 */
interface IVCCrossChainBridgeSimple {
    function sendToCrossChain(
        bytes32 _vcHash,
        string calldata _vcName,
        string calldata _holderEndpoint,
        string calldata _holderDID,
        address _vcManagerAddress,
        uint256 _expiryTime,
        string calldata _targetChain
    ) external;
}

/**
 * @title CertificateOfOriginVCManager
 * @dev 原产地VC管理合约，管理原产地证明的可验证凭证元数据
 * @author 大宗货物跨境交易系统
 */
contract CertificateOfOriginVCManager {
    // 引用DIDVerifier合约
    address public didVerifier;

    // VC元数据结构（标准格式）
    struct VCMetadata {
        bytes32 vcHash;              // VC的Hash
        string vcName;               // VC名称
        string vcDescription;        // VC用途描述
        string issuerEndpoint;       // 发行者ACAPY的endpoint
        string issuerDID;            // 发行者DID
        string holderEndpoint;       // 持有者ACAPY的endpoint
        string holderDID;            // 持有者DID
        string blockchainEndpoint;   // VC存储区块链的endpoint
        address vcManagerAddress;    // 当前VC管理智能合约地址
        string blockchainType;       // 存储区块链类型
        uint256 expiryTime;          // VC失效时间（Unix时间戳）
        bool exists;                 // 是否存在
    }

    // VC元数据映射：key为VC的hash
    mapping(bytes32 => VCMetadata) public vcMetadataList;

    // VC Hash列表（用于遍历）
    bytes32[] public vcHashes;

    // 跨链桥合约地址
    address public vcCrossChainBridge;

    // 管理员列表
    address public owner;
    mapping(address => bool) public isAdmin;

    // Oracle服务访问许可DID列表
    mapping(string => bool) public oracleAllowedDIDs;

    // 跨链用户许可DID列表
    mapping(string => bool) public crossChainAllowedDIDs;

    // 事件定义
    event VCMetadataAdded(bytes32 indexed vcHash, string vcName, string holderDID, uint256 timestamp);
    event VCMetadataUpdated(bytes32 indexed vcHash, string vcName, uint256 timestamp);
    event VCMetadataDeleted(bytes32 indexed vcHash, uint256 timestamp);
    event OracleDIDAdded(string did, uint256 timestamp);
    event OracleDIDRemoved(string did, uint256 timestamp);
    event CrossChainDIDAdded(string did, uint256 timestamp);
    event CrossChainDIDRemoved(string did, uint256 timestamp);
    event CrossChainTransferInitiated(bytes32 indexed vcHash, string targetChain, uint256 timestamp);
    event AdminAdded(address indexed admin, uint256 timestamp);
    event AdminRemoved(address indexed admin, uint256 timestamp);

    /**
     * @dev 构造函数
     * @param _didVerifier DIDVerifier合约地址
     * @param _vcCrossChainBridge VC跨链桥合约地址
     */
    constructor(address _didVerifier, address _vcCrossChainBridge) public {
        require(_didVerifier != address(0), "Invalid DIDVerifier address");
        require(_vcCrossChainBridge != address(0), "Invalid Bridge address");

        didVerifier = _didVerifier;
        vcCrossChainBridge = _vcCrossChainBridge;
        owner = msg.sender;
        isAdmin[owner] = true;
        emit AdminAdded(owner, block.timestamp);
    }

    /**
     * @dev 修饰符：只有owner可以调用
     */
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    /**
     * @dev 修饰符：只有管理员可以调用
     */
    modifier onlyAdmin() {
        require(isAdmin[msg.sender], "Only admin");
        _;
    }

    /**
     * @dev 修饰符：只有验证过的用户可以调用
     */
    modifier onlyVerified() {
        require(_isVerified(msg.sender), "User not verified");
        _;
    }

    /**
     * @dev 修饰符：只有Oracle服务可以调用
     */
    modifier onlyOracle() {
        require(_isOracleService(msg.sender), "Only oracle service");
        _;
    }

    /**
     * @dev 修饰符：只有Oracle或跨链授权用户可以调用
     */
    modifier onlyOracleOrCrossChainUser() {
        require(_isOracleService(msg.sender) || _isCrossChainUser(msg.sender), "Not authorized");
        _;
    }

    /**
     * @dev 内部函数：检查地址是否已验证
     */
    function _isVerified(address _user) internal view returns (bool) {
        if (_user == owner || isAdmin[_user]) {
            return true;
        }
        (bool success, bytes memory data) = didVerifier.staticcall(
            abi.encodeWithSignature("checkUserVerified(address)", _user)
        );
        return success && abi.decode(data, (bool));
    }

    /**
     * @dev 内部函数：检查是否为Oracle服务
     */
    function _isOracleService(address _caller) internal view returns (bool) {
        // 获取调用者的DID
        (bool success, bytes memory data) = didVerifier.staticcall(
            abi.encodeWithSignature("getUserDID(address)", _caller)
        );
        if (!success) {
            return false;
        }
        string memory callerDID = abi.decode(data, (string));
        return oracleAllowedDIDs[callerDID];
    }

    /**
     * @dev 内部函数：检查是否为跨链授权用户
     */
    function _isCrossChainUser(address _caller) internal view returns (bool) {
        // 获取调用者的DID
        (bool success, bytes memory data) = didVerifier.staticcall(
            abi.encodeWithSignature("getUserDID(address)", _caller)
        );
        if (!success) {
            return false;
        }
        string memory callerDID = abi.decode(data, (string));
        return crossChainAllowedDIDs[callerDID];
    }

    /**
     * @dev 设置DIDVerifier合约地址
     * @param _didVerifier 新的DIDVerifier地址
     */
    function setDIDVerifier(address _didVerifier) public onlyOwner {
        require(_didVerifier != address(0), "Invalid address");
        didVerifier = _didVerifier;
    }

    /**
     * @dev 设置跨链桥合约地址
     * @param _vcCrossChainBridge 新的跨链桥地址
     */
    function setVCCrossChainBridge(address _vcCrossChainBridge) public onlyOwner {
        require(_vcCrossChainBridge != address(0), "Invalid address");
        vcCrossChainBridge = _vcCrossChainBridge;
    }

    /**
     * @dev 添加管理员
     * @param _admin 管理员地址
     */
    function addAdmin(address _admin) public onlyOwner {
        require(_admin != address(0), "Invalid address");
        require(!isAdmin[_admin], "Already admin");
        isAdmin[_admin] = true;
        emit AdminAdded(_admin, block.timestamp);
    }

    /**
     * @dev 移除管理员
     * @param _admin 管理员地址
     */
    function removeAdmin(address _admin) public onlyOwner {
        require(_admin != owner, "Cannot remove owner");
        require(isAdmin[_admin], "Not admin");
        isAdmin[_admin] = false;
        emit AdminRemoved(_admin, block.timestamp);
    }

    /**
     * @dev 添加Oracle服务许可DID
     * @param _oracleDID Oracle服务的DID
     */
    function addOracleDID(string memory _oracleDID) public onlyAdmin {
        require(bytes(_oracleDID).length > 0, "Invalid DID");
        require(!oracleAllowedDIDs[_oracleDID], "Already allowed");
        oracleAllowedDIDs[_oracleDID] = true;
        emit OracleDIDAdded(_oracleDID, block.timestamp);
    }

    /**
     * @dev 移除Oracle服务许可DID
     * @param _oracleDID Oracle服务的DID
     */
    function removeOracleDID(string memory _oracleDID) public onlyAdmin {
        require(oracleAllowedDIDs[_oracleDID], "Not allowed");
        oracleAllowedDIDs[_oracleDID] = false;
        emit OracleDIDRemoved(_oracleDID, block.timestamp);
    }

    /**
     * @dev 添加跨链用户许可DID
     * @param _userDID 用户DID
     */
    function addCrossChainDID(string memory _userDID) public onlyAdmin {
        require(bytes(_userDID).length > 0, "Invalid DID");
        require(!crossChainAllowedDIDs[_userDID], "Already allowed");
        crossChainAllowedDIDs[_userDID] = true;
        emit CrossChainDIDAdded(_userDID, block.timestamp);
    }

    /**
     * @dev 移除跨链用户许可DID
     * @param _userDID 用户DID
     */
    function removeCrossChainDID(string memory _userDID) public onlyAdmin {
        require(crossChainAllowedDIDs[_userDID], "Not allowed");
        crossChainAllowedDIDs[_userDID] = false;
        emit CrossChainDIDRemoved(_userDID, block.timestamp);
    }

    /**
     * @dev 添加VC元数据（Oracle或管理员）
     * @param _vcHash VC的Hash
     * @param _vcName VC名称
     * @param _vcDescription VC用途描述
     * @param _issuerEndpoint 发行者ACAPY的endpoint
     * @param _issuerDID 发行者DID
     * @param _holderEndpoint 持有者ACAPY的endpoint
     * @param _holderDID 持有者DID
     * @param _blockchainEndpoint VC存储区块链endpoint
     * @param _blockchainType 存储区块链类型
     * @param _expiryTime VC失效时间
     */
    function addVCMetadata(
        bytes32 _vcHash,
        string memory _vcName,
        string memory _vcDescription,
        string memory _issuerEndpoint,
        string memory _issuerDID,
        string memory _holderEndpoint,
        string memory _holderDID,
        string memory _blockchainEndpoint,
        string memory _blockchainType,
        uint256 _expiryTime
    ) public onlyOracleOrCrossChainUser {
        require(_vcHash != bytes32(0), "Invalid VC hash");
        require(!vcMetadataList[_vcHash].exists, "VC already exists");

        vcMetadataList[_vcHash] = VCMetadata({
            vcHash: _vcHash,
            vcName: _vcName,
            vcDescription: _vcDescription,
            issuerEndpoint: _issuerEndpoint,
            issuerDID: _issuerDID,
            holderEndpoint: _holderEndpoint,
            holderDID: _holderDID,
            blockchainEndpoint: _blockchainEndpoint,
            vcManagerAddress: address(this),
            blockchainType: _blockchainType,
            expiryTime: _expiryTime,
            exists: true
        });

        vcHashes.push(_vcHash);

        // 自动将持有者DID添加到跨链许可列表
        if (!crossChainAllowedDIDs[_holderDID]) {
            crossChainAllowedDIDs[_holderDID] = true;
            emit CrossChainDIDAdded(_holderDID, block.timestamp);
        }

        emit VCMetadataAdded(_vcHash, _vcName, _holderDID, block.timestamp);
    }

    /**
     * @dev 更新VC元数据（Oracle或管理员）
     * @param _vcHash VC的Hash
     * @param _vcName VC名称
     * @param _vcDescription VC用途描述
     * @param _expiryTime VC失效时间
     */
    function updateVCMetadata(
        bytes32 _vcHash,
        string memory _vcName,
        string memory _vcDescription,
        uint256 _expiryTime
    ) public onlyOracleOrCrossChainUser {
        require(vcMetadataList[_vcHash].exists, "VC does not exist");

        vcMetadataList[_vcHash].vcName = _vcName;
        vcMetadataList[_vcHash].vcDescription = _vcDescription;
        vcMetadataList[_vcHash].expiryTime = _expiryTime;

        emit VCMetadataUpdated(_vcHash, _vcName, block.timestamp);
    }

    /**
     * @dev 删除VC元数据（只有管理员）
     * @param _vcHash VC的Hash
     */
    function deleteVCMetadata(bytes32 _vcHash) public onlyAdmin {
        require(vcMetadataList[_vcHash].exists, "VC does not exist");

        delete vcMetadataList[_vcHash];

        // 从列表中移除
        for (uint256 i = 0; i < vcHashes.length; i++) {
            if (vcHashes[i] == _vcHash) {
                vcHashes[i] = vcHashes[vcHashes.length - 1];
                vcHashes.length--;
                break;
            }
        }

        emit VCMetadataDeleted(_vcHash, block.timestamp);
    }

    /**
     * @dev 读取VC元数据
     * @param _vcHash VC的Hash
     * @return VC元数据详情
     */
    function getVCMetadata(bytes32 _vcHash) public view onlyVerified returns (
        bytes32 vcHash,
        string memory vcName,
        string memory vcDescription,
        string memory issuerEndpoint,
        string memory issuerDID,
        string memory holderEndpoint,
        string memory holderDID,
        string memory blockchainEndpoint,
        address vcManagerAddress,
        string memory blockchainType,
        uint256 expiryTime,
        bool exists
    ) {
        VCMetadata memory metadata = vcMetadataList[_vcHash];
        return (
            metadata.vcHash,
            metadata.vcName,
            metadata.vcDescription,
            metadata.issuerEndpoint,
            metadata.issuerDID,
            metadata.holderEndpoint,
            metadata.holderDID,
            metadata.blockchainEndpoint,
            metadata.vcManagerAddress,
            metadata.blockchainType,
            metadata.expiryTime,
            metadata.exists
        );
    }

    /**
     * @dev 获取VC数量
     * @return VC总数
     */
    function getVCCount() public view onlyVerified returns (uint256) {
        return vcHashes.length;
    }

    /**
     * @dev 获取所有VC Hash列表
     * @return VC Hash数组
     */
    function getAllVCHashes() public view onlyVerified returns (bytes32[] memory) {
        return vcHashes;
    }

    /**
     * @dev 根据持有者DID获取相关VC Hash列表
     * @param _holderDID 持有者DID
     * @return VC Hash数组
     */
    function getVCHashesByHolder(string memory _holderDID) public view onlyVerified returns (bytes32[] memory) {
        // 先计算匹配数量
        uint256 count = 0;
        for (uint256 i = 0; i < vcHashes.length; i++) {
            if (keccak256(abi.encodePacked(vcMetadataList[vcHashes[i]].holderDID)) == keccak256(abi.encodePacked(_holderDID))) {
                count++;
            }
        }

        // 创建结果数组
        bytes32[] memory result = new bytes32[](count);
        uint256 index = 0;
        for (uint256 i = 0; i < vcHashes.length; i++) {
            if (keccak256(abi.encodePacked(vcMetadataList[vcHashes[i]].holderDID)) == keccak256(abi.encodePacked(_holderDID))) {
                result[index] = vcHashes[i];
                index++;
            }
        }

        return result;
    }

    /**
     * @dev 发起跨链传输（调用新的简化跨链桥合约）
     * @param _vcHash VC的Hash
     * @param _targetChain 目标链名称
     */
    function initiateCrossChainTransfer(bytes32 _vcHash, string memory _targetChain) public onlyOracleOrCrossChainUser {
        require(vcMetadataList[_vcHash].exists, "VC does not exist");
        require(_isHolder(msg.sender, _vcHash), "Not holder of this VC");

        // 获取VC元数据
        VCMetadata memory metadata = vcMetadataList[_vcHash];

        // 调用新的简化跨链桥接口（单次调用，只传递7个核心字段）
        IVCCrossChainBridgeSimple bridge = IVCCrossChainBridgeSimple(vcCrossChainBridge);
        bridge.sendToCrossChain(
            _vcHash,                      // ① VC的Hash
            metadata.vcName,              // ② VC名称
            metadata.holderEndpoint,      // ③ 持有者endpoint（必需）
            metadata.holderDID,           // ④ 持有者DID
            address(this),                // ⑤ VC管理合约地址
            metadata.expiryTime,          // ⑥ 过期时间
            _targetChain                  // ⑦ 目标链
        );

        emit CrossChainTransferInitiated(_vcHash, _targetChain, block.timestamp);
    }

    /**
     * @dev 内部函数：检查调用者是否为VC的持有者
     * @param _caller 调用者地址
     * @param _vcHash VC的Hash
     * @return 是否为持有者
     */
    function _isHolder(address _caller, bytes32 _vcHash) internal view returns (bool) {
        // 管理员和Oracle可以操作所有VC
        if (isAdmin[_caller] || _isOracleService(_caller)) {
            return true;
        }

        // 获取调用者的DID
        (bool success, bytes memory data) = didVerifier.staticcall(
            abi.encodeWithSignature("getUserDID(address)", _caller)
        );
        if (!success) {
            return false;
        }
        string memory callerDID = abi.decode(data, (string));

        // 检查是否为持有者
        return keccak256(abi.encodePacked(vcMetadataList[_vcHash].holderDID)) == keccak256(abi.encodePacked(callerDID));
    }

    /**
     * @dev 检查VC是否有效（未过期且存在）
     * @param _vcHash VC的Hash
     * @return 是否有效
     */
    function isVCValid(bytes32 _vcHash) public view onlyVerified returns (bool) {
        return vcMetadataList[_vcHash].exists && vcMetadataList[_vcHash].expiryTime >= block.timestamp;
    }

    /**
     * @dev 检查VC是否存在
     * @param _vcHash VC的Hash
     * @return 是否存在
     */
    function vcExists(bytes32 _vcHash) public view onlyVerified returns (bool) {
        return vcMetadataList[_vcHash].exists;
    }
}
