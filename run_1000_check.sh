#!/bin/bash
python3 monitor_griff.py

echo "--- DAEMON LOGS FOR 10:00 CLOSE ---"
CLOUDSDK_METRICS_ENVIRONMENT=datacloud.antigravity gcloud compute ssh matt-berserker --zone=us-central1-a --project=project-45c3b27c-b597-4704-a50 --account=reemanos8422@gmail.com --command="sudo journalctl -u griff_engine_xau.service -u griff_engine.service -u griff_engine_btc.service --since '2026-09-17 09:59:45' --no-pager | grep -iE 'Inside Bar Detected|Setup:|Trailing stop'"
