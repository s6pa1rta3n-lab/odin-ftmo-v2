# MetaAPI hub

Shared synchronization owner for the BTC, US100, and Gold FTMO engines.

The hub ships **off** until `ODIN_METAAPI_HUB` is set. Operators completed the Stage 4 cutover on matt-berserker on 2026-10-01 (**PASS**, ~12:44–12:49 EDT). This tree records that evidence and the rollback. It does not itself install or edit a unit. Strategy and config stay intact; the hub is plumbing.

| Document | What it is |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Root cause, process layout, request path |
| [DECISIONS.md](DECISIONS.md) | What we checked, what we rejected, what we shipped |
| [FAILURE_MODES.md](FAILURE_MODES.md) | 429, 504, broker disconnect, duplicate orders |
| [RUNBOOK.md](RUNBOOK.md) | How to run shadow mode and how to read health |
| [CUTOVER.md](CUTOVER.md) | Stages 2–4 PASS, and the exact rollback |
| [TEST_EVIDENCE.md](TEST_EVIDENCE.md) | Local suite plus Stage 2, 3, and 4 results |
| [evidence/2026-10-01-stage3-canary.md](evidence/2026-10-01-stage3-canary.md) | Stage 3 canary report (no token) |
| [evidence/2026-10-01-stage4-cutover.md](evidence/2026-10-01-stage4-cutover.md) | Stage 4 production cutover report (no token) |

The production tree on the GCP VM `matt-berserker` (`us-central1-a`) is `/home/solveetcoagula/odin_ftmo`. The Stage 4 report places the durable hub package at `/home/solveetcoagula/odin-ftmo-hub` and also copies `metaapi_hub/` into the live tree. This pull request records that layout. It does not deploy it.
