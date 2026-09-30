import pandas as pd
import numpy as np
import os

def load_data(filepath):
    print(f"Loading {filepath}...")
    df = pd.read_csv(filepath)
    # Convert timestamp (ms) to datetime UTC
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.set_index('datetime', inplace=True)
    df.drop(columns=['timestamp'], inplace=True)
    
    # Filter out flatlines (weekends) where open == high == low == close
    # and diff is 0 to previous
    df['is_flat'] = (df['open'] == df['high']) & (df['high'] == df['low']) & (df['low'] == df['close'])
    df['diff'] = df['close'].diff().fillna(0)
    
    # Remove consecutive flats
    mask = ~(df['is_flat'] & (df['diff'] == 0))
    df = df[mask].copy()
    df.drop(columns=['is_flat', 'diff'], inplace=True)
    
    print(f"Loaded {len(df)} rows after cleaning.")
    return df

def resample_data(df, timeframe='5min'):
    # Resample to higher timeframe
    resampled = df.resample(timeframe).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    }).dropna()
    return resampled

if __name__ == "__main__":
    # Test script
    df = load_data('/Users/solveetcoagula/Desktop/google_cloud/usatechidxusd-m1-bid-2026-08-01-2026-09-02.csv')
    print(df.head())
