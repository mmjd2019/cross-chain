// SPDX-License-Identifier: MIT
pragma solidity ^0.5.16;

contract SimpleTest {
    string public message;
    uint256 public value;
    
    constructor() public {
        message = "Hello Cross-Chain!";
        value = 42;
    }
    
    function setMessage(string memory _message) public {
        message = _message;
    }
    
    function setValue(uint256 _value) public {
        value = _value;
    }
    
    function getInfo() public view returns (string memory, uint256) {
        return (message, value);
    }
}
