// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

/// @title TxOriginGateway — deliberately vulnerable (tx.origin auth)
/// @dev Educational example for slither-chat. DO NOT use in production.
///      Bug: admin functions are gated by `tx.origin == owner`. A phishing
///      contract that makes the victim call it can then call adminAction()
///      *as if* the victim were the caller — tx.origin is the original EOA,
///      not the direct caller. Always use msg.sender for authorization.
contract TxOriginGateway {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    /// @dev VULNERABLE: tx.origin instead of msg.sender.
    function setOwner(address newOwner) external {
        require(tx.origin == owner, "not owner");
        owner = newOwner;
    }

    function withdrawAll() external {
        require(tx.origin == owner, "not owner");
        (bool ok, ) = owner.call{value: address(this).balance}("");
        require(ok, "withdraw failed");
    }

    /// @dev Transfers a managed ERC20 out — full admin power behind tx.origin.
    function sweepToken(address token, address to, uint256 amount) external {
        require(tx.origin == owner, "not owner");
        (bool ok, bytes memory data) = token.call(
            abi.encodeWithSignature("transfer(address,uint256)", to, amount)
        );
        require(ok && (data.length == 0 || abi.decode(data, (bool))), "sweep failed");
    }
}