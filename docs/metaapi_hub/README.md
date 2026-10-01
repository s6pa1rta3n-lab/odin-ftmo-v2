# MetaAPI hub

Shared synchronization owner for the BTC, US100, and Gold FTMO engines.

**Do not cut over until Odin approves.** This change ships with the hub off. Engines keep their current MetaAPI connections until `ODIN_METAAPI_HUB` is set on purpose. No systemd unit on `matt-berserker` is installed or edited by this work.

| Document | What it is |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Root cause, process layout, request path |
| [DECISIONS.md](DECISIONS.md) | What we checked, what we rejected, what we shipped |
| [FAILURE_MODES.md](FAILURE_MODES.md) | 429, 504, broker disconnect, duplicate orders |
| [RUNBOOK.md](RUNBOOK.md) | How to run shadow mode and how to read health |
| [CUTOVER.md](CUTOVER.md) | Staged rollout, rollback, and the production checklist |
| [TEST_EVIDENCE.md](TEST_EVIDENCE.md) | Commands and results from this branch |

The production tree on the GCP VM `matt-berserker` (`us-central1-a`) is `/home/solveetcoagula/odin_ftmo`. This repository is that tree. Service files in the repo already point at that path. The hub code belongs in the same directory when someone later copies this branch onto the VM. That copy is not part of this pull request.
