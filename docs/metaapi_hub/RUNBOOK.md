# Runbook

Shadow mode is local and does not open a MetaAPI connection. Reviewing this branch does not start the live hub. Stage 4 on the VM is a separate operator step, documented in [CUTOVER.md](CUTOVER.md), and this file does not perform it.

## Tests

```sh
sh scripts/run_metaapi_hub_tests.sh
```

That runs `python3 -m pytest tests/metaapi_hub -q` and `python3 -m metaapi_hub.shadow_probe`. The probe exits 0 only when three clients subscribed, `synchronize_calls` is 1, and no order method reached the broker. It prints JSON. The note in that JSON says not to cut over.

`pytest` with no arguments still uses `pytest.ini`, which points at `tests/e2e`. Those tests are not the hub suite. They expect `config_us100.json`.

## Re-run on matt-berserker

Stage 1 shadow already passed on the VM. Re-run **only the test script** after updating the checkout that produced the 24/27 result. Do not deploy this branch onto the live tree, do not `systemctl` anything, and do not start `--mode live`.

Leave `ODIN_METAAPI_HUB` and `ODIN_METAAPI_HUB_ORDERS` unset. The script unsets them itself. Python on that host is 3.9 and already has `metaapi-cloud-sdk`; the suite is written for that. It still does not call `synchronize()` on the real SDK and it does not construct a live `MetaApi` client.

```sh
cd /path/to/the/checkout/that/ran/the/tests
git pull origin cursor/metaapi-hub-230c
unset ODIN_METAAPI_HUB
unset ODIN_METAAPI_HUB_ORDERS
sh scripts/run_metaapi_hub_tests.sh
```

If that path is `/home/solveetcoagula/odin_ftmo` and the Griff units are running from it, do not checkout or pull there. Clone or copy the branch somewhere else and run the script in that copy. A pull into the live working directory is a deploy.

Expect `python 3.9.x`, pytest all passed, and `shadow probe ok 1 orders 0`. `orders_live` in the probe JSON is false.

The three failures from the 24/27 run were:

1. Python 3.9 binds `asyncio.Lock` at construction. After `asyncio.run()`, building a broker outside a loop raised "no current event loop". Locks are now created on first use. A test builds the owner after `asyncio.run()` and still expects one sync and zero orders.
2. `MetaApiBroker.synchronize` was expected to raise `SDK_MISSING`. With the SDK installed that would have opened a real client. The test now hides `metaapi_cloud_sdk` and still requires `SDK_MISSING`, a redacted token, and zero orders.
3. Off mode was expected to fail importing `MetaApiWrapper`. On the VM that import succeeds. Off mode must return the direct wrapper and must not connect; the test stubs `__init__` so `MetaApi(token)` is not called. A missing wrapper still raises and does not fall through to the hub.

## Shadow hub

```sh
python3 -m metaapi_hub --mode shadow --orders deny --socket /tmp/odin-metaapi-hub.sock
```

Defaults are already `--mode shadow --orders deny`. In another shell, with the engines you intend to rehearse (not the production units):

```sh
ODIN_METAAPI_HUB=shadow \
ODIN_METAAPI_HUB_SOCKET=/tmp/odin-metaapi-hub.sock \
python3 griff_engine_live.py --test --symbol BTCUSD
```

`--test` on `GriffLiveEngine` runs the in-process self-test. Against a shadow hub it checks account info and candles and does not place an order. The self-test then closes only that engine's client.

A shadow engine will be refused if you point it at `--mode live`. `ODIN_METAAPI_HUB=on` against a hub that can trade is Stage 4 in [CUTOVER.md](CUTOVER.md), not a test command in this section.

## Health

From any local process that can see the socket, send one JSON line:

```json
{"id":"1","method":"health","params":{}}
```

Read `synchronize_calls`, `clients`, `orders_live`, and `broker_order_calls`. See [FAILURE_MODES.md](FAILURE_MODES.md).

## Logs worth keeping

The hub logs engine subscribe and unsubscribe, sync attempts, 504 retries, and duplicate suppression. It does not log the token. If a line contains a token, stop and treat that as a defect.

## Stopping a hub process

Record the hub PID when it starts. The Stage 3 v1 canary aborted because `kill -0` from user `reemanos8422` on a `solveetcoagula` PID returns EPERM, and the script treated EPERM as "PID gone". A later `ps` check is the one that tells you the process is still there.

```sh
ps -p "$HUB_PID" -o pid,user,cmd
sudo kill "$HUB_PID"
ps -p "$HUB_PID" -o pid,user,cmd
```

If it is still listed, the Stage 3 hub needed SIGKILL after SIGTERM (the SDK write loop hung on shutdown):

```sh
sudo kill -KILL "$HUB_PID"
ps -p "$HUB_PID" -o pid,user,cmd
```

That PID is the one you wrote down. Do not substitute a name search.

- Never `kill -0` across users. EPERM is not "the process exited".
- Never `pkill -f`. A pattern match can hit an engine, a second checkout, or the wrong Python.
- Never signal a PID you did not record for this hub.

`HubServer.close` closes idle client sockets before `wait_closed`, so a normal SIGTERM should return. The SDK write loop can still hang after that. KILL stays limited to the recorded PID.

## What not to do

- Do not `systemctl enable` or `systemctl start` the shadow or live-readonly files in `deploy/examples/` as a trader. They stay on `--orders deny`.
- Do not copy those two files to `/etc/systemd/system` on `matt-berserker`.
- `deploy/examples/odin-metaapi-hub.live-orders.service.example` is the only example with `--orders live`, `--enable-live-orders`, and `ODIN_METAAPI_HUB_ORDERS=live`. Installing it is the Stage 4 cutover in [CUTOVER.md](CUTOVER.md), not a rehearsal.
- Do not pass `--orders live` or `--enable-live-orders` unless that same command also has `--mode live` and the process environment has `ODIN_METAAPI_HUB_ORDERS=live`, and the three Griff units are already stopped.
- Do not export `ODIN_METAAPI_HUB=on` on `griff_engine_btc`, `griff_engine_us100`, or `griff_engine_gold` while those processes are still the ones synchronizing. Stop them first. The unit names are those three, not `griff_engine` / `griff_engine_xau`.
- Do not commit `config_us100.json` or any other file with `metaapi.token`.
- Do not `pkill -f`, and do not use `kill -0` to decide that a hub PID has exited.
