// SPDX-License-Identifier: MIT
pragma solidity ^0.5.16;
pragma experimental ABIEncoderV2;

/**
 * @title ContractManager
 * @dev 贸易合同管理合约，管理跨境贸易合同
 * @author 大宗货物跨境交易系统
 */
contract ContractManager {
    // 引用DIDVerifier合约
    address public didVerifier;

    // 贸易合同数据结构
    struct TradingContract {
        string name;              // 合同名称
        string id;                // 合同ID
        string version;           // 版本号
        string importer;          // 进口商DID
        string exporter;          // 出口商DID
        string contractContent;   // 合同内容
        uint256 signingDate;      // 签署日期（时间戳）
        bool exists;              // 合同是否存在
    }

    // 合同映射：key为合同ID
    mapping(string => TradingContract) public contracts;

    // 合同ID列表（用于遍历）
    string[] public contractIds;

    // 管理员列表
    address public owner;
    mapping(address => bool) public isAdmin;

    // 事件定义
    event ContractCreated(
        string indexed contractId,
        string name,
        string importer,
        string exporter,
        uint256 signingDate
    );
    event ContractUpdated(string indexed contractId, string name, uint256 timestamp);
    event ContractDeleted(string indexed contractId, uint256 timestamp);
    event AdminAdded(address indexed admin, uint256 timestamp);
    event AdminRemoved(address indexed admin, uint256 timestamp);

    /**
     * @dev 构造函数
     * @param _didVerifier DIDVerifier合约地址
     */
    constructor(address _didVerifier) public {
        require(_didVerifier != address(0), "Invalid DIDVerifier address");
        didVerifier = _didVerifier;
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
     * @dev 设置DIDVerifier合约地址
     * @param _didVerifier 新的DIDVerifier地址
     */
    function setDIDVerifier(address _didVerifier) public onlyOwner {
        require(_didVerifier != address(0), "Invalid address");
        didVerifier = _didVerifier;
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
     * @dev 创建贸易合同
     * @param _id 合同ID
     * @param _name 合同名称
     * @param _importer 进口商DID
     * @param _exporter 出口商DID
     * @param _contractContent 合同内容
     * @param _signingDate 签署日期
     */
    function createContract(
        string memory _id,
        string memory _name,
        string memory _importer,
        string memory _exporter,
        string memory _contractContent,
        uint256 _signingDate
    ) public onlyAdmin {
        require(bytes(_id).length > 0, "Invalid contract ID");
        require(!contracts[_id].exists, "Contract already exists");

        contracts[_id] = TradingContract({
            name: _name,
            id: _id,
            version: "1.0",
            importer: _importer,
            exporter: _exporter,
            contractContent: _contractContent,
            signingDate: _signingDate,
            exists: true
        });

        contractIds.push(_id);

        emit ContractCreated(_id, _name, _importer, _exporter, _signingDate);
    }

    /**
     * @dev 更新贸易合同
     * @param _id 合同ID
     * @param _name 合同名称
     * @param _contractContent 合同内容
     */
    function updateContract(
        string memory _id,
        string memory _name,
        string memory _contractContent
    ) public onlyAdmin {
        require(contracts[_id].exists, "Contract does not exist");

        contracts[_id].name = _name;
        contracts[_id].contractContent = _contractContent;

        emit ContractUpdated(_id, _name, block.timestamp);
    }

    /**
     * @dev 删除贸易合同
     * @param _id 合同ID
     */
    function deleteContract(string memory _id) public onlyAdmin {
        require(contracts[_id].exists, "Contract does not exist");

        delete contracts[_id];

        // 从列表中移除
        for (uint256 i = 0; i < contractIds.length; i++) {
            if (keccak256(abi.encodePacked(contractIds[i])) == keccak256(abi.encodePacked(_id))) {
                contractIds[i] = contractIds[contractIds.length - 1];
                contractIds.length--;
                break;
            }
        }

        emit ContractDeleted(_id, block.timestamp);
    }

    /**
     * @dev 读取贸易合同
     * @param _id 合同ID
     * @return 合同详情
     */
    function getContract(string memory _id) public view onlyVerified returns (
        string memory name,
        string memory id,
        string memory version,
        string memory importer,
        string memory exporter,
        string memory contractContent,
        uint256 signingDate,
        bool exists
    ) {
        TradingContract memory tradingContract = contracts[_id];
        return (
            tradingContract.name,
            tradingContract.id,
            tradingContract.version,
            tradingContract.importer,
            tradingContract.exporter,
            tradingContract.contractContent,
            tradingContract.signingDate,
            tradingContract.exists
        );
    }

    /**
     * @dev 获取合同数量
     * @return 合同总数
     */
    function getContractCount() public view onlyVerified returns (uint256) {
        return contractIds.length;
    }

    /**
     * @dev 获取所有合同ID列表
     * @return 合同ID数组
     */
    function getAllContractIds() public view onlyVerified returns (string[] memory) {
        return contractIds;
    }

    /**
     * @dev 根据进口商DID获取相关合同ID列表
     * @param _importerDID 进口商DID
     * @return 合同ID数组
     */
    function getContractsByImporter(string memory _importerDID) public view onlyVerified returns (string[] memory) {
        // 先计算匹配数量
        uint256 count = 0;
        for (uint256 i = 0; i < contractIds.length; i++) {
            if (keccak256(abi.encodePacked(contracts[contractIds[i]].importer)) == keccak256(abi.encodePacked(_importerDID))) {
                count++;
            }
        }

        // 创建结果数组
        string[] memory result = new string[](count);
        uint256 index = 0;
        for (uint256 i = 0; i < contractIds.length; i++) {
            if (keccak256(abi.encodePacked(contracts[contractIds[i]].importer)) == keccak256(abi.encodePacked(_importerDID))) {
                result[index] = contractIds[i];
                index++;
            }
        }

        return result;
    }

    /**
     * @dev 根据出口商DID获取相关合同ID列表
     * @param _exporterDID 出口商DID
     * @return 合同ID数组
     */
    function getContractsByExporter(string memory _exporterDID) public view onlyVerified returns (string[] memory) {
        // 先计算匹配数量
        uint256 count = 0;
        for (uint256 i = 0; i < contractIds.length; i++) {
            if (keccak256(abi.encodePacked(contracts[contractIds[i]].exporter)) == keccak256(abi.encodePacked(_exporterDID))) {
                count++;
            }
        }

        // 创建结果数组
        string[] memory result = new string[](count);
        uint256 index = 0;
        for (uint256 i = 0; i < contractIds.length; i++) {
            if (keccak256(abi.encodePacked(contracts[contractIds[i]].exporter)) == keccak256(abi.encodePacked(_exporterDID))) {
                result[index] = contractIds[i];
                index++;
            }
        }

        return result;
    }

    /**
     * @dev 检查合同是否存在
     * @param _id 合同ID
     * @return 是否存在
     */
    function contractExists(string memory _id) public view onlyVerified returns (bool) {
        return contracts[_id].exists;
    }
}
