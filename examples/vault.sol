// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

/// @title ReentrantVault — deliberately vulnerable (reentrancy)
/// @dev Educational example for slither-chat. DO NOT use in production.
///      Bug: state is updated AFTER the external call (checks-effects-interactions
///      violated), so an attacker contract can re-enter withdraw() before the
///      balance is zeroed and drain the vault.
contract ReentrantVault {
    mapping(address => uint256) public balances;
    uint256 public totalDeposited;

    event Deposit(address indexed who, uint256 amount);
    event Withdraw(address indexed who, uint256 amount);

    receive() external payable {
        deposit();
    }

    function deposit() public payable {
        require(msg.value > 0, "deposit must be > 0");
        balances[msg.sender] += msg.value;
        totalDeposited += msg.value;
        emit Deposit(msg.sender, msg.value);
    }

    /// @notice Withdraw your balance.
    /// @dev VULNERABLE: the external `call` happens BEFORE `balances[msg.sender] = 0`.
    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "insufficient balance");
        uint256 balanceBefore = balances[msg.sender];

        // External call to an attacker-controlled receiver...
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "transfer failed");

        // ...and only THEN the state is updated.
        balances[msg.sender] = balanceBefore - amount;
    }

    /// @notice Batch withdraw for several users (loop with external call).
    function withdrawMany(address[] calldata users) external {
        for (uint256 i = 0; i < users.length; i++) {
            uint256 amount = balances[users[i]];
            if (amount == 0) continue;
            (bool ok, ) = users[i].call{value: amount}("");
            if (ok) {
                balances[users[i]] = 0;
            }
        }
    }
}