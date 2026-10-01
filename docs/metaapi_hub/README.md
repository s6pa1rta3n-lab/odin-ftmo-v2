# MetaAPI hub

Shared synchronization owner for the BTC, US100, and Gold FTMO engines.

The hub ships **off**. Engines keep their current MetaAPI connections until `ODIN_METAAPI_HUB` is set on purpose. Odin approved production cutover on 2026-10-01 so the procedure and rollback are in git. This tree does not install or edit a systemd unit on `matt-berserker`. Strategy and config stay intact; the hub is plumbing.

| Document | What it is |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Root cause, process layout, request path |
| [DECISIONS.md](DECISIONS.md) | What we checked, what we rejected, what we shipped |
| [FAILURE_MODES.md](FAILURE_MODES.md) | 429, 504, broker disconnect, duplicate orders |
| [RUNBOOK.md](RUNBOOK.md) | How to run shadow mode and how to read health |
| [CUTOVER.md](CUTOVER.md) | Stages 2 and 3 done, Stage 4 approved, rollback |
| [TEST_EVIDENCE.md](TEST_EVIDENCE.md) | Local suite plus Stage 2 and Stage 3 results |
| [evidence/2026-10-01-stage3-canary.md](evidence/2026-10-01-stage3-canary.md) | Stage 3 canary report (no token) |

The production tree on the GCP VM `matt-berserker` (`us-central1-a`) is `/home/solveetcoagula/odin_ftmo`. Service files in the repo already point at that path. The Stage 3 canary did not git-pull that tree. Stage 4 uses a durable checkout of this branch (not `/tmp`) plus `PYTHONPATH` when the live tree has no `metaapi_hub` package. That copy is an operator step. This pull request does not perform it.
