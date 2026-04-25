// SPDX-License-Identifier: MIT
pragma solidity ^0.5.16;
pragma experimental ABIEncoderV2;

/**
 * @title DIDVerifier
 * @dev DID身份验证器，管理用户账户与DID的映射，确认地址是否通过身份验证
 * @author 大宗货物跨境交易系统
 */
contract DIDVerifier {
    // 核心映射：地址与DID的双向映射
    mapping(address => bool) public isVerified;           // 地址是否已验证
    mapping(address => string) public didOfAddress;       // 地址对应的DID
    mapping(string => address) public addressOfDid;       // DID对应的地址

    // 管理员列表
    address public owner;
    mapping(address => bool) public isAdmin;

    // 事件定义
    event IdentityVerified(address indexed user, string did, uint256 timestamp);
    event IdentityRevoked(address indexed user, string did, uint256 timestamp);
    event AdminAdded(address indexed admin, uint256 timestamp);
    event AdminRemoved(address indexed admin, uint256 timestamp);

    /**
     * @dev 构造函数，部署者为owner
     */
    constructor() public {
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
     * @dev 验证用户身份，建立地址与DID的映射
     * @param _user 用户地址
     * @param _did 用户DID
     */
    function verifyIdentity(address _user, string memory _did) public onlyAdmin {
        require(_user != address(0), "Invalid address");
        require(bytes(_did).length > 0, "Invalid DID");

        isVerified[_user] = true;
        didOfAddress[_user] = _did;
        addressOfDid[_did] = _user;

        emit IdentityVerified(_user, _did, block.timestamp);
    }

    /**
     * @dev 批量验证用户身份
     * @param _users 用户地址数组
     * @param _dids 用户DID数组
     */
    function verifyIdentityBatch(address[] memory _users, string[] memory _dids) public onlyAdmin {
        require(_users.length == _dids.length, "Length mismatch");
        for (uint256 i = 0; i < _users.length; i++) {
            verifyIdentity(_users[i], _dids[i]);
        }
    }

    /**
     * @dev 撤销用户身份验证
     * @param _user 用户地址
     */
    function revokeVerification(address _user) public onlyAdmin {
        require(isVerified[_user], "User not verified");

        string memory did = didOfAddress[_user];
        isVerified[_user] = false;
        delete didOfAddress[_user];
        delete addressOfDid[did];

        emit IdentityRevoked(_user, did, block.timestamp);
    }

    /**
     * @dev 获取用户DID
     * @param _user 用户地址
     * @return 用户DID
     */
    function getUserDID(address _user) public view returns (string memory) {
        return didOfAddress[_user];
    }

    /**
     * @dev 获取DID对应的地址
     * @param _did 用户DID
     * @return 用户地址
     */
    function getAddressByDID(string memory _did) public view returns (address) {
        return addressOfDid[_did];
    }

    /**
     * @dev 检查用户是否已验证
     * @param _user 用户地址
     * @return 是否已验证
     */
    function checkUserVerified(address _user) public view returns (bool) {
        return isVerified[_user];
    }

    /**
     * @dev 计算DID的哈希值（用于优化存储和查询）
     * @param _did DID字符串
     * @return DID的哈希值
     */
    function getDIDHash(string memory _did) public pure returns (bytes32) {
        return keccak256(abi.encodePacked(_did));
    }

    /**
     * @dev 验证DID与地址是否匹配
     * @param _did 用户DID
     * @param _address 用户地址
     * @return 是否匹配
     */
    function verifyDIDAddress(string memory _did, address _address) public view returns (bool) {
        string memory addressDID = didOfAddress[_address];
        return keccak256(abi.encodePacked(addressDID)) == keccak256(abi.encodePacked(_did));
    }

    /**
     * @dev 检查调用者是否为已验证的用户
     * @return 是否已验证
     */
    function amIVerified() public view returns (bool) {
        return isVerified[msg.sender];
    }
}
