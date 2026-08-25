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

