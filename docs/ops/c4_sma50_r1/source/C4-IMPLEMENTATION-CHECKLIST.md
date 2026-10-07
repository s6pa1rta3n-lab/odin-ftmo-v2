# C4 + drip freeze — implementation checklist (no execution gaps)

**Odin approval (2026-10-07 ~8:05 AM ET):** Freeze live catalogue drip AND set up Candidate 4. Test and see. Absolute requirement: no order-execution or implementation issues.

**Owners:** Trading Ops (live VM / services). Strategy Implementer if code must land in git. BTC Strategies = research rules only; does not touch live.

---

## A. Freeze the live drip (do first)

Service: `catalogue-btc-15m.service` on matt-berserker  
Script: `/home/solveetcoagula/ftmo-catalogue/btc_15m_buy.py`  
Account MetaAPI: `a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf`

Freeze means **no new catalogue market buys**. Prefer a reversible config flag / env (e.g. `FREEZE_NEW_BUYS=1`) over deleting the service so TP recovery / tp_sweep can still run on existing tickets if that is how the script is structured.

Must verify after freeze:
1. Service still healthy OR intentionally stopped with Ops note.
2. Next :00/:30 slot does **not** place a new `CATALOGUE_BTC_15M` buy.
3. Existing open catalogue positions: **leave management policy explicit** — recommended: keep TP modify/recovery for open tickets; do **not** mass-close unless Odin says so.
4. Margin ≥22% hourly cut behavior: document whether it still runs while frozen.
5. Sheet updater: still writes, or note lag.
6. Journalctl proof of skipped slots after freeze.

Do **not** rewrite drip into C4 in-place.

---

## B. Candidate 4 rules (exact)

| Item | Value |
|---|---|
| Symbol | BTCUSD |
| Volume | 0.01 (or document scaled size so full stop ≈ $400–$450) |
| Regime | Prior UTC daily close vs SMA50 |
| Long | close > SMA50 → buy next 00:00 UTC only |
| Short | close < SMA50 → sell next 00:00 UTC only |
| Flat | close == SMA50 |
| Entry clock | 00:00 UTC M1 open only; skip missing bar |
| Max positions | **1 total** (no pyramid, no drip) |
| Stop | ±412.91 from entry (hard stop on the order / position) |
| Target | ±412.91 from entry (R=1) |
| Double-touch | Treat as stop |
| Comment | Distinct from drip, e.g. `C4_SMA50_R1` |
| Risk day stop | No new entries if this book closed+float ≤ −2% equity (CE(S)T day) |
| Account floor buffer | No new entries if within 3% of FTMO 10% max-loss floor |

First possible entry after deploy: next **00:00 UTC** (= **8:00 PM ET** while EDT).

Regime as of morning research: spot ~83.6k, SMA50 was ~80.3k → expect **long** unless daily close flips.

---

## C. Pre-flight before first live order (blocking)

All must pass; if any fail, **do not arm** entries:

1. **MetaAPI** London host reachable; account id correct; no stale token.
2. Symbol BTCUSD tradeable now (not in daily break ~4:55–5:05 PM ET).
3. SMA50 computed from **same price source** you will trade (document feed); prior close only.
4. Order path places **market + SL + TP in one atomic path** or guaranteed modify-with-retry; never leave a position with TP-only and no SL.
5. SL/TP distances survive broker digits (2dp half-up like drip TP) — verify 412.91 rounds correctly both sides.
6. **Short path tested** in demo/paper or dry-run even if first live day is long (sell + SL above + TP below).
7. Max-1 enforced: second signal while open is hard skip (unit test / dry-run log).
8. Freeze still holds: drip cannot open during C4 arming.
9. Kill switch documented and tested (env flag or service stop < 60s).
10. Paper/dry-run one full long ticket lifecycle OR first live ticket on **minimum volume** with Ops watching fill+SL+TP on broker.
11. Logging: entry, regime value, SMA50, SL, TP, ticket id, comment; alert on reject / partial / timeout / 504.
12. No conflict with Asterdex / Griff (paused) — confirm comments and magic/ids won’t collide.

---

## D. Success / kill (first 10 trading days)
- Keep: no day worse than −2% from C4 book; C4 cumulative not worse than −3%.
- Kill: FTMO daily/max near-miss from C4, or 10 days C4 net < −2%.

---

## E. Report back to BTC Strategies / Odin
- Freeze proof (timestamp + journal excerpt summary)
- C4 service/path name, account, first armed entry time
- Pre-flight checklist pass/fail list
- Any deviation from rules above
