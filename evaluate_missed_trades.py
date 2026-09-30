import yfinance as yf
import pandas as pd
nq_df = yf.download("NQ=F", period="2d", interval="1m", progress=False)
if isinstance(nq_df.columns, pd.MultiIndex): nq_df.columns = nq_df.columns.droplevel(1)
nq_df.index = nq_df.index.tz_convert('UTC')

mask = (nq_df.index >= pd.to_datetime("2026-09-22 17:12:00+00:00")) & (nq_df.index <= pd.to_datetime("2026-09-22 17:13:00+00:00"))
print(nq_df[mask]['Close'])
