#!/usr/bin/env python3
"""EURUSD Asian-session mean-reversion crawl-back (FTMO survival).

Comment: CRAWLBACK_EURUSD_ASIA
Arm only when CRAWL_ARMED=1. Flattens at session end (00:00 America/New_York).
"""
from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

ACCOUNT_ID = os.environ.get("CRAWL_ACCOUNT_ID", "a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf")
SYMBOL = os.environ.get("CRAWL_SYMBOL", "EURUSD")
COMMENT = "CRAWLBACK_EURUSD_ASIA"
CLIENT_HOST = "https://mt-client-api-v1.london.agiliumtrade.ai"
MARKET_HOST = "https://mt-market-data-client-api-v1.london.agiliumtrade.ai"
TOKEN_SOURCE = Path(os.environ.get("CRAWL_TOKEN_SOURCE", "/home/solveetcoagula/odin_ftmo/config_us100.json"))
LOG_PATH = Path(os.environ.get("CRAWL_LOG_PATH", "/home/solveetcoagula/ftmo-crawlback/crawlback.log"))
STATE_PATH = Path(os.environ.get("CRAWL_STATE_PATH", "/home/solveetcoagula/ftmo-crawlback/crawl_state.json"))

ET = ZoneInfo("America/New_York")
UTC = timezone.utc

CRAWL_ARMED = os.environ.get("CRAWL_ARMED", "0").strip() == "1"
CRAWL_KILL = os.environ.get("CRAWL_KILL", "0").strip() == "1"

FAIL_EQUITY = Decimal(os.environ.get("CRAWL_FAIL_EQUITY", "90000"))
TARGET_EQUITY = Decimal(os.environ.get("CRAWL_TARGET_EQUITY", "95000"))
RISK_MIN = Decimal(os.environ.get("CRAWL_RISK_MIN", "100"))
RISK_MAX = Decimal(os.environ.get("CRAWL_RISK_MAX", "150"))
SL_PIPS = Decimal(os.environ.get("CRAWL_SL_PIPS", "6"))
RR = Decimal(os.environ.get("CRAWL_RR", "1.2"))  # 1.0–1.5
LOT_CAP = Decimal(os.environ.get("CRAWL_LOT_CAP", "2.0"))
LOT_STEP = Decimal(os.environ.get("CRAWL_LOT_STEP", "0.01"))
# Fallback pip $/lot for EURUSD on USD account; overridden by symbol tick if available.
PIP_VALUE_PER_LOT = Decimal(os.environ.get("CRAWL_PIP_VALUE_PER_LOT", "10"))
PIP_SIZE = Decimal(os.environ.get("CRAWL_PIP_SIZE", "0.0001"))

SESSION_START_HOUR = int(os.environ.get("CRAWL_SESSION_START_HOUR", "18"))  # 6 PM ET
SESSION_END_HOUR = int(os.environ.get("CRAWL_SESSION_END_HOUR", "0"))  # midnight ET
RANGE_BARS = int(os.environ.get("CRAWL_RANGE_BARS", "8"))  # short evening box on 15m
WICK_FRAC = Decimal(os.environ.get("CRAWL_WICK_FRAC", "0.35"))
MAX_OPEN = 1
POLL_SEC = float(os.environ.get("CRAWL_POLL_SEC", "20"))


def load_token() -> str:
    cfg = json.loads(TOKEN_SOURCE.read_text(encoding="utf-8"))
    value = cfg.get("metaapi", {}).get("token", "")
    if not value:
        raise RuntimeError("metaapi token missing")
    return value


def api_request(host: str, method: str, path: str, token: str, body: dict | None = None, timeout: float = 90.0):
    url = f"{host}{path}"
    data = None
    headers = {"auth-token": token, "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {err_body}") from exc


def client(method: str, path: str, token: str, body: dict | None = None, timeout: float = 90.0):
    return api_request(CLIENT_HOST, method, path, token, body, timeout)


def market(method: str, path: str, token: str, timeout: float = 90.0):
    return api_request(MARKET_HOST, method, path, token, None, timeout)


def log(event: dict) -> None:
    event = dict(event)
    event["loggedAt"] = datetime.now(ET).isoformat()
    line = json.dumps(event, default=str)
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def q_lots(x: Decimal) -> float:
    stepped = (x / LOT_STEP).to_integral_value(rounding=ROUND_DOWN) * LOT_STEP
    if stepped < LOT_STEP:
        return 0.0
    return float(stepped)


def risk_dollars(equity: Decimal) -> Decimal:
    span = TARGET_EQUITY - FAIL_EQUITY
    if span <= 0:
        return RISK_MIN
    t = (equity - FAIL_EQUITY) / span
    if t < 0:
        t = Decimal("0")
    if t > 1:
        t = Decimal("1")
    r = RISK_MIN + (RISK_MAX - RISK_MIN) * t
    if r < RISK_MIN:
        r = RISK_MIN
    if r > RISK_MAX:
        r = RISK_MAX
    return r.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def lots_for_risk(risk: Decimal) -> float:
    denom = SL_PIPS * PIP_VALUE_PER_LOT
    if denom <= 0:
        return 0.0
    raw = risk / denom
    if raw > LOT_CAP:
        raw = LOT_CAP
    return q_lots(raw)


def in_session(now: datetime | None = None) -> bool:
    now = now or datetime.now(ET)
    h = now.hour
    # 18:00 inclusive through 23:59; end at 00:00 (exclusive of morning)
    if SESSION_END_HOUR == 0:
        return h >= SESSION_START_HOUR
    if SESSION_START_HOUR < SESSION_END_HOUR:
        return SESSION_START_HOUR <= h < SESSION_END_HOUR
    return h >= SESSION_START_HOUR or h < SESSION_END_HOUR


def account_information(token: str) -> dict:
    return client("GET", f"/users/current/accounts/{ACCOUNT_ID}/account-information", token)


def positions(token: str) -> list:
    pos = client("GET", f"/users/current/accounts/{ACCOUNT_ID}/positions", token)
    return pos if isinstance(pos, list) else []


def crawl_positions(token: str) -> list:
    return [p for p in positions(token) if (p.get("comment") or "") == COMMENT or (p.get("symbol") or "").startswith("EUR")]


def close_position(token: str, position_id: str) -> dict:
    return client(
        "POST",
        f"/users/current/accounts/{ACCOUNT_ID}/trade",
        token,
        {"actionType": "POSITION_CLOSE_ID", "positionId": str(position_id)},
        timeout=120,
    )


def cancel_orders(token: str) -> None:
    orders = client("GET", f"/users/current/accounts/{ACCOUNT_ID}/orders", token)
    for o in orders if isinstance(orders, list) else []:
        try:
            client(
                "POST",
                f"/users/current/accounts/{ACCOUNT_ID}/trade",
                token,
                {"actionType": "ORDER_CANCEL", "orderId": str(o.get("id"))},
            )
            log({"event": "order_cancelled", "orderId": o.get("id")})
        except Exception as exc:
            log({"event": "order_cancel_fail", "orderId": o.get("id"), "error": str(exc)[:300]})


def flatten_crawl(token: str, reason: str) -> None:
    for p in crawl_positions(token):
        try:
            res = close_position(token, str(p.get("id")))
            log({"event": "flatten_close", "reason": reason, "id": p.get("id"), "code": res.get("stringCode")})
        except Exception as exc:
            log({"event": "flatten_fail", "id": p.get("id"), "error": str(exc)[:300]})
    cancel_orders(token)


def fetch_candles_15m(token: str, bars: int = 40) -> list:
    # recent-first or oldest-first — normalize to oldest→newest
    end = datetime.now(UTC)
    start = end - timedelta(hours=bars)
    path = (
        f"/users/current/accounts/{ACCOUNT_ID}/historical-market-data/symbols/{SYMBOL}/timeframes/M15/candles"
        f"?startTime={urllib.parse.quote(start.isoformat().replace('+00:00', 'Z'))}"
        f"&limit={bars}"
    )
    raw = market("GET", path, token)
    candles = raw if isinstance(raw, list) else raw.get("candles") or raw.get("data") or []
    def key(c):
        return c.get("time") or c.get("timestamp") or ""
    candles = sorted(candles, key=key)
    return candles[-bars:]


def mid_price(c: dict) -> Decimal:
    o = Decimal(str(c.get("open") or c.get("o")))
    h = Decimal(str(c.get("high") or c.get("h")))
    l = Decimal(str(c.get("low") or c.get("l")))
    cl = Decimal(str(c.get("close") or c.get("c")))
    return (o + h + l + cl) / 4


def signal_from_candles(candles: list) -> tuple[str | None, dict]:
    """Return ('BUY'|'SELL'|None, meta). Fade exhaustion at range extreme toward mid."""
    if len(candles) < RANGE_BARS + 2:
        return None, {"reason": "not_enough_bars", "n": len(candles)}
    window = candles[-(RANGE_BARS + 1) : -1]  # completed bars forming the box
    last = candles[-1]
    hi = max(Decimal(str(c.get("high") or c.get("h"))) for c in window)
    lo = min(Decimal(str(c.get("low") or c.get("l"))) for c in window)
    mid = sum(mid_price(c) for c in window) / len(window)
    lh = Decimal(str(last.get("high") or last.get("h")))
    ll = Decimal(str(last.get("low") or last.get("l")))
    lo_ = Decimal(str(last.get("open") or last.get("o")))
    lc = Decimal(str(last.get("close") or last.get("c")))
    rng = lh - ll
    if rng <= 0:
        return None, {"reason": "flat_bar"}
    upper_wick = lh - max(lo_, lc)
    lower_wick = min(lo_, lc) - ll
    meta = {
        "boxHigh": float(hi),
        "boxLow": float(lo),
        "boxMid": float(mid),
        "lastClose": float(lc),
        "upperWick": float(upper_wick),
        "lowerWick": float(lower_wick),
    }
    # Sell fade: tag high, upper wick exhaustion, close back inside
    if lh >= hi and upper_wick / rng >= WICK_FRAC and lc < hi and lc > mid:
        return "SELL", meta
    # Buy fade: tag low, lower wick exhaustion, close back inside
    if ll <= lo and lower_wick / rng >= WICK_FRAC and lc > lo and lc < mid:
        return "BUY", meta
    return None, {**meta, "reason": "no_exhaustion"}


def place_market(token: str, side: str, volume: float, sl: float, tp: float) -> dict:
    action = "ORDER_TYPE_BUY" if side == "BUY" else "ORDER_TYPE_SELL"
    payload = {
        "actionType": action,
        "symbol": SYMBOL,
        "volume": float(volume),
        "stopLoss": float(sl),
        "takeProfit": float(tp),
        "comment": COMMENT,
    }
    return client("POST", f"/users/current/accounts/{ACCOUNT_ID}/trade", token, payload, timeout=120)


def levels_for(side: str, price: Decimal) -> tuple[float, float]:
    sl_dist = SL_PIPS * PIP_SIZE
    tp_dist = sl_dist * RR
    if side == "BUY":
        return float(price - sl_dist), float(price + tp_dist)
    return float(price + sl_dist), float(price - tp_dist)


def current_price(token: str) -> Decimal:
    raw = client("GET", f"/users/current/accounts/{ACCOUNT_ID}/symbols/{SYMBOL}/current-price", token)
    bid = Decimal(str(raw.get("bid") or raw.get("price") or raw.get("ask")))
    ask = Decimal(str(raw.get("ask") or bid))
    return (bid + ask) / 2


def once(token: str) -> None:
    now = datetime.now(ET)
    if CRAWL_KILL or not CRAWL_ARMED:
        log({"event": "disarmed", "armed": CRAWL_ARMED, "kill": CRAWL_KILL})
        return
    info = account_information(token)
    equity = Decimal(str(info.get("equity")))
    if equity <= FAIL_EQUITY:
        log({"event": "halt_at_fail_equity", "equity": float(equity)})
        flatten_crawl(token, "fail_equity")
        return
    open_crawl = crawl_positions(token)
    if not in_session(now):
        if open_crawl:
            flatten_crawl(token, "session_end")
        log({"event": "out_of_session", "hour": now.hour, "openCrawl": len(open_crawl)})
        return
    if len(open_crawl) >= MAX_OPEN:
        log({"event": "max_open", "n": len(open_crawl)})
        return
    risk = risk_dollars(equity)
    lots = lots_for_risk(risk)
    if lots <= 0:
        log({"event": "lots_zero", "risk": float(risk), "equity": float(equity)})
        return
    try:
        candles = fetch_candles_15m(token)
    except Exception as exc:
        log({"event": "candles_fail", "error": str(exc)[:400]})
        return
    side, meta = signal_from_candles(candles)
    if not side:
        log({"event": "no_signal", **meta})
        return
    px = current_price(token)
    sl, tp = levels_for(side, px)
    try:
        res = place_market(token, side, lots, sl, tp)
        log(
            {
                "event": "entry",
                "side": side,
                "lots": lots,
                "risk": float(risk),
                "equity": float(equity),
                "sl": sl,
                "tp": tp,
                "price": float(px),
                "code": res.get("stringCode"),
                "orderId": res.get("orderId") or res.get("positionId"),
                **meta,
            }
        )
    except Exception as exc:
        log({"event": "entry_fail", "side": side, "error": str(exc)[:400]})


def main() -> None:
    log({"event": "start", "armed": CRAWL_ARMED, "symbol": SYMBOL, "comment": COMMENT})
    token = load_token()
    while True:
        try:
            once(token)
        except Exception as exc:
            log({"event": "loop_error", "error": str(exc)[:500]})
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
