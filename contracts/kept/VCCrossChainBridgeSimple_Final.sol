// SPDX-License-Identifier: MIT
pragma solidity ^0.5.16;
pragma experimental ABIEncoderV2;

/**
 * @title VCCrossChainBridgeSimple
 * @dev 简化版VC跨链桥，单次调用完成发送/接收
 * @notice 包含holderEndpoint，共7个核心字段
 */
contract VCCrossChainBridgeSimple {
    DIDVerifier public didVerifier;

    enum TransferStatus { InProgress, Completed }

    /**
     * @dev 简化的VC元数据（7个核心字段）
     */
    struct VCMetadataSimple {
        bytes32 vcHash;              // ① VC的Hash（主键）
        string vcName;               // ② VC名称
        string holderEndpoint;       // ③ 持有者ACA-Py endpoint（必需）
        string holderDID;            // ④ 持有者DID（权限验证）
        address vcManagerAddress;    // ⑤ VC管理合约
        uint256 expiryTime;          // ⑥ 过期时间
        bool exists;
    }

    struct SendRecord {
        VCMetadataSimple metadata;
        string targetChain;          // ⑦ 目标链
        TransferStatus status;
        uint256 timestamp;
        bool exists;
    }

    struct ReceiveRecord {
        VCMetadataSimple metadata;
        string sourceChain;          // ⑦ 源链
        uint256 timestamp;
        bool exists;
    }

    // 存储变量
    mapping(bytes32 => SendRecord) public sendList;
    mapping(bytes32 => ReceiveRecord) public receiveList;
    bytes32[] public sendListIndexes;
    bytes32[] public receiveListIndexes;

    // 权限控制
    address public owner;
    mapping(address => bool) public adminList;
    mapping(string => bool) public oracleDIDList;
    mapping(address => bool) public vcManagerList;

    // 事件
    event VCSent(bytes32 indexed vcHash, string targetChain, address indexed sender, string holderEndpoint);
    event VCReceived(bytes32 indexed vcHash, string sourceChain, string holderEndpoint);

    modifier onlyOwner() { require(msg.sender == owner, "Only owner"); _; }
    modifier onlyAdmin() { require(adminList[msg.sender], "Only admin"); _; }
    modifier onlyAllowedVCManager() { require(vcManagerList[msg.sender], "Only allowed VC manager"); _; }
    modifier onlyAllowedOracleDID() {
        string memory callerDID = didVerifier.getUserDID(msg.sender);
        require(oracleDIDList[callerDID], "Only allowed Oracle DID");
        _;
    }

    constructor(address _didVerifier) public {
        didVerifier = DIDVerifier(_didVerifier);
        owner = msg.sender;
        adminList[owner] = true;
    }

    // ==================== 单次调用：发送VC ====================
    /**
     * @dev VC管理合约调用：单次交易完成VC发送
     * @param _vcHash VC的Hash
     * @param _vcName VC名称
     * @param _holderEndpoint 持有者ACA-Py endpoint（必需）
     * @param _holderDID 持有者DID
     * @param _vcManagerAddress VC管理合约地址
     * @param _expiryTime VC过期时间
     * @param _targetChain 目标区块链名称
     */
    function sendToCrossChain(
        bytes32 _vcHash,
        string calldata _vcName,
        string calldata _holderEndpoint,
        string calldata _holderDID,
        address _vcManagerAddress,
        uint256 _expiryTime,
        string calldata _targetChain
    ) external onlyAllowedVCManager {
        require(_vcHash != bytes32(0), "Invalid VC hash");
        require(!sendList[_vcHash].exists, "VC already exists");

        SendRecord storage record = sendList[_vcHash];
        record.metadata.vcHash = _vcHash;
        record.metadata.vcName = _vcName;
        record.metadata.holderEndpoint = _holderEndpoint;
        record.metadata.holderDID = _holderDID;
        record.metadata.vcManagerAddress = _vcManagerAddress;
        record.metadata.expiryTime = _expiryTime;
        record.metadata.exists = true;
        record.targetChain = _targetChain;
        record.status = TransferStatus.InProgress;
        record.timestamp = block.timestamp;
        record.exists = true;

        sendListIndexes.push(_vcHash);
        emit VCSent(_vcHash, _targetChain, msg.sender, _holderEndpoint);
    }

    // ==================== 单次调用：接收VC ====================
    /**
     * @dev Oracle调用：单次交易完成VC接收
     */
    function receiveFromCrossChain(
        bytes32 _vcHash,
        string calldata _vcName,
        string calldata _holderEndpoint,
        string calldata _holderDID,
        address _vcManagerAddress,
        uint256 _expiryTime,
        string calldata _sourceChain
    ) external onlyAllowedOracleDID {
        require(_vcHash != bytes32(0), "Invalid VC hash");
        require(!receiveList[_vcHash].exists, "VC already exists");

        ReceiveRecord storage record = receiveList[_vcHash];
        record.metadata.vcHash = _vcHash;
        record.metadata.vcName = _vcName;
        record.metadata.holderEndpoint = _holderEndpoint;
        record.metadata.holderDID = _holderDID;
        record.metadata.vcManagerAddress = _vcManagerAddress;
        record.metadata.expiryTime = _expiryTime;
        record.metadata.exists = true;
        record.sourceChain = _sourceChain;
        record.timestamp = block.timestamp;
        record.exists = true;

        receiveListIndexes.push(_vcHash);
        emit VCReceived(_vcHash, _sourceChain, _holderEndpoint);
    }

    // ==================== 状态管理 ====================
    function updateSendStatus(bytes32 _vcHash, TransferStatus _status) external onlyAllowedOracleDID {
        require(sendList[_vcHash].exists, "VC not found");
        sendList[_vcHash].status = _status;
    }

    // ==================== 查询函数 ====================
    function getSendRecord(bytes32 _vcHash) external view returns (
        string memory vcName,
        string memory holderEndpoint,
        string memory holderDID,
        string memory targetChain,
        TransferStatus status,
        uint256 timestamp
    ) {
        require(sendList[_vcHash].exists, "VC not found");
        SendRecord memory record = sendList[_vcHash];
        return (
            record.metadata.vcName,
            record.metadata.holderEndpoint,
            record.metadata.holderDID,
            record.targetChain,
            record.status,
            record.timestamp
        );
    }

    function getReceiveRecord(bytes32 _vcHash) external view returns (
        string memory vcName,
        string memory holderEndpoint,
        string memory holderDID,
        string memory sourceChain,
        uint256 timestamp
    ) {
        require(receiveList[_vcHash].exists, "VC not found");
        ReceiveRecord memory record = receiveList[_vcHash];
        return (
            record.metadata.vcName,
            record.metadata.holderEndpoint,
            record.metadata.holderDID,
            record.sourceChain,
            record.timestamp
        );
    }

    function getSendListIndexes() external view returns (bytes32[] memory) {
        return sendListIndexes;
    }

    function getReceiveListIndexes() external view returns (bytes32[] memory) {
        return receiveListIndexes;
    }

    function getSendListCount() external view returns (uint256) {
        return sendListIndexes.length;
    }

    function getReceiveListCount() external view returns (uint256) {
        return receiveListIndexes.length;
    }

    // ==================== 权限管理 ====================
    function addAdmin(address _admin) external onlyOwner {
        adminList[_admin] = true;
    }

    function removeAdmin(address _admin) external onlyOwner {
        require(_admin != owner, "Cannot remove owner");
        adminList[_admin] = false;
    }

    function addOracleDID(string calldata _did) external onlyAdmin {
        oracleDIDList[_did] = true;
    }

    function removeOracleDID(string calldata _did) external onlyAdmin {
        oracleDIDList[_did] = false;
    }

    function addVCManager(address _vcManager) external onlyAdmin {
        vcManagerList[_vcManager] = true;
    }

    function removeVCManager(address _vcManager) external onlyAdmin {
        vcManagerList[_vcManager] = false;
    }

    function transferOwnership(address _newOwner) external onlyOwner {
        owner = _newOwner;
        adminList[_newOwner] = true;
    }

    function setDIDVerifier(address _didVerifier) external onlyOwner {
        didVerifier = DIDVerifier(_didVerifier);
    }

    // ==================== 删除操作 ====================
    function deleteSendRecord(bytes32 _vcHash) external onlyAdmin {
        require(sendList[_vcHash].exists, "VC not found");
        delete sendList[_vcHash];
        // 从索引中移除
        for (uint256 i = 0; i < sendListIndexes.length; i++) {
            if (sendListIndexes[i] == _vcHash) {
                sendListIndexes[i] = sendListIndexes[sendListIndexes.length - 1];
                sendListIndexes.length--;
                break;
            }
        }
    }

    function deleteReceiveRecord(bytes32 _vcHash) external onlyAdmin {
        require(receiveList[_vcHash].exists, "VC not found");
        delete receiveList[_vcHash];
        // 从索引中移除
        for (uint256 i = 0; i < receiveListIndexes.length; i++) {
            if (receiveListIndexes[i] == _vcHash) {
                receiveListIndexes[i] = receiveListIndexes[receiveListIndexes.length - 1];
                receiveListIndexes.length--;
                break;
            }
        }
    }
}

interface DIDVerifier {
    function getUserDID(address _user) external view returns (string memory);
    function checkUserVerified(address _user) external view returns (bool);
}
