# Paranoid preflight 2026-10-07 (~1:45–1:47 PM ET)

| Check | Result |
|-------|--------|
| Re-poll flat | **PASS** equity=balance $91,614.96, pos=0, ord=0, margin=0 |
| C4 / catalogue disabled | **PASS** inactive + disabled |
| VM install + unit | **PASS** `/home/solveetcoagula/ftmo-crawlback/` + `crawlback-eurusd-asia.service` |
| EURUSD symbol specs | **PASS** pipSize=0.0001, contractSize=100000, minVolume=0.01, profitTickValue=$1/tick → **$10/pip/lot** |
| Risk math @ 6 pip SL | 1.67 lots≈$100; 1.94≈$116; 2.00 lot-cap≈$120 (RISK_MAX $150 capped by LOT_CAP) |
| Test order | **PASS** buy 0.01 `CRAWLBACK_EURUSD_ASIA` orderId/positionId **173856690**, SL+TP set, close `TRADE_RETCODE_DONE` |
| Code smells | comment-only positions; comment-scoped cancels; symbol-spec pip load on VM |
| Arm | **PASS** `CRAWL_ARMED=1`, service active/enabled, journal `armed: true` @ 13:46:48 ET |
| C48E / research live | **PASS** not armed |

Session window starts 18:00 ET; until then bot logs out_of_session and will not enter.
