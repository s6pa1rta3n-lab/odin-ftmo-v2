# Trailing Stop Hotfix & Duplicate Resolution
- Engine was patched to utilize a local `self.highest_sl_memory` to remember high-water mark trailing stops in the event of `MetaApi` connection timeouts.
- A duplicate US100 breakout position and order were triggered due to `TooManyRequestsError` masking active positions upon engine initialization.
- The duplicate position and pending order were successfully cleared.
- Both the `griff_engine.service` (US100) and `griff_engine_btc.service` (BTCUSD) daemons have been restarted on the VM and are active.
