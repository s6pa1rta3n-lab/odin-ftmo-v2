# Runbook

Do not run the live hub on `matt-berserker` as part of reviewing this branch. Shadow mode is local and does not open a MetaAPI connection.

## Tests

```sh
sh scripts/run_metaapi_hub_tests.sh
```

That runs `python3 -m pytest tests/metaapi_hub -q` and `python3 -m metaapi_hub.shadow_probe`. The probe exits 0 only when three clients subscribed, `synchronize_calls` is 1, and no order method reached the broker. It prints JSON. The note in that JSON says not to cut over.

`pytest` with no arguments still uses `pytest.ini`, which points at `tests/e2e`. Those tests are not the hub suite. They expect `config_us100.json` and the SDK, which this checkout does not have.

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

A shadow engine will be refused if you point it at `--mode live`. Use `ODIN_METAAPI_HUB=on` only after the cutover checklist, and only against a hub whose orders are still `deny`.

## Health

From any local process that can see the socket, send one JSON line:

```json
{"id":"1","method":"health","params":{}}
```

Read `synchronize_calls`, `clients`, `orders_live`, and `broker_order_calls`. See [FAILURE_MODES.md](FAILURE_MODES.md).

## Logs worth keeping

The hub logs engine subscribe and unsubscribe, sync attempts, 504 retries, and duplicate suppression. It does not log the token. If a line contains a token, stop and treat that as a defect.

## What not to do

- Do not `systemctl enable` or `systemctl start` the files in `deploy/examples/`.
- Do not copy those files to `/etc/systemd/system` on `matt-berserker`.
- Do not pass `--orders live` or `--enable-live-orders`.
- Do not export `ODIN_METAAPI_HUB=on` on the three Griff units while they are still the processes that synchronize.
- Do not commit `config_us100.json` or any other file with `metaapi.token`.
