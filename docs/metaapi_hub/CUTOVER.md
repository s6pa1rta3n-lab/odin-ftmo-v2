# Cutover

**Do not cut over until Odin approves.**

This pull request does not enable the hub, does not place orders, and does not change live systemd units. The default remains `ODIN_METAAPI_HUB` off, which is the current behavior: each engine constructs `MetaApiWrapper` and synchronizes itself.

A live hub must not be started while `griff_engine`, `griff_engine_btc`, and `griff_engine_xau` are still synchronizing. That would be a fourth synchronization on an account that allows one.

London (`ftmo_london_reversal.service`) and Omni (`ftmo_hft_omni.service`) are not wired to the hub. If they are running on the same account, they are additional synchronizations. Stop them or leave the hub in shadow until someone decides their place in the account. This PR does not stop them.

## Stages

### Stage 0 — this pull request

Code and tests only. Engines unchanged at runtime. Stop here until Odin says otherwise.

### Stage 1 — shadow rehearsal, no MetaAPI

On a checkout of this branch, not by editing the running units:

1. `python3 -m metaapi_hub.shadow_probe` exits 0.
2. `sh scripts/run_metaapi_hub_tests.sh` is green.
3. Optional: start `python3 -m metaapi_hub --mode shadow --orders deny` and point a **manual** `ODIN_METAAPI_HUB=shadow` process at it. Do not export that variable in the production unit files.

Shadow mode does not read the token file and does not connect to the broker. `orders_live` in health is false. `broker_order_calls` stays 0.

### Stage 2 — read-only live hub, only after approval

Do this in a window when the three Griff engines can be stopped. Do not do it from this pull request.

1. Stop `griff_engine.service`, `griff_engine_btc.service`, and `griff_engine_xau.service`. Confirm with `systemctl is-active` that they are inactive. Confirm London and Omni are not holding the account, or stop them too.
2. Start the hub by hand, not by installing the example unit:

    ```sh
    python3 -m metaapi_hub \
      --mode live \
      --orders deny \
      --config /home/solveetcoagula/odin_ftmo/config_us100.json \
      --account-id THE_ACCOUNT_ID \
      --socket /run/odin/metaapi-hub.sock
    ```

    Do not add `--orders live` or `--enable-live-orders`. Do not set `ODIN_METAAPI_HUB_ORDERS=live`.
3. Health shows `synchronize_calls == 1`, `orders_live == false`, `connected == true`.
4. Start the three engines with a drop-in that is easy to delete:

    ```
    Environment=ODIN_METAAPI_HUB=on
    Environment=ODIN_METAAPI_HUB_SOCKET=/run/odin/metaapi-hub.sock
    ```

    One engine at a time. After each start, health `clients` grows and `synchronize_calls` stays 1.
5. Watch logs for candle fetches and account info. Orders will raise `ORDERS_DISABLED` and must not show broker code 10009. That is expected. **This stage cannot trade.** Leaving it in production would block entries. It is a proof stage, not the final trading configuration.
6. If `synchronize_calls` climbs once per engine, stop. The engines are still synchronizing themselves. Roll back.

### Stage 3 — live orders, a later change, not this PR

Only after Stage 2 has been watched and Odin has approved trading through the hub:

- Hub: `--mode live --orders live --enable-live-orders` and `ODIN_METAAPI_HUB_ORDERS=live`.
- Confirm the first order is a size the strategy already uses, on one symbol, and that the other two engines did not also send it.
- This repository's example files intentionally omit those switches so they cannot be installed as a live trader by accident.

## Rollback

Rollback returns to today's behavior. It does not require a code revert if the flag was the only production change.

1. Stop the three engines.
2. Remove `ODIN_METAAPI_HUB` and `ODIN_METAAPI_HUB_SOCKET` from their environment.
3. Stop the hub process. If a unit was installed despite this document, `systemctl disable --now` that unit and delete the unit file. `daemon-reload` only if you added a unit.
4. Start the three engines the way they start today, with no hub variable.
5. Confirm the hub socket is gone and the engines log `hub_mode=off`.

After rollback each engine synchronizes itself again. That is the known TooManyRequests behavior. It is still the safe rollback because it is the behavior Odin is running now. Do not invent a third topology during an incident.

## Production checklist

Complete every line before Stage 2. Stage 3 is out of scope until a new approval.

- [ ] Odin has approved this cutover in writing. Until that exists, stop at Stage 0.
- [ ] The branch tests and `python3 -m metaapi_hub.shadow_probe` were green on the commit that will be copied to the VM.
- [ ] No `metaapi.token` value is in the diff (`git diff` / `git log -p`).
- [ ] `setup_gold_service.sh`, `setup_us100_service.sh`, `ftmo_hft_omni.service`, and `ftmo_london_reversal.service` are unchanged.
- [ ] Example units under `deploy/examples/` were not copied to `/etc/systemd/system`.
- [ ] London and Omni are either stopped or explicitly accepted as extra synchronizations. This PR does not switch them.
- [ ] The three Griff units are stopped before the live hub starts.
- [ ] Hub command is `--mode live --orders deny` with no `--enable-live-orders`.
- [ ] Health after all three engines attach: `synchronize_calls` is 1, `orders_live` is false, `broker_order_calls` is 0, `clients` lists the three engines.
- [ ] A candle fetch for BTCUSD, US100.cash, and XAUUSD succeeds through the hub.
- [ ] An order attempt is rejected with `ORDERS_DISABLED` and the broker shows no new ticket.
- [ ] Rollback was rehearsed on the shadow socket: unset the flag, engines construct `MetaApiWrapper` again (they will fail closed in shadow without the SDK; on the VM they will connect directly, so rehearse the flag removal before the live window).
- [ ] Someone is watching logs for the first hour of Stage 2.
- [ ] Stage 3 live orders are **not** part of this approval.

## VM path

| Item | Value |
| --- | --- |
| Host | `matt-berserker`, zone `us-central1-a` |
| Code | `/home/solveetcoagula/odin_ftmo` |
| Config | `/home/solveetcoagula/odin_ftmo/config_us100.json` (not in git) |
| Units | `griff_engine.service`, `griff_engine_btc.service`, `griff_engine_xau.service` |
| This repo | same code layout; do not assume a second checkout on the VM until someone deploys this branch |
