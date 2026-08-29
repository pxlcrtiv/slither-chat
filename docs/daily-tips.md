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

