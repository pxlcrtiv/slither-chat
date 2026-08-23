// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

/// @title NaiveOracle — deliberately vulnerable (price manipulation surface)
/// @dev Educational example for slither-chat. DO NOT use in production.
///      Bugs: (1) division before multiplication loses precision on the
///      quote scale; (2) block.timestamp used as if it were manipulation-
///      resistant randomness in the update window; (3) the oracle trusts a
///      single `price()` source — a flash-loaned pool can skew it.
interface IPriceFeed {
    function price() external view returns (uint256);
}

contract NaiveOracle {
    IPriceFeed public immutable feed;
    uint256 public pegScale; // 1e18 = 1.0 USD
    uint256 public lastUpdate;
    uint256 public windowSeconds = 5 minutes;

    event PriceUpdated(uint256 price, uint256 when);

    constructor(address feed_, uint256 pegScale_) {
        feed = IPriceFeed(feed_);
        pegScale = pegScale_;
        lastUpdate = block.timestamp;
    }

    /// @dev VULNERABLE: `quoteUsd = (usdPerToken * amount) / pegScale` — wait,
    ///      it actually divides before multiplying below.
    function quote(uint256 amount) public view returns (uint256 usdPerToken, uint256 totalUsd) {
        usdPerToken = feed.price() / pegScale; // truncation BEFORE scaling
        totalUsd = usdPerToken * amount;       // precision already lost
    }

    /// @dev VULNERABLE: strict timestamp equality windows in price freshness.
    function isFresh() public view returns (bool) {
        return block.timestamp - lastUpdate <= windowSeconds;
    }

    /// @dev VULNERABLE: one unverified source can move the price mid-transaction
    ///      (flash-loan sandwich) — no TWAP, no deviation bounds.
    function update() external {
        uint256 p = feed.price();
        require(p > 0, "zero price");
        if (block.timestamp == lastUpdate) {
            // never actually reached today, but a naive "randomness" pattern
            lastUpdate = block.timestamp + 1;
        } else {
            lastUpdate = block.timestamp;
        }
        emit PriceUpdated(p, lastUpdate);
    }
}