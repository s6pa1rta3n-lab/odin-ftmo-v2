# Ops records

Durable records of live operations performed by Trading Ops on matt-berserker, copied into version control after the fact. Files here describe what already runs; they do not install, enable, or edit anything on the VM and do not change trading-code behaviour. Hub-specific operations (cutover, restarts, failure modes) stay under [`../metaapi_hub/`](../metaapi_hub/README.md).

| Record | Scope |
| --- | --- |
| [c4_sma50_r1/](c4_sma50_r1/README.md) | Candidate 4 book (`C4_SMA50_R1`, BTCUSD SMA50 R = 1) and the 2026-10-07 live catalogue drip freeze (`FREEZE_NEW_BUYS=1`) |

Conventions:

- `evidence/` — dated reports written from the operator's status; no tokens, no secrets.
- `source/` — the operator's own briefs / checklists / status files, verbatim.
- `unit/` — snapshots of live systemd unit files for the record only; never install from this repository.
