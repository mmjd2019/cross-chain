// SPDX-License-Identifier: MIT
pragma solidity ^0.5.16;

contract DIDVerifier {
    mapping(address => bool) public isVerified;
    mapping(address => string) public didOfAddress;
    mapping(string => address) public addressOfDid;
    
    address public owner;
    address public oracle;
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function");
        _;
    }
    
    modifier onlyOracle() {
        require(msg.sender == oracle, "Only oracle can call this function");
        _;
    }
    
    constructor() public {
        owner = msg.sender;
    }
    
    function setOracle(address _oracle) public onlyOwner {
        oracle = _oracle;
    }
    
    function verifyIdentity(address _user, string memory _did) public onlyOracle {
        isVerified[_user] = true;
        didOfAddress[_user] = _did;
        addressOfDid[_did] = _user;
        
        emit IdentityVerified(_user, _did, block.timestamp);
    }
    
    function revokeVerification(address _user) public onlyOracle {
        string memory did = didOfAddress[_user];
        isVerified[_user] = false;
        delete didOfAddress[_user];
        delete addressOfDid[did];
        
        emit IdentityRevoked(_user, did, block.timestamp);
    }
    
    event IdentityVerified(address indexed user, string did, uint256 timestamp);
    event IdentityRevoked(address indexed user, string did, uint256 timestamp);
}
