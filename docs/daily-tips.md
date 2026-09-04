# Slither tips of the day

> Maintained by `scripts/daily_update.py` (Daily Green automation) — one
> dated, non-empty security tip per day, rotated from the pool in
> `scripts/tips_pool.json`. Pause by creating a `.daily-pause` file in the
> repo root, or unload the scheduler job (see README, Daily Green).


## 2026-08-23 — Tip of the day: Access control lives in three places — check all of them

Missing `onlyOwner` is the classic, but also check: (1) functions that should be admin-only but are public, (2) init functions that any caller can front-run to become the admin (see `initializer` detector), (3) `selfdestruct` reachable by non-owners. Slither: `missing-modifier`, `initializer`, `controlled-selfdestruct`.

> `slither . --detect missing-modifier,initializer,controlled-selfdestruct`


## 2026-08-24 — Tip of the day: Front-running: order-dependent transactions need commit-reveal

Any transaction whose profit depends on being early (auctions, token swaps, reveals) will be front-run by bots. For auctions, use commit-reveal (hash submitted first, value revealed later). For swaps, enforce slippage limits. Auditors flag 'no slippage parameter' as high severity even when 'users can choose' — because they can't choose fast enough.

> `slither . --detect assembly  # and review the auction/reveal flow manually`


## 2026-08-25 — Tip of the day: Spot-price oracles are a flash-loan away from a rug

Reading `pair.getReserves()` or `pool.balanceOf()` as a price source lets a flash loan move the price mid-transaction. Use time-weighted (TWAP) oracles (Uniswap v3 `consult`, Chainlink) and add a staleness check. If a contract prices collateral against the DEX it also trades on, the auditor will give it a red flag.

> `slither-chat audit contracts/Lending.sol`


## 2026-08-26 — Tip of the day: State-variable shadowing silently splits storage

An inherited contract redeclaring a parent's state variable gets an independent storage slot — reads and writes go to different places depending on which contract's view you call. The `shadowing-state` and `shadowing-abstract` detectors find every case. Rename or use an explicit getter.

> `slither . --detect shadowing-state,shadowing-abstract`


## 2026-08-27 — Tip of the day: Default visibility: a state variable without a keyword is public

State variables default to `public` (and internal visibility for functions is explicit). A public `address owner` is harmless alone but combined with a missing setter check is a takeover. More dangerous: `public` arrays of structs leak whole storage. Declare `private` or `internal` explicitly — the `state-variable-default-visibility` detector enforces it.

> `slither . --detect state-variable-default-visibility`


## 2026-08-28 — Tip of the day: Uninitialized storage pointers read arbitrary slots

A local variable of storage pointer type that is never assigned (e.g. `User storage u;`) points at slot 0 — writes clobber the first state variable, reads leak it. This is one of the few Slither findings that is almost always exploitable when it fires. Fix: always initialize the pointer.

> `slither . --detect uninitialized-storage`


## 2026-08-29 — Tip of the day: delegatecall is a storage-collision weapon

`delegatecall` runs foreign code in your storage layout. Differences in slot order between caller and callee silently corrupt state, and `controlled-delegatecall` (user-controlled target) is a full contract takeover. Auditors treat any delegatecall to a non-immutable, non-admin target as critical.

> `slither . --detect controlled-delegatecall`


## 2026-08-30 — Tip of the day: selfdestruct: audit who can call it and what it breaks

Even with `onlyOwner`, selfdestruct sends the whole balance to the owner and deletes code — breaking integrations that assume your address is a contract forever. Slither's `controlled-selfdestruct` with the kill-switch pattern review covers the common case; also check `suicide` in assembly.

> `slither . --detect controlled-selfdestruct`


## 2026-08-31 — Tip of the day: send() vs transfer() vs call(): 2300 gas is a footgun

`transfer`/`send` forward 2300 gas — enough for a plain recipient, not enough for a contract that logs or has a receive() with logic. Wallets and multisigs will fail to receive funds, permanently bricking withdrawals. Prefer call + reentrancy protection, or document the 2300 assumption.

> `slither . --detect suicidal,unchecked-send  # and review withdrawal paths by hand`


## 2026-09-01 — Tip of the day: ERC-777 hooks re-open the reentrancy door

ERC-777 tokensNotify receivers on transfer, letting a malicious receiver re-enter mid-transfer — this is how the famous 2019 imBTC drain worked. If your protocol integrates an ERC-777 (or any hook-capable token), reentrancy guards must cover the token transfer itself, not just the surrounding function.

> `slither . --detect reentrancy-eth  # on every transfer handling path`


## 2026-09-02 — Tip of the day: Gas griefing: loops bounded by attacker-controlled input

A loop over `pendingWithdrawals.length` where the attacker controls the array size lets them push thousands of entries and make your function cost more than the block gas limit — permanent DoS. Cap array sizes, batch with page offsets, or compute per-user instead of global. Slither's `costly-loop` flags them.

> `slither . --detect costly-loop`


## 2026-09-03 — Tip of the day: Missing events strangle monitoring and forensics

No event on transfer, deposit, or admin change means no off-chain tracking, no alerting, and no way to reconstruct an attack later. Self-audit rule: every state-changing function emits an event. Slither's `events-maths` and `events-access` detectors remind you on the arithmetic and access-control sides.

> `slither . --detect events-maths,events-access`


## 2026-09-04 — Tip of the day: Floating pragma is a deployment lottery

`pragma solidity ^0.8.0;` compiles to *whatever compiler the deployer has*. A patch release can change codegen, or worse, your CI verifies one version and you deploy another. Pin the exact version for anything that ships; the `pragma` detector lists every file and its constraint.

> `slither . --detect pragma`

