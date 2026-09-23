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


## 2026-09-05 — Tip of the day: Dead code is how audit findings hide

Functions nobody calls, modifiers never applied, internal helpers orphaned by refactors — each is a place where intent and reality diverge, and auditors waste budget proving it's unreachable. `dead-code` plus `unused-return` makes the sweep mechanical.

> `slither . --detect dead-code,unused-return`


## 2026-09-06 — Tip of the day: assert() vs require(): knows the gas refund difference

`assert` failures consume all provided gas (for the invalid opcode), `require` refunds the remainder. Use `require` for user-input and invariant checks you expect to actually fail; reserve `assert` for internal invariants that should never break. Slither's `assert-state-changing` and `incorrect-equality` catch misuse patterns.

> `slither . --detect incorrect-equality`


## 2026-09-07 — Tip of the day: fallback vs receive: know which one fires

`receive()` handles plain ETH transfers, `fallback()` catches everything else including calldata. A contract with only `fallback()` still accepts ETH silently, and a fallback that does nontrivial work can be forced to run via a zero-data call, gassing the sender. The `uninitialized-state` style audit checklist covers the layout; check both functions for logic.

> `slither . --detect locked-ether,unused-state`


## 2026-09-08 — Tip of the day: The approve/transferFrom race is why increaseAllowance exists

`approve(X, 100)` then `X` spends 100, then `approve(X, 100)` again — the second approve can be sandwiched: `X` spends the remaining allowance before your new value lands. Use `increaseAllowance`/`decreaseAllowance`. Slither's `controlled-delegatecall` is unrelated, but its sibling audit of token wrappers catches naive re-implementations.

> `slither . --detect arbitrary-send-erc20`


## 2026-09-09 — Tip of the day: Upgradeable proxies: storage layout can never change

With proxy + implementation, the implementation's variables must keep the exact same slot order forever — inserting a variable shifts every downstream slot to garbage. The `slither-upgrade` plugin (truffle/hardhat variants) compares proxy vs implementation and flags mismatches automatically.

> `slither . --detect shadowing-state --filter-paths lib  # plus slither-upgrade in CI`


## 2026-09-10 — Tip of the day: The initializer can be front-run — call it in the same tx as deploy

An uninitalized proxy is owned by nobody — anyone can call `initialize()` first with their own address. Deploy and initialize atomically (constructor of a factory, or deploy script that calls init in the same transaction). The `initializer` detector finds init functions callable by anyone.

> `slither . --detect initializer`


## 2026-09-11 — Tip of the day: block.timestamp is manipulable within ~15 seconds

Validators can shift timestamp a little — enough to game 'time-lock of 1 block', or to flip a threshold at the boundary. Never use timestamps for randomness or tight racing conditions. Slither's `assembly`/`timestamp` manual review: search for `block.timestamp`/`now` in every comparison, not just in random functions.

> `slither . --detect assembly && grep -rn 'block.timestamp\|now' contracts/`


## 2026-09-12 — Tip of the day: prevrandao is not randomness — it is miner-influenced entropy

Post-Merge, `block.prevrandao` (formerly `block.difficulty`) looks random but validators can bias it, and MEV bots can reorder around it. Any lottery, NFT reveal, or NFT mint that uses it is exploitable. Real options: Chainlink VRF, commit-reveal, or verifiable delay functions. Auditors will flag prevrandao-derived randomness as medium-or-higher.

> `grep -rn 'prevrandao\|difficulty' contracts/`


## 2026-09-13 — Tip of the day: Oracle staleness: a frozen oracle is an oracle

Chainlink aggregators expose `latestRoundData()` — check that `updatedAt` is recent and `answeredInRound >= roundId`, otherwise a stalled aggregator returns last year's price and your liquidations suddenly fire everywhere. This exact bug (missing staleness check) has drained several lending protocols.

> `grep -rn 'latestRoundData' contracts/ && grep -rn 'updatedAt' contracts/`


## 2026-09-14 — Tip of the day: Slippage protection is not optional in swaps

A swap without `minAmountOut`/`maxInput` lets any sandwich bot take the difference. 'User could set it themselves' fails in practice: most users accept defaults. Enforce a sane default and expose the parameter. Audit checklist: every swap entry point has slippage machinery.

> `slither-chat audit contracts/SwapRouter.sol`


## 2026-09-15 — Tip of the day: Emergency pause: the cheapest insurance in the codebase

A pausable contract (OpenZeppelin `Pausable`) costs ~20 lines and turns a live exploit into a 30-second response. Without it, a found vulnerability means a race between you and the attacker. Combine with `onlyOwner` and a time-delayed or multi-sig admin so a key compromise can't pause permanently.

> `slither . --detect missing-modifier  # then add Pausable to critical paths`


## 2026-09-16 — Tip of the day: Rate limiting and circuit breakers stop brute-force drains

For withdrawal-heavy protocols, a per-block/per-hour cap converts 'drain everything in one tx' into 'drain must wait N hours', buying time for alarms and pauses. Cheap to implement, disproportionately effective. Slither can't auto-find this — put it on the manual checklist.

> `slither-chat audit contracts/Withdrawals.sol`


## 2026-09-17 — Tip of the day: Trusted automation: keepers are an attack surface

If a keeper or bot triggers your functions, anyone can usually trigger them too — so every keeper-called function must be safe when called by a random address at a random time. Audit keeper entry points for: griefing loops, front-running of the trigger, and state assumptions about who called.

> `slither . --detect controlled-delegatecall,missing-modifier`


## 2026-09-18 — Tip of the day: Library shadowing: an attacker can't, but a bad merge can

Two imports naming different contracts with the same identifier is a compile error, but a *library redeclared* or a `using ... for` pointing at a wrong library silently changes behavior. Slither's `assembly` and `controlled-delegatecall` detectors plus a careful diff-review of library usage catches the merge-time variant.

> `slither . --detect controlled-delegatecall`


## 2026-09-19 — Tip of the day: Pack your structs: storage is the biggest runtime cost

Storage is 20,000 gas per 32-byte slot written. Order struct fields so they pack: uint128+uint128 in one slot, address+uint96 in another, bools together. Slither's `constable-states` and the gas report from `forge snapshot` quantify it. Same order matters for layout-compat in upgrades.

> `slither . --detect constable-states && forge snapshot`


## 2026-09-20 — Tip of the day: indexed event parameters are your free index

Only `indexed` (max 3) parameters can be filtered by off-chain indexers. Non-indexed args are invisible to topic filters — put the address/ID you query by in indexed position. This is a data-availability finding, not just style: a registry nobody can query is a registry nobody trusts.

> `grep -rn 'event ' contracts/ | head -20`


## 2026-09-21 — Tip of the day: memory vs storage: the copy semantics that eat funds

`storage` refs alias the source (writes persist), `memory` copies (writes vanish). Assigning `User storage u = users[i]` then mutating `u.balance` without a second write is a silent no-op that withdraws show as 'successful' but never move funds. The `uninitialized-storage` and `assembly` detectors help, but a reviewer pass over every struct mutation is mandatory.

> `slither . --detect uninitialized-storage`


## 2026-09-22 — Tip of the day: Modifier order: require() before _; — always

Modifiers run top-down; `_` is the function body. A modifier that does work after `_` runs *after* state changes, turning `nonReentrant`-style guards into decorations. Convention: all checks above `_`, all effects below, never `_` twice. Slither's `missing-zero-check` adds the classic first-line-of-modifier check.

> `slither . --detect missing-zero-check`


## 2026-09-23 — Tip of the day: The 10-minute audit checklist

1) `reentrancy-eth/no-eth` 2) `tx-origin` 3) `unchecked-lowlevel/send` 4) `arithmetic` 5) `missing-modifier` 6) `shadowing-*` 7) `uninitialized-storage` 8) `controlled-delegatecall/selfdestruct` 9) `pragma` + `dead-code` 10) run slither-chat for explanations, patch hints, and the full triage report. Ten minutes, every contract, every PR.

> `slither . --detect all && slither-chat audit . --out report.md`

