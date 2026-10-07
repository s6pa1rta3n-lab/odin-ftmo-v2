# EURUSD Asian “Crawl Back” — FTMO survival book

**Odin order:** 2026-10-07 ~1:39 PM ET  
**Purpose:** Survive and rebuild toward ~$95k with small night-only EURUSD mean-reversion trades. Not a monthly-profit strategy. Replaces C4 + catalogue on this FTMO account.

## Cutover (done 2026-10-07)

1. Stopped + disabled `c4-sma50-r1.service`, `catalogue-btc-15m.service`; stopped `btc-sheet-updater.service`
2. Closed all 34 open `CATALOGUE_BTC_15M` positions; cancelled pending (none)
3. Evidence: `FLATTEN-EVIDENCE.json` — before equity ~$91,645 / 34 pos → after equity = balance **$91,614.96** / **0 pos / 0 orders**
4. Griff FTMO engines were already inactive; Asterdex untouched

## Live rules

| Item | Rule |
|------|------|
| Symbol | EURUSD only |
| Session | 18:00–00:00 America/New_York; flatten by session end; no London/NY opens; no hold into Europe |
| Chart | 15-minute |
| Setup | Stall at high/low of short evening range (exhaustion wick / rejection); fade toward session mid / volume average |
| Risk | Equity-scaled toward fail line; survival clamp **$100–$150** max risk per trade |
| Stop | ~6 pips hard SL |
| Target | Hard R:R **1:1 to 1:1.5** (~$120–$180); no trailing |
| Lot cap | Verify vs pip value; ~1.5–2.0 lots max at 6-pip SL for $100–$120 risk |
| Comment | `CRAWLBACK_EURUSD_ASIA` |
| Arm | `CRAWL_ARMED=1` required; default 0 |

## Risk formula (survival phase)

```
FAIL_EQUITY = 90000   # ~10% FTMO max-loss floor on $100k (configurable)
TARGET_EQUITY = 95000
risk = clamp(
  RISK_MIN + (RISK_MAX - RISK_MIN) * (equity - FAIL_EQUITY) / (TARGET_EQUITY - FAIL_EQUITY),
  RISK_MIN, RISK_MAX
)
# defaults RISK_MIN=100, RISK_MAX=150
lots = min(LOT_CAP, risk / (SL_PIPS * PIP_VALUE_PER_LOT))
```

At equity ≈ $91.6k this yields risk near the **$100** floor → ~16 consecutive full losses to the $90k floor (order-of-magnitude), matching Odin’s “room to breathe.”

## EURUSD lot math (FTMO / USD account)

- 1.00 lot ≈ $10 per pip on EURUSD  
- 6 pip SL → **$60 risk per lot**  
- $100 risk → **1.67 lots**; $120 → **2.00 lots**; $150 → **2.50 lots** (cap at 2.00 unless Ops raises `LOT_CAP`)

Confirm tick value from MetaAPI symbol spec before first live fill.

## Explicit non-goals

- Do not re-enable C4 / catalogue for recovery on this account  
- Do not arm research ACCEPT candidates (e.g. C48E) on this account  
- Do not raise risk to chase the challenge pass overnight

## Implementation patches

See `PATCH-NOTES.md` (2026-10-07 paranoid pre-arm): comment-only position isolation, scoped order cancel, MetaAPI pip/$ refresh, optional `CRAWL_TEST_ORDER=1` one-shot (do not leave armed or test-flagged in the unit).
