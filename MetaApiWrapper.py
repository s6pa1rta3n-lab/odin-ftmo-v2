import asyncio
import logging
from metaapi_cloud_sdk import MetaApi
from metaapi_cloud_sdk.clients.metaapi.synchronization_listener import SynchronizationListener
try:
    from metaapi_cloud_sdk.clients.timeout_exception import TimeoutException
except ImportError:
    class TimeoutException(Exception):
        pass

class MetaApiPriceListener(SynchronizationListener):
    def __init__(self):
        super().__init__()
        self.prices = {}

    async def on_symbol_price_updated(self, instance_index, price):
        self.prices[price['symbol']] = price

    async def on_symbol_prices_updated(self, instance_index, prices, equity=None, margin=None, free_margin=None, margin_level=None, account_currency_exchange_rate=None):
        for p in prices:
            self.prices[p['symbol']] = p

log = logging.getLogger("MetaApiWrapper")

class MetaApiWrapper:
    """
    A flawless execution bridge translating Binance-style payloads into MetaApi MT5 commands.
    This ensures odin2.py and odin4.py can run their complex logic untouched.
    """
    def __init__(self, token, account_id):
        self.token = token
        self.api = MetaApi(token)
        self.account_id = account_id
        self.connection = None
        self.account = None
        self.price_listener = MetaApiPriceListener()
        self.contract_sizes = {
            "BTCUSD": 1.0,
            "ADAUSD": 100000.0
        }

    async def get_positions(self):
        """Retrieve open positions checking streaming terminal state first with REST fallback.

        Returns:
            List of open positions or None on failure.
        """
        if hasattr(self, "streaming_connection") and self.streaming_connection:
            try:
                state = getattr(self.streaming_connection, "terminal_state", None)
                if state and getattr(state, "connected", False):
                    positions = getattr(state, "positions", None)
                    if positions is not None:
                        return positions
            except Exception as e:
                log.warning(f"Streaming connection positions unavailable: {e}. Falling back to REST.")
                await asyncio.sleep(1.0)
        return await self.get_positions_rest()

    async def get_account_information(self):
        """Retrieve account information checking streaming terminal state first with REST fallback.

        Returns:
            Account information dictionary or empty dict on failure.
        """
        if hasattr(self, "streaming_connection") and self.streaming_connection:
            try:
                state = getattr(self.streaming_connection, "terminal_state", None)
                if state and getattr(state, "connected", False):
                    info = getattr(state, "account_information", None)
                    if info:
                        return info
            except Exception as e:
                log.warning(f"Streaming connection account info unavailable: {e}. Falling back to REST.")
                await asyncio.sleep(1.0)
        return await self.get_account_information_rest()

    async def get_orders_rest(self):
        """Fetch pending orders via RPC connection with timeout handling and error recovery.

        Returns:
            List of pending orders or None on failure.
        """
        if not self.connection:
            log.error("RPC connection unavailable for get_orders_rest.")
            return None
        try:
            return await asyncio.wait_for(self.connection.get_orders(), timeout=10.0)
        except TimeoutException as e:
            log.error(f"MetaApi TimeoutException in get_orders_rest: {e}")
            return None
        except asyncio.TimeoutError:
            log.error("Asyncio TimeoutError in get_orders_rest after 10.0s.")
            return None
        except Exception as e:
            log.error(f"Error in get_orders_rest: {e}")
            return None

    async def get_positions_rest(self):
        """Fetch positions via RPC connection with timeout handling and error recovery.

        Returns:
            List of MT5 positions or None on failure.
        """
        if not self.connection:
            log.error("RPC connection unavailable for get_positions_rest.")
            return None
        try:
            return await asyncio.wait_for(self.connection.get_positions(), timeout=10.0)
        except TimeoutException as e:
            log.error(f"MetaApi TimeoutException in get_positions_rest: {e}")
            return None
        except asyncio.TimeoutError:
            log.error("Asyncio TimeoutError in get_positions_rest after 10.0s.")
            return None
        except Exception as e:
            log.error(f"Error in get_positions_rest: {e}")
            return None

    async def get_account_information_rest(self):
        """Fetch account information via RPC connection with timeout handling and error recovery.

        Returns:
            Account information dictionary or empty dict on failure.
        """
        if not self.connection:
            log.error("RPC connection unavailable for get_account_information_rest.")
            return {}
        try:
            return await asyncio.wait_for(self.connection.get_account_information(), timeout=10.0)
        except TimeoutException as e:
            log.error(f"MetaApi TimeoutException in get_account_information_rest: {e}")
            return {}
        except asyncio.TimeoutError:
            log.error("Asyncio TimeoutError in get_account_information_rest after 10.0s.")
            return {}
        except Exception as e:
            log.error(f"Error in get_account_information_rest: {e}")
            return {}

    def _to_mt5(self, sym):
        if not sym: return None
        if sym == "DOTUSDT": return "DOTUSD"
        return sym.replace("USDT", "USD")

    def _to_binance(self, sym):
        if not sym: return None
        if sym == "DOTUSD": return "DOTUSDT"
        return sym.replace("USD", "USDT")

    def get_contract_size(self, symbol):
        return self.contract_sizes.get(symbol.replace(".sim", ""), 1.0)

    async def connect(self):
        log.info(f"Connecting to MetaApi for account {self.account_id}...")
        self.account = await self.api.metatrader_account_api.get_account(self.account_id)
        self.connection = self.account.get_rpc_connection()
        self.streaming_connection = self.account.get_streaming_connection()
        self.streaming_connection.add_synchronization_listener(self.price_listener)
        await self.streaming_connection.connect()
        await self.connection.connect()
        try:
            await asyncio.wait_for(self.streaming_connection.wait_synchronized(), timeout=60.0)
            log.info("MetaApi connection synchronized successfully.")
        except Exception as e:
            log.warning(f"Streaming connection synchronization timed out or failed: {e}. Proceeding in REST fallback mode.")

    async def get_binance_formatted_balance(self):
        """Return account state mimicking Binance /fapi/v3/balance.

        Returns:
            List containing balance mapping dictionary.
        """
        if not self.connection:
            return []
        info = await self.get_account_information()
        balance_val = float(info.get('balance', 0.0)) if info else 0.0
        equity_val = float(info.get('equity', 0.0)) if info else 0.0
        free_margin_val = float(info.get('freeMargin', 0.0)) if info else 0.0
        return [{
            "asset": "USD",
            "balance": str(balance_val),
            "crossUnPnl": str(equity_val - balance_val),
            "availableBalance": str(free_margin_val)
        }]

    async def get_binance_formatted_positions(self):
        """Return MT5 positions mapped to Binance /fapi/v3/positionRisk.

        Returns:
            List of Binance-formatted position dictionaries.
        """
        if not self.connection:
            return []
        mt5_positions = await self.get_positions()
        if not mt5_positions:
            return []
        binance_positions = []
        
        aggregated = {}
        for p in mt5_positions:
            sym = p['symbol']
            side = "LONG" if p['type'] == 'POSITION_TYPE_BUY' else "SHORT"
            key = f"{sym}_{side}"
            
            if key not in aggregated:
                aggregated[key] = {
                    "symbol": sym,
                    "positionSide": side,
                    "positionAmt": 0.0,
                    "unRealizedProfit": 0.0,
                    "notional": 0.0
                }
            
            c_size = self.get_contract_size(sym)
            amt = (p['volume'] * c_size) if side == "LONG" else -(p['volume'] * c_size)
            aggregated[key]["positionAmt"] += amt
            aggregated[key]["unRealizedProfit"] += p.get('unrealizedProfit', 0.0)
            aggregated[key]["notional"] += (p.get('volume', 0) * c_size * p.get('openPrice', 0))

        for k, v in aggregated.items():
            qty = v["positionAmt"]
            notional = v["notional"]
            entry = abs(notional / qty) if qty != 0 else 0.0
            
            binance_positions.append({
                "symbol": self._to_binance(v["symbol"]),
                "positionSide": v["positionSide"],
                "positionAmt": str(qty),
                "entryPrice": str(entry),
                "unRealizedProfit": str(v["unRealizedProfit"])
            })
            
        return binance_positions

    async def get_binance_formatted_open_orders(self, symbol=None):
        """Returns MT5 pending orders mapped to Binance /fapi/v3/openOrders"""
        if not self.connection or not self.streaming_connection: return []
        mt5_orders = self.streaming_connection.terminal_state.orders
        binance_orders = []
        
        target_mt5_symbol = self._to_mt5(symbol)
        
        for o in mt5_orders:
            if target_mt5_symbol and o['symbol'] != target_mt5_symbol: continue
            
            b_side = "LONG" if 'BUY' in o['type'] else "SHORT"
            reduce_only = False
            
            c_size = self.get_contract_size(o['symbol'])
            binance_orders.append({
                "symbol": self._to_binance(o['symbol']),
                "orderId": str(o['id']),
                "clientOrderId": o.get('clientId', str(o['id'])),
                "positionSide": b_side,
                "side": "BUY" if b_side == "LONG" else "SELL",
                "type": "LIMIT",
                "reduceOnly": reduce_only,
                "price": str(o.get('openPrice', 0)),
                "origQty": str(o.get('volume', 0) * c_size)
            })
        return binance_orders

    async def route_order(self, order_dict):
        """Translates a Binance order payload into a MetaApi execution call."""
        sym = self._to_mt5(order_dict["symbol"])
        c_size = self.get_contract_size(sym)
        raw_qty = float(order_dict["quantity"]) / c_size
        qty = round(raw_qty, 2)
        
        if qty < 0.01:
            return {"status": "REJECTED", "code": -1, "msg": f"Invalid volume in the request: {qty} lots (< 0.01) [Coins: {order_dict['quantity']}]"}
            
        o_type = order_dict["type"]
        side = order_dict["side"]
        
        action = "ORDER_TYPE_BUY" if side == "BUY" else "ORDER_TYPE_SELL"
        
        try:
            if o_type == "MARKET":
                sl = float(order_dict.get("stopLoss", 0))
                tp = float(order_dict.get("takeProfit", 0))
                if sl: sl = round(sl, 3)
                if tp: tp = round(tp, 3)
                
                if sl == 0:
                    current_p = await self.get_symbol_price(sym)
                    if current_p:
                        price = current_p["askPrice"] if side == "BUY" else current_p["bidPrice"]
                        sl = round(price * 0.975 if side == "BUY" else price * 1.025, 3)

                opts = {"comment": order_dict["newClientOrderId"]} if "newClientOrderId" in order_dict else {}
                    
                if side == "BUY":
                    res = await self.connection.create_market_buy_order(sym, qty, stop_loss=sl if sl else None, take_profit=tp if tp else None, options=opts)
                else:
                    res = await self.connection.create_market_sell_order(sym, qty, stop_loss=sl if sl else None, take_profit=tp if tp else None, options=opts)
                    
                return {"status": "FILLED", "orderId": res.get("orderId"), "msg": "success"}
            elif o_type == "STOP":
                price = float(order_dict["stopPrice"])
                opts = {"comment": order_dict["newClientOrderId"]} if "newClientOrderId" in order_dict else {}
                
                sl = float(order_dict.get("stopLoss", 0))
                tp = float(order_dict.get("takeProfit", 0))
                
                if sl == 0:
                    sl = round(price * 0.975 if side == "BUY" else price * 1.025, 3)
                    
                if side == "BUY":
                    res = await self.connection.create_stop_buy_order(sym, qty, price, stop_loss=sl if sl else None, take_profit=tp if tp else None, options=opts)
                else:
                    res = await self.connection.create_stop_sell_order(sym, qty, price, stop_loss=sl if sl else None, take_profit=tp if tp else None, options=opts)
                    
                return {"status": "NEW", "orderId": res.get("orderId"), "msg": "success"}
            elif o_type == "LIMIT":
                price = float(order_dict["price"])
                opts = {"comment": order_dict["newClientOrderId"]} if "newClientOrderId" in order_dict else {}
                
                sl = float(order_dict.get("stopLoss", 0))
                tp = float(order_dict.get("takeProfit", 0))
                
                if sl == 0:
                    sl = round(price * 0.975 if side == "BUY" else price * 1.025, 3)

                if side == "BUY":
                    res = await self.connection.create_limit_buy_order(sym, qty, price, stop_loss=sl, take_profit=tp if tp else None, options=opts)
                else:
                    res = await self.connection.create_limit_sell_order(sym, qty, price, stop_loss=sl, take_profit=tp if tp else None, options=opts)
                return {"status": "NEW", "orderId": res.get("orderId"), "msg": "success"}
        except Exception as e:
            err_msg = str(e)
            if hasattr(e, 'details'): err_msg += f" | Details: {e.details}"
            return {"status": "REJECTED", "code": -1, "msg": err_msg}

    async def cancel_order(self, order_id):
        """Cancel an existing order via connection.

        Parameters:
            order_id: Order identifier.

        Returns:
            Dictionary indicating cancellation status.
        """
        try:
            await asyncio.wait_for(self.connection.cancel_order(order_id), timeout=5.0)
            return {"status": "CANCELED"}
        except TimeoutException as e:
            log.error(f"MetaApi TimeoutException in cancel_order for {order_id}: {e}")
            return {"status": "REJECTED", "msg": str(e)}
        except asyncio.TimeoutError:
            log.error(f"Asyncio TimeoutError in cancel_order for {order_id} after 5.0s.")
            return {"status": "REJECTED", "msg": "TimeoutError"}
        except Exception as e:
            return {"status": "REJECTED", "msg": str(e)}

    async def get_symbol_price(self, symbol):
        """Fetch current bid and ask price with cache lookup and RPC fallback.

        Parameters:
            symbol: Target symbol.

        Returns:
            Dictionary with bidPrice and askPrice, or None on failure.
        """
        if not self.connection:
            return None
        sym = self._to_mt5(symbol)
        
        cached = self.price_listener.prices.get(sym)
        if cached:
            return {"bidPrice": cached["bid"], "askPrice": cached["ask"]}
            
        try:
            res = await asyncio.wait_for(self.connection.get_symbol_price(sym), timeout=5.0)
            return {"bidPrice": res["bid"], "askPrice": res["ask"]}
        except TimeoutException as e:
            log.warning(f"MetaApi TimeoutException in get_symbol_price for {symbol}: {e}")
            return None
        except asyncio.TimeoutError:
            log.warning(f"Asyncio TimeoutError in get_symbol_price for {symbol} after 5.0s.")
            return None
        except Exception:
            return None

    async def get_previous_day_candle(self, symbol):
        """Fetches the actual 1d broker candle for the previous completed day using H1 aggregation to bypass broker bugs."""
        if not hasattr(self, 'account') or not self.account: return None, None
        mt5_sym = self._to_mt5(symbol)
        try:
            import pytz
            from datetime import datetime, timezone
            candles = await self.account.get_historical_candles(mt5_sym, '1h')
            if candles:
                broker_tz = pytz.timezone("Europe/Athens")
                current_broker_date = datetime.now(broker_tz).date()
                
                daily_highs = {}
                daily_lows = {}
                
                for c in candles:
                    candle_broker_date = c['time'].astimezone(broker_tz).date()
                    if candle_broker_date < current_broker_date:
                        date_str = str(candle_broker_date)
                        if date_str not in daily_highs:
                            daily_highs[date_str] = c['high']
                            daily_lows[date_str] = c['low']
                        else:
                            daily_highs[date_str] = max(daily_highs[date_str], c['high'])
                            daily_lows[date_str] = min(daily_lows[date_str], c['low'])
                        
                if daily_highs:
                    sorted_dates = sorted(daily_highs.keys())
                    prev_date = sorted_dates[-1]
                    return float(daily_highs[prev_date]), float(daily_lows[prev_date])
        except Exception as e:
            print(f"Error fetching candles: {e}")
        return None, None

    async def get_asian_range_levels(self, symbol):
        """Fetches the 1h candles and returns the high/low of the 00:00 to 07:59 UTC Asian session."""
        if not hasattr(self, 'account') or not self.account: return None, None
        mt5_sym = self._to_mt5(symbol)
        try:
            import pytz
            from datetime import datetime, timezone
            candles = await self.account.get_historical_candles(mt5_sym, '1h')
            if candles:
                broker_tz = pytz.timezone("Europe/Athens")
                current_broker_date = datetime.now(broker_tz).date()
                
                asian_high = None
                asian_low = None
                
                for c in candles:
                    candle_time = c['time']
                    candle_broker_date = candle_time.astimezone(broker_tz).date()
                    
                    if candle_broker_date == current_broker_date:
                        candle_utc_hour = candle_time.astimezone(timezone.utc).hour
                        if 0 <= candle_utc_hour < 8:
                            if asian_high is None or c['high'] > asian_high:
                                asian_high = c['high']
                            if asian_low is None or c['low'] < asian_low:
                                asian_low = c['low']
                                
                if asian_high is not None and asian_low is not None:
                    return float(asian_high), float(asian_low)
        except Exception as e:
            print(f"Error fetching Asian Range candles: {e}")
        return None, None

    async def get_us_open_range_levels(self, symbol):
        """Fetches the 1m candles and returns the high/low of the 13:30 to 13:59 UTC US Open session for the current day."""
        if not hasattr(self, 'account') or not self.account: return None, None
        mt5_sym = self._to_mt5(symbol)
        try:
            import pytz
            import asyncio
            from datetime import datetime, timezone, timedelta
            candles = await asyncio.wait_for(self.account.get_historical_candles(mt5_sym, '1m'), timeout=10.0)
            import logging
            logging.info(f"DEBUG: get_us_open_range_levels for {mt5_sym} returned {len(candles)} candles")
            if candles:
                broker_tz = pytz.timezone("Europe/Athens")
                current_broker_date = datetime.now(broker_tz).date()
                
                orb_high = None
                orb_low = None
                
                for c in candles:
                    candle_time = c['time']
                    candle_broker_date = candle_time.astimezone(broker_tz).date()
                    
                    if candle_broker_date == current_broker_date:
                        candle_utc = candle_time.astimezone(timezone.utc)
                        if (candle_utc.hour == 13 and 30 <= candle_utc.minute <= 59):
                            if orb_high is None or c['high'] > orb_high:
                                orb_high = c['high']
                            if orb_low is None or c['low'] < orb_low:
                                orb_low = c['low']
                                
                if orb_high is not None and orb_low is not None:
                    return float(orb_high), float(orb_low)
        except Exception as e:
            import logging
            logging.error(f"Error fetching US Open Range candles: {repr(e)}")
            print(f"Error fetching US Open Range candles: {e}")
        return None, None

    async def get_asian_range_levels(self, symbol):
        """Fetches the 1m candles and returns the high/low of the 00:00 to 06:59 UTC Asian session for the current day."""
        if not hasattr(self, 'account') or not self.account: return None, None
        mt5_sym = self._to_mt5(symbol)
        try:
            import pytz
            import asyncio
            from datetime import datetime, timezone, timedelta
            candles = await asyncio.wait_for(self.account.get_historical_candles(mt5_sym, '1m'), timeout=10.0)
            if candles:
                broker_tz = pytz.timezone("Europe/Athens")
                current_broker_date = datetime.now(broker_tz).date()
                
                orb_high = None
                orb_low = None
                
                for c in candles:
                    candle_time = c['time']
                    candle_broker_date = candle_time.astimezone(broker_tz).date()
                    
                    if candle_broker_date == current_broker_date:
                        candle_utc = candle_time.astimezone(timezone.utc)
                        if (0 <= candle_utc.hour <= 6):
                            if orb_high is None or c['high'] > orb_high:
                                orb_high = c['high']
                            if orb_low is None or c['low'] < orb_low:
                                orb_low = c['low']
                                
                if orb_high is not None and orb_low is not None:
                    return float(orb_high), float(orb_low)
        except Exception as e:
            import logging
            logging.error(f"Error fetching Asian Range candles: {repr(e)}")
        return None, None

    async def get_14d_atr(self, symbol):
        """Fetches the last 15 daily candles (via H1 aggregation) and computes the 14-day Average True Range."""
        if not hasattr(self, 'account') or not self.account: return None
        mt5_sym = self._to_mt5(symbol)
        try:
            import pytz
            import asyncio
            import pandas as pd
            from datetime import datetime, timezone
            candles = await asyncio.wait_for(self.account.get_historical_candles(mt5_sym, '1h'), timeout=10.0)
            if candles:
                broker_tz = pytz.timezone("Europe/Athens")
                current_broker_date = datetime.now(broker_tz).date()
                
                daily_candles_dict = {}
                for c in candles:
                    candle_broker_date = c['time'].astimezone(broker_tz).date()
                    if candle_broker_date < current_broker_date:
                        date_str = str(candle_broker_date)
                        if date_str not in daily_candles_dict:
                            daily_candles_dict[date_str] = {
                                'time': c['time'],
                                'open': c['open'],
                                'high': c['high'],
                                'low': c['low'],
                                'close': c['close']
                            }
                        else:
                            daily_candles_dict[date_str]['high'] = max(daily_candles_dict[date_str]['high'], c['high'])
                            daily_candles_dict[date_str]['low'] = min(daily_candles_dict[date_str]['low'], c['low'])
                            daily_candles_dict[date_str]['close'] = c['close']
                
                valid_candles = []
                for d in sorted(daily_candles_dict.keys()):
                    valid_candles.append(daily_candles_dict[d])
                
                if len(valid_candles) >= 15:
                    df = pd.DataFrame(valid_candles[-15:])
                    df['high'] = df['high'].astype(float)
                    df['low'] = df['low'].astype(float)
                    df['close'] = df['close'].astype(float)
                    
                    df['prev_close'] = df['close'].shift(1)
                    tr1 = df['high'] - df['low']
                    tr2 = (df['high'] - df['prev_close']).abs()
                    tr3 = (df['low'] - df['prev_close']).abs()
                    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                    
                    return float(tr.tail(14).mean())
        except Exception as e:
            print(f"Error fetching ATR: {e}")
        return None

    async def sync_native_take_profit_staggered(self, symbol, side, tp_prices_array):
        """Attach staggered Take Profit prices natively to MT5 position tickets.

        Parameters:
            symbol: Target symbol.
            side: Target side ('LONG' or 'SHORT').
            tp_prices_array: List of target TP prices.
        """
        if not self.connection or not tp_prices_array:
            return
        try:
            mt5_sym = self._to_mt5(symbol)
            mt5_positions = await self.get_positions()
            if not mt5_positions:
                return
            target_type = 'POSITION_TYPE_BUY' if side == "LONG" else 'POSITION_TYPE_SELL'
            active_tickets = [p for p in mt5_positions if p['symbol'] == mt5_sym and p['type'] == target_type]
            if not active_tickets:
                return
            
            if side == "LONG":
                active_tickets.sort(key=lambda x: x.get('openPrice', 0), reverse=True)
            else:
                active_tickets.sort(key=lambda x: x.get('openPrice', 0))
                
            for i, p in enumerate(active_tickets):
                target_tp = float(tp_prices_array[i]) if i < len(tp_prices_array) else float(tp_prices_array[-1])
                current_tp = p.get('takeProfit', 0)
                if current_tp == 0 or (target_tp > 0 and abs(current_tp - target_tp) / target_tp > 0.0015):
                    try:
                        await self.connection.modify_position(p['id'], take_profit=target_tp)
                    except Exception as e:
                        log.error(f"TP SYNC NATIVE ERROR on ticket {p['id']}: {e}")
        except Exception as e:
            log.error(f"TP SYNC NATIVE CRITICAL ERROR: {e}")

    async def amputate_toxic_tickets(self, symbol, side, budget_usd, current_price):
        """Surgically amputate worst-priced tickets using allocated pool budget.

        Parameters:
            symbol: Target symbol.
            side: Target side ('LONG' or 'SHORT').
            budget_usd: Allocated loss budget.
            current_price: Reference market price.

        Returns:
            Total loss amount spent.
        """
        if not self.connection or budget_usd <= 0:
            return 0.0
        try:
            mt5_sym = self._to_mt5(symbol)
            mt5_positions = await self.get_positions()
            if not mt5_positions:
                return 0.0
            target_type = 'POSITION_TYPE_BUY' if side == "LONG" else 'POSITION_TYPE_SELL'
            
            tickets = [p for p in mt5_positions if p['symbol'] == mt5_sym and p['type'] == target_type]
            if not tickets:
                return 0.0
            
            tickets.sort(key=lambda x: x['openPrice'], reverse=(side == "LONG"))
            
            spent = 0.0
            for t in tickets:
                if spent >= budget_usd:
                    break
                
                open_p = t['openPrice']
                vol = t['volume']
                
                loss_per_coin = (open_p - current_price) if side == "LONG" else (current_price - open_p)
                if loss_per_coin <= 0:
                    continue
                
                affordable_vol = (budget_usd - spent) / loss_per_coin
                affordable_vol = round(affordable_vol / 0.01) * 0.01
                
                close_vol = min(vol, affordable_vol)
                if close_vol < 0.01:
                    continue
                
                log.info(f"NATIVE AMPUTATION: Slicing {close_vol} lots from ticket {t['id']} at {current_price} (Loss: ${close_vol * loss_per_coin:.2f})")
                
                if close_vol >= vol - 0.001:
                    await self.connection.close_position(t['id'])
                else:
                    await self.connection.close_position_partially(t['id'], close_vol)
                    
                spent += (close_vol * loss_per_coin)
                await asyncio.sleep(0.5)
                
            return spent
        except Exception as e:
            log.error(f"AMPUTATION ERROR: {e}")
            return 0.0
