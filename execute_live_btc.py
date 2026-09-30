"""Execute genuine live market trade on FTMO Demo account using Griff's strategy."""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

from MetaApiWrapper import MetaApiWrapper
from griff_engine_live import (
    DEFAULT_ACCOUNT_ID,
    GRIFF_ORDER_COMMENT,
    load_metaapi_token,
    compute_atr_14,
    calculate_position_size,
    calculate_initial_stop_loss,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("GriffLiveExecution")


async def execute_trade() -> Dict[str, Any]:
    """Execute live market order on open FTMO Demo instrument with 1% risk position sizing."""
    token = load_metaapi_token("config_us100.json")
    account_id = DEFAULT_ACCOUNT_ID
    symbol = "BTCUSD"

    logger.info("Initializing MetaApiWrapper connection for account %s...", account_id)
    wrapper = MetaApiWrapper(token, account_id)
    await wrapper.connect()

    try:
        account_info = await wrapper.get_account_information()
        balance = float(account_info.get("balance", 100000.0))
        equity = float(account_info.get("equity", 100000.0))
        server = str(account_info.get("server", "FTMO-Demo"))
        login = str(account_info.get("login", "N/A"))

        logger.info(
            "Account Verified | Server: %s | Login: %s | Balance: $%.2f | Equity: $%.2f",
            server,
            login,
            balance,
            equity,
        )

        candles = await wrapper.account.get_historical_candles(symbol, "1h")
        atr_14 = compute_atr_14(candles)
        risk_pct = 0.01
        lots = calculate_position_size(
            equity=equity,
            atr_14=atr_14,
            tick_value=1.0,
            contract_size=1.0,
            risk_pct=risk_pct,
            max_lot=5.0,
        )

        price_obj = await wrapper.connection.get_symbol_price(symbol)
        ask = float(price_obj["ask"])
        bid = float(price_obj["bid"])
        direction = "BUY"
        initial_sl = calculate_initial_stop_loss(direction, ask, atr_14)

        logger.info(
            "Routing Live Trade | Symbol: %s | Action: %s | Lots: %.2f | Ask: %.2f | SL: %.2f | 14-ATR: %.2f",
            symbol,
            direction,
            lots,
            ask,
            initial_sl,
            atr_14,
        )

        opts = {"comment": GRIFF_ORDER_COMMENT}
        order_res = await wrapper.connection.create_market_buy_order(
            symbol,
            lots,
            stop_loss=initial_sl,
            options=opts,
        )

        logger.info("Broker Response: %s", json.dumps(order_res, indent=2, default=str))

        await asyncio.sleep(2.0)
        terminal_positions = await wrapper.connection.get_positions()
        matched_pos = None
        for p in (terminal_positions or []):
            if str(p.get("id")) == str(order_res.get("orderId")) or str(p.get("positionId")) == str(order_res.get("positionId")) or (p.get("symbol") == symbol and str(p.get("comment", "")).startswith("GRIFF_")):
                matched_pos = p
                break

        logger.info("Matched Live Terminal Position: %s", json.dumps(matched_pos, indent=2, default=str))

        receipt = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "accountId": account_id,
            "server": server,
            "login": login,
            "balance": balance,
            "equity": equity,
            "symbol": symbol,
            "direction": direction,
            "volume": lots,
            "requestedPrice": ask,
            "stopLoss": initial_sl,
            "atr_14": atr_14,
            "orderId": order_res.get("orderId"),
            "numericCode": order_res.get("numericCode"),
            "stringCode": order_res.get("stringCode"),
            "brokerResponse": order_res,
            "terminalPosition": matched_pos,
        }

        with open("live_execution_receipt.json", "w", encoding="utf-8") as f:
            json.dump(receipt, f, indent=2, default=str)

        return receipt

    finally:
        if hasattr(wrapper, "streaming_connection") and wrapper.streaming_connection:
            await wrapper.streaming_connection.close()
        if hasattr(wrapper, "connection") and wrapper.connection:
            await wrapper.connection.close()


def main() -> None:
    """Synchronous entrypoint."""
    receipt = asyncio.run(execute_trade())
    print("\n================ LIVE EXECUTION CONFIRMATION ================")
    print(f"Order ID: {receipt.get('orderId')}")
    print(f"Numeric Code: {receipt.get('numericCode')} ({receipt.get('stringCode')})")
    print(f"Symbol: {receipt.get('symbol')} | Direction: {receipt.get('direction')} | Lots: {receipt.get('volume')}")
    print(f"14-Period ATR: {receipt.get('atr_14')} | Stop Loss: {receipt.get('stopLoss')}")
    pos = receipt.get("terminalPosition")
    if pos:
        print(f"MT5 Terminal Position Ticket: {pos.get('id')} | Open Price: {pos.get('openPrice')} | Current SL: {pos.get('stopLoss')}")
    print("=============================================================")


if __name__ == "__main__":
    main()
