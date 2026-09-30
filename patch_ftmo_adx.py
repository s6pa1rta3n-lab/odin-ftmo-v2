import re

with open('/home/solveetcoagula/odin_ftmo/griff_engine_live.py', 'r') as f:
    content = f.read()

# Add compute_adx function if not present
if "def compute_adx" not in content:
    adx_func = """
def compute_adx(candles, period=14):
    if len(candles) <= period: return [0]*len(candles)
    tr_list, pdm, ndm = [0], [0], [0]
    for i in range(1, len(candles)):
        c, pc = candles[i], candles[i-1]
        tr = max(float(c['high']) - float(c['low']), abs(float(c['high']) - float(pc['close'])), abs(float(c['low']) - float(pc['close'])))
        up = float(c['high']) - float(pc['high'])
        dn = float(pc['low']) - float(c['low'])
        pos = up if up > dn and up > 0 else 0
        neg = dn if dn > up and dn > 0 else 0
        tr_list.append(tr)
        pdm.append(pos)
        ndm.append(neg)
    
    adx, dx = [0]*len(candles), [0]*len(candles)
    if len(candles) <= period*2: return adx
    
    sm_tr = sum(tr_list[1:period+1])
    sm_pdm = sum(pdm[1:period+1])
    sm_ndm = sum(ndm[1:period+1])
    
    for i in range(period, len(candles)):
        if i > period:
            sm_tr = sm_tr - (sm_tr / period) + tr_list[i]
            sm_pdm = sm_pdm - (sm_pdm / period) + pdm[i]
            sm_ndm = sm_ndm - (sm_ndm / period) + ndm[i]
        
        pdi = 100 * (sm_pdm / sm_tr) if sm_tr > 0 else 0
        ndi = 100 * (sm_ndm / sm_tr) if sm_tr > 0 else 0
        diff = abs(pdi - ndi)
        summ = pdi + ndi
        dx[i] = 100 * (diff / summ) if summ > 0 else 0
        
    adx[period*2 - 1] = sum(dx[period:period*2]) / period
    for i in range(period*2, len(candles)):
        adx[i] = (adx[i-1] * (period - 1) + dx[i]) / period
    return adx
"""
    # Insert it right before compute_ema_50
    content = content.replace('def compute_ema_50(', adx_func + '\ndef compute_ema_50(')

# Inject the ADX filter logic
target_block = """                logger.info("Inside Bar confirmed on bar %s. Macro Trend: %s (EMA50: %.2f)", latest_bar_time, trend_direction, ema_50)
                
                # We place the pending breakout orders, but the place_pending_breakout_orders method needs to be aware of the trend
                # We'll pass the trend to place_pending_breakout_orders to only place the aligned order
                await self.place_pending_breakout_orders(current_bar, atr_14, self.current_equity, trend_direction)"""

replacement_block = """                logger.info("Inside Bar confirmed on bar %s. Macro Trend: %s (EMA50: %.2f)", latest_bar_time, trend_direction, ema_50)
                
                adx_values = compute_adx(candles, 14)
                current_adx = adx_values[-1] if adx_values else 0
                
                if current_adx < 25:
                    logger.info("ADX Filter Blocked Trade: Current ADX is %.2f (Requires >= 25). Skipping chop.", current_adx)
                    return {"status": "SKIPPED_ADX_LOW", "atr_14": atr_14, "bar": latest_bar_time}
                
                logger.info("ADX is %.2f. Trend is strong. Proceeding to place orders.", current_adx)
                
                # We place the pending breakout orders, but the place_pending_breakout_orders method needs to be aware of the trend
                # We'll pass the trend to place_pending_breakout_orders to only place the aligned order
                await self.place_pending_breakout_orders(current_bar, atr_14, self.current_equity, trend_direction)"""

if "compute_adx(candles, 14)" not in content:
    content = content.replace(target_block, replacement_block)

with open('/home/solveetcoagula/odin_ftmo/griff_engine_live.py', 'w') as f:
    f.write(content)
