# FTMO crawl-back (EURUSD Asia)

Survival book ordered by Odin 2026-10-07. See `DESIGN.md` and `FLATTEN-EVIDENCE.json`.

## VM install

```bash
sudo mkdir -p /home/solveetcoagula/ftmo-crawlback
sudo cp crawlback_eurusd_asia.py DESIGN.md FLATTEN-EVIDENCE.json README.md \
  /home/solveetcoagula/ftmo-crawlback/
sudo cp crawlback-eurusd-asia.service /etc/systemd/system/
sudo chown -R solveetcoagula:solveetcoagula /home/solveetcoagula/ftmo-crawlback
sudo systemctl daemon-reload
# leave disabled until arm:
# sudo systemctl enable --now crawlback-eurusd-asia.service
# To arm: set Environment=CRAWL_ARMED=1 in the unit or drop-in, then restart.
```

Default is **disarmed** (`CRAWL_ARMED=0`).
