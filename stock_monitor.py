#!/usr/bin/env python3

# Stock Crash Monitor
# Version 1.0
# By Alan Rockefeller - October 17, 2025

try:
    import yfinance as yf
    import pandas as pd
    import requests
except ImportError:
    print("Required packages are not installed. Please install them using: pip install yfinance pandas requests")
    exit(1)

import os
import argparse
import datetime
import csv

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
        }, timeout=10)
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

def parse_watchlist():
    """
    Parses the watchlist.txt file, returning a dictionary of tickers and their configurations.
    """
    watchlist = {}
    try:
        with open("watchlist.txt", "r") as f:
            reader = csv.reader(f)
            # Skip header row
            next(reader)
            for row in reader:
                # Skip comments and blank lines
                if not row or row[0].strip().startswith('#'):
                    continue

                ticker = row[0].strip()
                threshold = float(row[1].strip()) if len(row) > 1 and row[1].strip() else DEFAULT_THRESHOLD
                direction = row[2].strip().lower() if len(row) > 2 and row[2].strip() else 'both'
                price_below = float(row[3].strip()) if len(row) > 3 and row[3].strip() else None
                price_above = float(row[4].strip()) if len(row) > 4 and row[4].strip() else None

                if direction not in ['gain', 'drop', 'both']:
                    print(f"Invalid direction '{direction}' for ticker {ticker}. Defaulting to 'both'.")
                    direction = 'both'

                watchlist[ticker] = {
                    "threshold": threshold,
                    "direction": direction,
                    "price_below": price_below,
                    "price_above": price_above
                }
    except FileNotFoundError:
        print("watchlist.txt not found.")
    
    return watchlist

def analyze_stocks(args):
    """
    Analyzes the stocks in the watchlist to determine how many alerts would have been triggered
    in the last month at different thresholds.
    """
    watchlist = parse_watchlist()
    if not watchlist:
        print("Watchlist is empty or not found.")
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

        except requests.exceptions.RequestException as e:
            print(f"Could not download data for {ticker}: {e}")
        except (KeyError, ValueError) as e:
            print(f"Could not analyze data for {ticker}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while analyzing {ticker}: {e}")
            raise

def check_stock_price_change(verbose=False, apilog=False):
    """
    Checks for unusual price changes in stocks listed in watchlist.txt.
    """
    watchlist = parse_watchlist()
    if not watchlist:
        print("Watchlist is empty or not found.")
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
            ticker_data = None
            if isinstance(data['Close'], pd.DataFrame):
                if ticker in data['Close'].columns:
                    ticker_data = data['Close'][ticker]
            else: # It's a Series
                ticker_data = data['Close']

            if ticker_data is None or ticker_data.isnull().all():
                print(f"No data for {ticker}, skipping.")
                continue

            # Drop NaNs and get the last two available prices for the ticker
            valid_data = ticker_data.dropna()
            
            if len(valid_data) < 2:
                if verbose:
                    print(f"Not enough data for {ticker} after dropping NaNs, skipping.")
                continue

            # Get the last two available prices and their timestamps
            price1 = valid_data.iloc[-2]
            time1 = valid_data.index[-2]
            price2 = valid_data.iloc[-1]
            time2 = valid_data.index[-1]
            
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
            if price_below is not None and price2 < price_below:
                message = f"{ticker} has dropped below your target of {price_below:.2f}. Current price: {price2:.2f}"
                log_alert(message)
            
            if price_above is not None and price2 > price_above:
                message = f"{ticker} has gone above your target of {price_above:.2f}. Current price: {price2:.2f}"
                log_alert(message)

    except requests.exceptions.RequestException as e:
        print(f"Could not download data for tickers: {e}")
    except (KeyError, ValueError, ZeroDivisionError) as e:
        print(f"Could not process tickers: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor stock prices for unusual changes.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed stock data.")
    parser.add_argument("--testpush", action="store_true", help="Send a test notification to Pushover.")
    parser.add_argument("--analyze", action="store_true", help="Analyze stocks in the watchlist.")
    parser.add_argument("--apilog", action="store_true", help="Log all API requests to api_log.txt.")
    args = parser.parse_args()


    if args.analyze:
        analyze_stocks(args)
        exit()

    if args.testpush:
        test_pushover()
        exit()
    
    check_stock_price_change(args.verbose, args.apilog)
