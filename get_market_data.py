import yfinance as yf
from datetime import datetime, timedelta

def get_data(ticker):
    print(f"\n--- {ticker} ---")
    end = datetime.utcnow()
    start = end - timedelta(hours=6)
    data = yf.download(ticker, start=start, interval="1h", progress=False)
    print(data[['Open', 'High', 'Low', 'Close']])

get_data('BTC-USD')
get_data('NQ=F')
