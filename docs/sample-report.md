# Audit report: `examples/vault.sol`

- **Slither**: 0.11.6 (compiler n/a)
- **Backend**: `rule`
- **Duration**: 0.5s
- **Findings**: 6 (high=2, medium=0, low=1, info=3)

## Summary

| Severity | Count |
| --- | --- |
| High | 2 |
| Medium | 0 |
| Low | 1 |
| Informational | 3 |

## Findings

### 1. `reentrancy-eth` — High

**Where**: ReentrantVault:withdraw (lines 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39) · **Confidence**: Medium

**Detector**: Reentrancy in ReentrantVault.withdraw(uint256) (examples/vault.sol#29-39):
	External calls:
	- (ok,None) = msg.sender.call{value: amount}() (examples/vault.sol#34)
	State variables written after the call(s):
	- balances[msg.sender] = balanceBefore - amount (examples/vault.sol#38)
	ReentrantVault.balances (examples/vault.sol#10) can be used in cross function reentrancies:
	- ReentrantVault.balances (examples/vault.sol#10)
	- ReentrantVault.deposit() (examples/vault.sol#20-25)
	- ReentrantVault.withdraw(uint256) (examples/vault.sol#29-39)
	- ReentrantVault.withdrawMany(address[]) (examples/vault.sol#42-51)

**Explanation**:

External call into an untrusted contract before state is updated. An attacker contract can re-enter the function and drain funds because the balance/state is still the pre-update value. This is the classic DAO-hack class of bug.

**Suggested fix**:

Apply checks-effects-interactions: update all state (including balances) before making the external call, or use a reentrancy guard modifier.

**Flagged code**:

```solidity
     26 | 
     27 |     /// @notice Withdraw your balance.
     28 |     /// @dev VULNERABLE: the external `call` happens BEFORE `balances[msg.sender] = 0`.
>>   29 |     function withdraw(uint256 amount) external {
>>   30 |         require(balances[msg.sender] >= amount, "insufficient balance");
>>   31 |         uint256 balanceBefore = balances[msg.sender];
>>   32 | 
>>   33 |         // External call to an attacker-controlled receiver...
>>   34 |         (bool ok, ) = msg.sender.call{value: amount}("");
>>   35 |         require(ok, "transfer failed");
>>   36 | 
>>   37 |         // ...and only THEN the state is updated.
>>   38 |         balances[msg.sender] = balanceBefore - amount;
>>   39 |     }
     40 | 
     41 |     /// @notice Batch withdraw for several users (loop with external call).
     42 |     function withdrawMany(address[] calldata users) external {
```

**Suggested patch (review before applying)**:

```diff
--- a/vault.sol
+++ b/vault.sol  (suggested hardening — review before applying)
@@ -27,15 +27,15 @@
    27 |     /// @notice Withdraw your balance.
    28 |     /// @dev VULNERABLE: the external `call` happens BEFORE `balances[msg.sender] = 0`.
-   29 |     function withdraw(uint256 amount) external {
-   30 |         require(balances[msg.sender] >= amount, "insufficient balance");
-   31 |         uint256 balanceBefore = balances[msg.sender];
-   32 | 
-   33 |         // External call to an attacker-controlled receiver...
-   34 |         (bool ok, ) = msg.sender.call{value: amount}("");
-   35 |         require(ok, "transfer failed");
-   36 | 
-   37 |         // ...and only THEN the state is updated.
-   38 |         balances[msg.sender] = balanceBefore - amount;
-   39 |     }
    40 | 
    41 |     /// @notice Batch withdraw for several users (loop with external call).
+> apply checks-effects-interactions; update balances before external calls

```

### 2. `reentrancy-eth` — High

**Where**: ReentrantVault:withdrawMany (lines 42, 43, 44, 45, 46, 47, 48, 49, 50, 51) · **Confidence**: Medium

**Detector**: Reentrancy in ReentrantVault.withdrawMany(address[]) (examples/vault.sol#42-51):
	External calls:
	- (ok,None) = users[i].call{value: amount}() (examples/vault.sol#46)
	State variables written after the call(s):
	- balances[users[i]] = 0 (examples/vault.sol#48)
	ReentrantVault.balances (examples/vault.sol#10) can be used in cross function reentrancies:
	- ReentrantVault.balances (examples/vault.sol#10)
	- ReentrantVault.deposit() (examples/vault.sol#20-25)
	- ReentrantVault.withdraw(uint256) (examples/vault.sol#29-39)
	- ReentrantVault.withdrawMany(address[]) (examples/vault.sol#42-51)

**Explanation**:

External call into an untrusted contract before state is updated. An attacker contract can re-enter the function and drain funds because the balance/state is still the pre-update value. This is the classic DAO-hack class of bug.

**Suggested fix**:

Apply checks-effects-interactions: update all state (including balances) before making the external call, or use a reentrancy guard modifier.

**Flagged code**:

```solidity
     39 |     }
     40 | 
     41 |     /// @notice Batch withdraw for several users (loop with external call).
>>   42 |     function withdrawMany(address[] calldata users) external {
>>   43 |         for (uint256 i = 0; i < users.length; i++) {
>>   44 |             uint256 amount = balances[users[i]];
>>   45 |             if (amount == 0) continue;
>>   46 |             (bool ok, ) = users[i].call{value: amount}("");
>>   47 |             if (ok) {
>>   48 |                 balances[users[i]] = 0;
>>   49 |             }
>>   50 |         }
>>   51 |     }
     52 | }
```

**Suggested patch (review before applying)**:

```diff
--- a/vault.sol
+++ b/vault.sol  (suggested hardening — review before applying)
@@ -40,13 +40,13 @@
    40 | 
    41 |     /// @notice Batch withdraw for several users (loop with external call).
-   42 |     function withdrawMany(address[] calldata users) external {
-   43 |         for (uint256 i = 0; i < users.length; i++) {
-   44 |             uint256 amount = balances[users[i]];
-   45 |             if (amount == 0) continue;
-   46 |             (bool ok, ) = users[i].call{value: amount}("");
-   47 |             if (ok) {
-   48 |                 balances[users[i]] = 0;
-   49 |             }
-   50 |         }
-   51 |     }
    52 | }
+> apply checks-effects-interactions; update balances before external calls

```

### 3. `calls-loop` — Low

**Where**: ReentrantVault:withdrawMany (lines 42, 43, 44, 45, 46, 47, 48, 49, 50, 51) · **Confidence**: Medium

**Detector**: ReentrantVault.withdrawMany(address[]) (examples/vault.sol#42-51) has external calls inside a loop: (ok,None) = users[i].call{value: amount}() (examples/vault.sol#46)

**Explanation**:

External calls inside a loop. Each iteration pays for a call and can re-enter; a malicious callee can DoS the whole loop.

**Suggested fix**:

Use pull-over-push (let users withdraw individually).

**Flagged code**:

```solidity
     39 |     }
     40 | 
     41 |     /// @notice Batch withdraw for several users (loop with external call).
>>   42 |     function withdrawMany(address[] calldata users) external {
>>   43 |         for (uint256 i = 0; i < users.length; i++) {
>>   44 |             uint256 amount = balances[users[i]];
>>   45 |             if (amount == 0) continue;
>>   46 |             (bool ok, ) = users[i].call{value: amount}("");
>>   47 |             if (ok) {
>>   48 |                 balances[users[i]] = 0;
>>   49 |             }
>>   50 |         }
>>   51 |     }
     52 | }
```

**Suggested patch (review before applying)**:

```diff
--- a/vault.sol
+++ b/vault.sol  (suggested hardening — review before applying)
@@ -40,13 +40,13 @@
    40 | 
    41 |     /// @notice Batch withdraw for several users (loop with external call).
-   42 |     function withdrawMany(address[] calldata users) external {
-   43 |         for (uint256 i = 0; i < users.length; i++) {
-   44 |             uint256 amount = balances[users[i]];
-   45 |             if (amount == 0) continue;
-   46 |             (bool ok, ) = users[i].call{value: amount}("");
-   47 |             if (ok) {
-   48 |                 balances[users[i]] = 0;
-   49 |             }
-   50 |         }
-   51 |     }
    52 | }
+> avoid external calls inside loops (gas griefing)

```

### 4. `solc-version` — Informational

**Where**: - (lines 2) · **Confidence**: High

**Detector**: Version constraint ^0.8.13 contains known severe issues (https://solidity.readthedocs.io/en/latest/bugs.html)
	- VerbatimInvalidDeduplication
	- FullInlinerNonExpressionSplitArgumentEvaluationOrder
	- MissingSideEffectsOnSelectorAccess
	- StorageWriteRemovalBeforeConditionalTermination
	- AbiReencodingHeadOverflowWithStaticArrayCleanup
	- DirtyBytesArrayToStorage
	- InlineAssemblyMemorySideEffects
	- DataLocationChangeInInternalOverride
	- NestedCalldataArrayAbiReencodingSizeValidation.
It is used by:
	- ^0.8.13 (examples/vault.sol#2)

**Explanation**:

A Slither detector (solc-version) flagged this code — see the detector documentation for the canonical explanation.. Static-analysis rules flag patterns that correlate with real exploits; treat every finding as actionable until proven benign.

**Suggested fix**:

Review the flagged lines; add explicit guards or refactor the pattern the detector describes.

**Flagged code**:

```solidity
      1 | // SPDX-License-Identifier: MIT
>>    2 | pragma solidity ^0.8.13;
      3 | 
      4 | /// @title ReentrantVault — deliberately vulnerable (reentrancy)
      5 | /// @dev Educational example for slither-chat. DO NOT use in production.
```

**Suggested patch (review before applying)**:

```diff
--- a/vault.sol
+++ b/vault.sol  (suggested hardening — review before applying)
@@ -1,4 +1,4 @@
     1 | // SPDX-License-Identifier: MIT
-    2 | pragma solidity ^0.8.13;
     3 | 
     4 | /// @title ReentrantVault — deliberately vulnerable (reentrancy)
+> review the flagged lines; consult the detector docs for the canonical fix

```

### 5. `low-level-calls` — Informational

**Where**: ReentrantVault:withdraw (lines 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39) · **Confidence**: High

**Detector**: Low level call in ReentrantVault.withdraw(uint256) (examples/vault.sol#29-39):
	- (ok,None) = msg.sender.call{value: amount}() (examples/vault.sol#34)

**Explanation**:

Preference of low-level calls over high-level Solidity calls. Low-level calls bypass checks and return raw bools; they hide errors and enable subtle bugs.

**Suggested fix**:

Use high-level calls with try/catch.

**Flagged code**:

```solidity
     26 | 
     27 |     /// @notice Withdraw your balance.
     28 |     /// @dev VULNERABLE: the external `call` happens BEFORE `balances[msg.sender] = 0`.
>>   29 |     function withdraw(uint256 amount) external {
>>   30 |         require(balances[msg.sender] >= amount, "insufficient balance");
>>   31 |         uint256 balanceBefore = balances[msg.sender];
>>   32 | 
>>   33 |         // External call to an attacker-controlled receiver...
>>   34 |         (bool ok, ) = msg.sender.call{value: amount}("");
>>   35 |         require(ok, "transfer failed");
>>   36 | 
>>   37 |         // ...and only THEN the state is updated.
>>   38 |         balances[msg.sender] = balanceBefore - amount;
>>   39 |     }
     40 | 
     41 |     /// @notice Batch withdraw for several users (loop with external call).
     42 |     function withdrawMany(address[] calldata users) external {
```

**Suggested patch (review before applying)**:

```diff
--- a/vault.sol
+++ b/vault.sol  (suggested hardening — review before applying)
@@ -27,15 +27,15 @@
    27 |     /// @notice Withdraw your balance.
    28 |     /// @dev VULNERABLE: the external `call` happens BEFORE `balances[msg.sender] = 0`.
-   29 |     function withdraw(uint256 amount) external {
-   30 |         require(balances[msg.sender] >= amount, "insufficient balance");
-   31 |         uint256 balanceBefore = balances[msg.sender];
-   32 | 
-   33 |         // External call to an attacker-controlled receiver...
-   34 |         (bool ok, ) = msg.sender.call{value: amount}("");
-   35 |         require(ok, "transfer failed");
-   36 | 
-   37 |         // ...and only THEN the state is updated.
-   38 |         balances[msg.sender] = balanceBefore - amount;
-   39 |     }
    40 | 
    41 |     /// @notice Batch withdraw for several users (loop with external call).
+> use high-level calls with try/catch instead of .call()

```

### 6. `low-level-calls` — Informational

**Where**: ReentrantVault:withdrawMany (lines 42, 43, 44, 45, 46, 47, 48, 49, 50, 51) · **Confidence**: High

**Detector**: Low level call in ReentrantVault.withdrawMany(address[]) (examples/vault.sol#42-51):
	- (ok,None) = users[i].call{value: amount}() (examples/vault.sol#46)

**Explanation**:

Preference of low-level calls over high-level Solidity calls. Low-level calls bypass checks and return raw bools; they hide errors and enable subtle bugs.

**Suggested fix**:

Use high-level calls with try/catch.

**Flagged code**:

```solidity
     39 |     }
     40 | 
     41 |     /// @notice Batch withdraw for several users (loop with external call).
>>   42 |     function withdrawMany(address[] calldata users) external {
>>   43 |         for (uint256 i = 0; i < users.length; i++) {
>>   44 |             uint256 amount = balances[users[i]];
>>   45 |             if (amount == 0) continue;
>>   46 |             (bool ok, ) = users[i].call{value: amount}("");
>>   47 |             if (ok) {
>>   48 |                 balances[users[i]] = 0;
>>   49 |             }
>>   50 |         }
>>   51 |     }
     52 | }
```

**Suggested patch (review before applying)**:

```diff
--- a/vault.sol
+++ b/vault.sol  (suggested hardening — review before applying)
@@ -40,13 +40,13 @@
    40 | 
    41 |     /// @notice Batch withdraw for several users (loop with external call).
-   42 |     function withdrawMany(address[] calldata users) external {
-   43 |         for (uint256 i = 0; i < users.length; i++) {
-   44 |             uint256 amount = balances[users[i]];
-   45 |             if (amount == 0) continue;
-   46 |             (bool ok, ) = users[i].call{value: amount}("");
-   47 |             if (ok) {
-   48 |                 balances[users[i]] = 0;
-   49 |             }
-   50 |         }
-   51 |     }
    52 | }
+> use high-level calls with try/catch instead of .call()

```


---
_Generated by [slither-chat](https://github.com/pxlcrtiv/slither-chat). Suggested patches are review aids, not autonomous fixes._
