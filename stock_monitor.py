#!/usr/bin/env python3

# Stock Crash Monitor
# Version 1.0
# By Alan Rockefeller - October 17, 2025

import yfinance as yf
import os
import argparse
import datetime
import requests
import pandas as pd

# CONFIGURATION
# =============
# Set the interval for fetching data (e.g., '1m', '5m', '15m')
DATA_INTERVAL = '5m'

# Set the log file path
LOG_FILE = "stock_monitor.log"

DEFAULT_THRESHOLD = 0.5

# PUSHOVER CONFIGURATION
# ======================
# Your Pushover User Key
PUSHOVER_USER_KEY = ""
# Your Pushover API Token
PUSHOVER_API_TOKEN = ""

def send_pushover_notification(message):
    """
    Sends a push notification using Pushover.
    """
    if not PUSHOVER_USER_KEY or not PUSHOVER_API_TOKEN:
        print("Pushover credentials are not set. Skipping notification.")
        return

    try:
        response = requests.post("https://api.pushover.net/1/messages.json", data={
            "token": PUSHOVER_API_TOKEN,
            "user": PUSHOVER_USER_KEY,
            "message": message,
        })
        response.raise_for_status()
        print("Pushover notification sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Could not send Pushover notification: {e}")

def log_alert(message):
    """
    Logs an alert message to the console, to a log file, and sends a push notification.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    with open(LOG_FILE, "a") as f:
        f.write(log_message + "\n")
    send_pushover_notification(message)


def log_api(message):
    """
    Logs an API request/response to api_log.txt.
    """
    with open("api_log.txt", "a") as f:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {message}\n")

def test_pushover():
    """
    Sends a test notification to Pushover.
    """
    print("Sending test notification to Pushover...")
    send_pushover_notification("This is a test notification from the stock monitor script.")

def analyze_stocks(args):
    """
    Analyzes the stocks in the watchlist to determine how many alerts would have been triggered
    in the last month at different thresholds.
    """
    watchlist = {}
    try:
        with open("watchlist.txt", "r") as f:
            # Skip header row
            next(f)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(',')
                ticker = parts[0].strip()
                # Threshold from file is not used in analysis, but we need the ticker
                watchlist[ticker] = 0
    except FileNotFoundError:
        print("watchlist.txt not found.")
        return

    if not watchlist:
        print("Watchlist is empty.")
        return

    print("Analyzing stocks... This may take a minute or two.")

    thresholds_to_analyze = [0.1, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0]

    for ticker in watchlist.keys():
        print(f"\n--- Analyzing {ticker} ---")
        try:
            # Download historical data for the last month
            if args.apilog:
                log_api(f"Request: yf.download(ticker={ticker}, period='1mo', interval={DATA_INTERVAL})")
            data = yf.download(ticker, period="1mo", interval=DATA_INTERVAL, auto_adjust=True, progress=False)
            if args.apilog:
                log_api(f"Response: Received {len(data)} rows of data.")

            if data.empty:
                print(f"Could not get historical data for {ticker}.")
                continue

            # Calculate percentage change
            data['Percent Change'] = data['Close'].pct_change() * 100

            for threshold in thresholds_to_analyze:
                alerts = data[abs(data['Percent Change']) > threshold]
                print(f"Alerts in the last month at {threshold}% threshold: {len(alerts)}")

        except Exception as e:
            print(f"Could not analyze {ticker}: {e}")

def check_stock_price_change(verbose=False, apilog=False):
    """
    Checks for unusual price changes in stocks listed in watchlist.txt.
    """
    watchlist = {}
    try:
        with open("watchlist.txt", "r") as f:
            # Skip header row
            next(f)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(',')
                ticker = parts[0].strip()
                threshold = float(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else DEFAULT_THRESHOLD
                direction = parts[2].strip().lower() if len(parts) > 2 and parts[2].strip() else 'both'
                price_below = float(parts[3].strip()) if len(parts) > 3 and parts[3].strip() else None
                price_above = float(parts[4].strip()) if len(parts) > 4 and parts[4].strip() else None
                watchlist[ticker] = {
                    "threshold": threshold,
                    "direction": direction,
                    "price_below": price_below,
                    "price_above": price_above
                }
    except FileNotFoundError:
        print("watchlist.txt not found.")
        return

    if not watchlist:
        print("Watchlist is empty.")
        return

    try:
        # Download intraday data for all tickers in a single request
        tickers_string = " ".join(watchlist.keys())
        if apilog:
            log_api(f"Request: yf.download(tickers={tickers_string}, period=\"1d\", interval={DATA_INTERVAL})")
        data = yf.download(tickers=tickers_string, period="1d", interval=DATA_INTERVAL, auto_adjust=True, progress=False)
        if apilog:
            log_api(f"Response: Received {len(data)} rows of data.")

        if len(data) < 2:
            print(f"Could not get enough data for the given tickers at {DATA_INTERVAL} interval, skipping.")
            return

        for ticker, config in watchlist.items():
            threshold = config["threshold"]
            direction = config["direction"]
            price_below = config["price_below"]
            price_above = config["price_above"]

            # Extract data for the current ticker
            ticker_data = data['Close'][ticker]
            
            if ticker_data.isnull().all():
                print(f"No data for {ticker}, skipping.")
                continue

            # Get the last two available prices and their timestamps
            price1 = ticker_data.iloc[-2]
            time1 = ticker_data.index[-2]
            price2 = ticker_data.iloc[-1]
            time2 = ticker_data.index[-1]
            
            percent_change = ((price2 - price1) / price1) * 100
            
            if verbose:
                print(f"--- {ticker} ---")
                print(f"Time 1: {time1.strftime('%Y-%m-%d %H:%M:%S')}, Price 1: {price1:.2f}")
                print(f"Time 2: {time2.strftime('%Y-%m-%d %H:%M:%S')}, Price 2: {price2:.2f}")
                print(f"Percent Change: {percent_change:.2f}%")
                print(f"Threshold: {threshold}%")
                print(f"Direction: {direction}")
                if price_below:
                    print(f"Price Below: {price_below:.2f}")
                if price_above:
                    print(f"Price Above: {price_above:.2f}")
                print("---------------------")

            # Percentage change alerts
            percentage_alert = False
            if direction == 'both' and abs(percent_change) > threshold:
                percentage_alert = True
            elif direction == 'gain' and percent_change > threshold:
                percentage_alert = True
            elif direction == 'drop' and percent_change < -threshold:
                percentage_alert = True

            if percentage_alert:
                message = f"Unusual price change detected for {ticker}: {percent_change:.2f}% (Threshold: {threshold}%, Direction: {direction})"
                log_alert(message)

            # Price target alerts
            if price_below and price2 < price_below:
                message = f"{ticker} has dropped below your target of {price_below:.2f}. Current price: {price2:.2f}"
                log_alert(message)
            
            if price_above and price2 > price_above:
                message = f"{ticker} has gone above your target of {price_above:.2f}. Current price: {price2:.2f}"
                log_alert(message)

    except Exception as e:
        print(f"Could not process tickers: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor stock prices for unusual changes.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed stock data.")
    parser.add_argument("--testpush", action="store_true", help="Send a test notification to Pushover.")
    parser.add_argument("--analyze", action="store_true", help="Analyze stocks in the watchlist.")
    parser.add_argument("--apilog", action="store_true", help="Log all API requests to api_log.txt.")
    args = parser.parse_args()

    # Check if yfinance and requests are installed
    try:
        import yfinance
        import requests
        import pandas
    except ImportError:
        print("yfinance, requests, and pandas are not installed. Please install them using: pip install yfinance requests pandas")
        exit(1)

    if args.analyze:
        analyze_stocks(args)
        exit()

    if args.testpush:
        test_pushover()
        exit()
    
    check_stock_price_change(args.verbose, args.apilog)
