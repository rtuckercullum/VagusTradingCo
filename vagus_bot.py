"""
Vagus-Nerve Informed Alpaca Trading Bot
---------------------------------------
This script demonstrates how one might combine spiritual/physiological-inspired
concepts (e.g., a "vagus nerve index" for calm trading) with a simple technical 
signal (RSI). It uses Alpaca’s API to place live trades automatically, so be sure 
you only run it with a paper trading account until thoroughly tested.
"""

import os
import time
import numpy as np
import pandas as pd
import requests
import talib   # pip install TA-Lib
from datetime import datetime, timedelta
import alpaca_trade_api as tradeapi

##############################
# 1) Configuration & Setup
##############################

# For safety, use environment variables or other secure methods
# to store your API credentials. (Set these in your environment or .env file)
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY_ID")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET_KEY")
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"  # 'Paper' for testing

# Symbol(s) to trade—choose flexible or specific
SYMBOL = "SPY"

# Example timeframe: 15-minute bars. Could also do 1Min, 1Hour, 1Day, etc.
TIMEFRAME = "15Min"

# RSI thresholds (tweak these prayerfully)
RSI_LOWER = 30
RSI_UPPER = 70

# “Vagus nerve factor” – a conceptual attempt to avoid “fight or flight” trades.
# If we sense the market is too volatile or our spiritual sense says “hold”,
# we can adjust signals accordingly. For example, if vol is too high,
# raise the RSI thresholds to be more conservative.
VAGUS_NERVE_SENSITIVITY = 0.5  # 0.0 -> super calm, 1.0 -> moderate, >1.0 -> more cautious

# Position sizing: fraction of account equity to allocate each trade
POSITION_SIZE_FRACTION = 0.1

# How often to run the loop (in seconds). 900 sec = 15 minutes
LOOP_INTERVAL = 900  

##############################
# 2) Connect to Alpaca
##############################
api = tradeapi.REST(
    ALPACA_API_KEY,
    ALPACA_API_SECRET,
    ALPACA_BASE_URL,
    api_version="v2"
)

def get_account_info():
    account = api.get_account()
    print(f"Account Status: {account.status}")
    print(f"Equity: {account.equity}")
    print(f"Buying Power: {account.buying_power}")
    return account

##############################
# 3) “Vagus Nerve” Informed Logic Helpers
##############################
def get_vagus_nerve_factor():
    """
    Example: measure volatility or emotional measure to adapt RSI thresholds.
    In a real-world scenario, this might integrate with data about volatility,
    or even personal biometric data. Here, we simply fetch the symbol’s 
    average true range (ATR) as a proxy for 'market stress.'
    """
    # For demonstration, fetch recent bars
    now = datetime.now()
    start = (now - timedelta(days=5)).isoformat()
    bars = api.get_bars(SYMBOL, "15Min", start, now.isoformat()).df
    
    if len(bars) < 14:
        return 1.0  # if not enough data, default factor
    
    # Compute ATR (Average True Range) as a basic 'volatility' measure
    bars['high_low'] = bars['high'] - bars['low']
    bars['high_close'] = np.abs(bars['high'] - bars['close'].shift(1))
    bars['low_close'] = np.abs(bars['low'] - bars['close'].shift(1))
    tr = bars[['high_low','high_close','low_close']].max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]

    # The bigger the ATR, the more 'stressful' the market.
    # Adjust the factor so that higher volatility -> bigger factor -> more conservative
    baseline_atr = bars['close'].mean() * 0.005  # just a rough baseline
    stress_factor = atr / baseline_atr
    # Combine with user-chosen sensitivity
    vagus_factor = 1.0 + (stress_factor - 1.0) * VAGUS_NERVE_SENSITIVITY
    
    return vagus_factor

def compute_rsi_vagus_adjusted(prices, rsi_lower=30, rsi_upper=70):
    """
    Compute RSI, then adjust thresholds based on the 'vagus nerve' factor.
    This is purely a demonstration of how you might incorporate 
    physiological/spiritual caution.
    """
    # Standard RSI
    rsi = talib.RSI(prices, timeperiod=14)
    latest_rsi = rsi.iloc[-1]

    # Market 'stress' factor
    vagus_factor = get_vagus_nerve_factor()

    # Adjust RSI thresholds up or down based on factor. 
    # e.g., if factor>1, raise the thresholds => trade less often
    rsi_lower_adj = rsi_lower * vagus_factor
    rsi_upper_adj = rsi_upper * vagus_factor

    return latest_rsi, rsi_lower_adj, rsi_upper_adj

##############################
# 4) Trading Logic
##############################
def get_recent_bars(symbol, timeframe, lookback_minutes=60*6):
    """
    Fetch historical bar data for the given lookback window.
    By default, looks back about 6 hours for intraday strategies.
    """
    now = datetime.now()
    start = (now - timedelta(minutes=lookback_minutes)).isoformat()
    bars = api.get_bars(symbol, timeframe, start, now.isoformat()).df
    return bars

def get_current_position(symbol):
    """
    Return any open position for the symbol, or None if no position.
    """
    try:
        position = api.get_position(symbol)
        return position
    except tradeapi.rest.APIError:
        # means no position
        return None

def calculate_order_quantity(symbol, fraction):
    """
    Calculate how many shares to buy based on fraction of account equity.
    """
    account = api.get_account()
    equity = float(account.equity)
    allocate = equity * fraction  # amount of $ to allocate
    # Get current price
    quote = api.get_last_quote(symbol)
    last_price = quote.askprice if quote.askprice > 0 else quote.bidprice
    if last_price == 0:
        # fallback
        last_trade = api.get_last_trade(symbol)
        last_price = last_trade.price
    shares = int(allocate // last_price)
    return max(shares, 0)

def trade_decision():
    """
    Main logic to decide whether to buy, sell, or hold based on RSI + vagus nerve factors.
    """
    bars = get_recent_bars(SYMBOL, TIMEFRAME)
    if len(bars) < 14:
        print("Not enough bars to compute RSI. Waiting...")
        return

    close_prices = bars['close']
    latest_rsi, rsi_lower_adj, rsi_upper_adj = compute_rsi_vagus_adjusted(
        close_prices, 
        RSI_LOWER, 
        RSI_UPPER
    )

    print(f"[{datetime.now()}] {SYMBOL} RSI: {latest_rsi:.2f} (Adjusted L:{rsi_lower_adj:.2f} U:{rsi_upper_adj:.2f})")

    position = get_current_position(SYMBOL)
    if position:
        # Already in a position
        qty = abs(int(position.qty))
        side = "long" if float(position.qty) > 0 else "short"
        print(f"Current position: {qty} shares {side}.")

        # Example exit condition if RSI crosses above upper threshold
        if float(position.qty) > 0 and latest_rsi > rsi_upper_adj:
            # Sell to close
            print(f"RSI above {rsi_upper_adj:.2f}, closing long position.")
            api.submit_order(
                symbol=SYMBOL,
                qty=qty,
                side="sell",
                type="market",
                time_in_force="gtc"
            )
        # If you had short logic, you could close short if RSI < lower threshold, etc.
    else:
        # No position, consider entering if RSI is below lower threshold
        if latest_rsi < rsi_lower_adj:
            # Buy
            qty = calculate_order_quantity(SYMBOL, POSITION_SIZE_FRACTION)
            if qty > 0:
                print(f"RSI below {rsi_lower_adj:.2f}, buying {qty} shares.")
                api.submit_order(
                    symbol=SYMBOL,
                    qty=qty,
                    side="buy",
                    type="market",
                    time_in_force="gtc"
                )
            else:
                print("Calculated quantity was 0. Possibly insufficient equity.")
        else:
            print("No trade signal at this time.")

##############################
# 5) Main Loop
##############################
if __name__ == "__main__":
    # Print basic account info for confirmation
    get_account_info()
    
    print("Starting Vagus-Nerve Informed Trading Bot. Press Ctrl+C to exit.")
    while True:
        try:
            trade_decision()
            # Sleep until next cycle
            time.sleep(LOOP_INTERVAL)
        except KeyboardInterrupt:
            print("Shutting down gracefully...")
            break
        except Exception as e:
            # Log any error but keep going
            print("Error encountered:", e)
            time.sleep(LOOP_INTERVAL)