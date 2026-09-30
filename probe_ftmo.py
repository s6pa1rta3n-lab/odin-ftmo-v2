"""Probe FTMO demo account connectivity, symbol specs, and market quotes."""

import asyncio
import json
import logging
import sys
from griff_engine_live import (
    DEFAULT_ACCOUNT_ID,
    DEFAULT_SYMBOL,
    load_metaapi_token,
    compute_atr_14,
    calculate_position_size,
    calculate_initial_stop_loss,
)
from MetaApiWrapper import MetaApiWrapper

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ProbeFTMO")


async def async_probe() -> None:
    """Connect to MetaAPI and probe account state and market specifications."""
    token = load_metaapi_token("config_us100.json")
    wrapper = MetaApiWrapper(token, DEFAULT_ACCOUNT_ID)
    logger.info("Connecting to MetaApi account %s...", DEFAULT_ACCOUNT_ID)
    await wrapper.connect()

    try:
        info = await wrapper.get_account_information()
        logger.info("Account Information: %s", json.dumps(info, indent=2))

        symbol_spec = await wrapper.connection.get_symbol_specification(DEFAULT_SYMBOL)
        logger.info("Symbol Specification: %s", json.dumps(symbol_spec, indent=2))

        price = await wrapper.connection.get_symbol_price(DEFAULT_SYMBOL)
        logger.info("Current Price: %s", json.dumps(price, indent=2))

        candles = await wrapper.account.get_historical_candles(DEFAULT_SYMBOL, "1h")
        logger.info("Retrieved %d historical 1H candles", len(candles))
        if len(candles) >= 15:
            atr = compute_atr_14(candles)
            equity = float(info.get("equity", 100000.0))
            lots = calculate_position_size(equity, atr)
            logger.info(
                "ATR_14: %.4f | Equity: $%.2f | Position Size (1%% risk): %.2f lots",
                atr,
                equity,
                lots,
            )

        positions = await wrapper.connection.get_positions()
        logger.info("Current Open Positions (%d): %s", len(positions or []), json.dumps(positions, indent=2))

        orders = await wrapper.connection.get_orders()
        logger.info("Current Pending Orders (%d): %s", len(orders or []), json.dumps(orders, indent=2))
    finally:
        if hasattr(wrapper, "streaming_connection") and wrapper.streaming_connection:
            await wrapper.streaming_connection.close()
        if hasattr(wrapper, "connection") and wrapper.connection:
            await wrapper.connection.close()


def main() -> None:
    """Execute async probe."""
    asyncio.run(async_probe())


if __name__ == "__main__":
    main()
