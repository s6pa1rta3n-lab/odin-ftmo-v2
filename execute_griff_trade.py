"""Execute genuine live trade on FTMO Demo account via MetaAPI."""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from MetaApiWrapper import MetaApiWrapper
from griff_engine_live import (
    DEFAULT_ACCOUNT_ID,
    DEFAULT_SYMBOL,
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


async def run_live_execution() -> Dict[str, Any]:
    """Connect to MetaAPI, calculate ATR and 1% risk size, and route live trade."""
    token = load_metaapi_token("config_us100.json")
    account_id = DEFAULT_ACCOUNT_ID
    symbol = DEFAULT_SYMBOL

    logger.info("Initializing connection to MetaAPI account %s...", account_id)
    wrapper = MetaApiWrapper(token, account_id)
    await wrapper.connect()

    try:
        account_info = await wrapper.get_account_information()
        balance = float(account_info.get("balance", 100000.0))
        equity = float(account_info.get("equity", 100000.0))
        server = account_info.get("server", "FTMO-Demo")
        login = account_info.get("login", "N/A")

        logger.info(
            "Account Verified | Server: %s | Login: %s | Balance: $%.2f | Equity: $%.2f",
            server,
            login,
            balance,
            equity,
        )

        candles = await wrapper.account.get_historical_candles(symbol, "1h")
        if len(candles) < 15:
            raise RuntimeError(f"Insufficient completed 1H candles: {len(candles)}")

        atr_14 = compute_atr_14(candles)
        risk_pct = 0.01
        lots = calculate_position_size(
            equity=equity,
            atr_14=atr_14,
            tick_value=1.0,
            contract_size=1.0,
            risk_pct=risk_pct,
        )

        logger.info(
            "Strategy Calculations | 14-Period ATR: %.2f | Equity: $%.2f | 1%% Risk: $%.2f | Sizing: %.2f lots",
            atr_14,
            equity,
            equity * risk_pct,
            lots,
        )

        price_obj = await wrapper.connection.get_symbol_price(symbol)
        ask_price = float(price_obj["ask"])
        bid_price = float(price_obj["bid"])
        logger.info("Live Quotes for %s | Bid: %.2f | Ask: %.2f", symbol, bid_price, ask_price)

        direction = "BUY"
        entry_price = ask_price
        initial_sl = calculate_initial_stop_loss(direction, entry_price, atr_14)

        logger.info(
            "Routing Live Trade | Action: %s | Lots: %.2f | Price: %.2f | Initial SL: %.2f | Comment: %s",
            direction,
            lots,
            entry_price,
            initial_sl,
            GRIFF_ORDER_COMMENT,
        )

        options = {"comment": GRIFF_ORDER_COMMENT}
        order_result = await wrapper.connection.create_market_buy_order(
            symbol,
            lots,
            stop_loss=initial_sl,
            options=options,
        )

        logger.info("Broker Response Received: %s", json.dumps(order_result, indent=2, default=str))

        order_id = str(order_result.get("orderId", ""))
        numeric_code = order_result.get("numericCode", 0)
        string_code = order_result.get("stringCode", "")
        position_id = str(order_result.get("positionId", order_id))

        await asyncio.sleep(2.0)

        terminal_positions = await wrapper.connection.get_positions()
        matching_position = None
        for pos in (terminal_positions or []):
            if str(pos.get("id")) in (order_id, position_id) or str(pos.get("positionId")) in (order_id, position_id):
                matching_position = pos
                break
            if pos.get("symbol") == symbol and str(pos.get("comment", "")).startswith("GRIFF_"):
                matching_position = pos
                break

        logger.info("Terminal Position State: %s", json.dumps(matching_position, indent=2, default=str))

        terminal_orders = await wrapper.connection.get_orders()
        logger.info("Terminal Orders Count: %d", len(terminal_orders or []))

        receipt = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "accountId": account_id,
            "server": server,
            "login": login,
            "startingBalance": balance,
            "equity": equity,
            "atr_14": atr_14,
            "riskPct": risk_pct,
            "riskDollars": equity * risk_pct,
            "symbol": symbol,
            "direction": direction,
            "volume": lots,
            "requestedPrice": entry_price,
            "stopLoss": initial_sl,
            "comment": GRIFF_ORDER_COMMENT,
            "brokerResponse": order_result,
            "orderId": order_id,
            "positionId": position_id,
            "numericCode": numeric_code,
            "stringCode": string_code,
            "terminalPosition": matching_position,
        }

        with open("live_execution_receipt.json", "w", encoding="utf-8") as f:
            json.dump(receipt, f, indent=2, default=str)

        logger.info("Live execution receipt saved to live_execution_receipt.json")
        return receipt

    finally:
        if hasattr(wrapper, "streaming_connection") and wrapper.streaming_connection:
            await wrapper.streaming_connection.close()
        if hasattr(wrapper, "connection") and wrapper.connection:
            await wrapper.connection.close()


def main() -> None:
    """Entrypoint for live execution script."""
    receipt = asyncio.run(run_live_execution())
    print("\n--- LIVE TRADE EXECUTION SUMMARY ---")
    print(f"Broker Order ID: {receipt.get('orderId')}")
    print(f"Position ID: {receipt.get('positionId')}")
    print(f"Broker Return Code: {receipt.get('numericCode')} ({receipt.get('stringCode')})")
    print(f"Symbol: {receipt.get('symbol')} | Direction: {receipt.get('direction')} | Volume: {receipt.get('volume')} lots")
    print(f"14-Period ATR: {receipt.get('atr_14')} | Stop Loss: {receipt.get('stopLoss')}")
    if receipt.get("terminalPosition"):
        pos = receipt["terminalPosition"]
        print(f"Confirmed MT5 Terminal Position: Ticket {pos.get('id')} | Open Price {pos.get('openPrice')} | Current SL {pos.get('stopLoss')}")


if __name__ == "__main__":
    main()
