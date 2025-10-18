#!/usr/bin/env python3

# Stock Crash Monitor
# Version 1.0
# By Alan Rockefeller - October 17, 2025

try:
    import yfinance as yf
    import pandas as pd
    import requests
    from zoneinfo import ZoneInfo
except ImportError:
    print("Required packages are not installed. Please install them using: pip install yfinance pandas requests tzdata")
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
DEFAULT_ALERT_FREQUENCY = 'daily'

# PUSHOVER CONFIGURATION
# ======================
# Your Pushover User Key
PUSHOVER_USER_KEY = ""
# Your Pushover API Token
PUSHOVER_API_TOKEN = ""

def send_pushover_notification(message):
    """
    Sends a push notification using Pushover.
    Returns True on success, False on skip or failure.
    """
    if not PUSHOVER_USER_KEY or not PUSHOVER_API_TOKEN:
        print("Pushover credentials are not set. Skipping notification.")
        return False # Return False if skipped

    try:
        response = requests.post("https://api.pushover.net/1/messages.json", data={
            "token": PUSHOVER_API_TOKEN,
            "user": PUSHOVER_USER_KEY,
            "message": message,
        }, timeout=10)
        response.raise_for_status()
        print("Pushover notification sent successfully.")
        return True # Return True on success
    except requests.exceptions.RequestException as e:
        print(f"Could not send Pushover notification: {e}")
        return False # Return False on failure

def create_alert_file(ticker, message):
    """
    Creates a file in the alerts directory to log the alert.
    """
    if not os.path.exists("alerts"):
        os.makedirs("alerts")
    
    alert_file_path = os.path.join("alerts", f"{ticker}.txt")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(alert_file_path, "w") as f:
        f.write(f"Alert sent ({timestamp})\n")
        f.write(message + "\n")

def should_send_alert(ticker, frequency):
    """
    Checks if an alert should be sent based on the alert frequency, using calendar-based checks.
    """
    alert_file_path = os.path.join("alerts", f"{ticker}.txt")
    if not os.path.exists(alert_file_path):
        return True # First time, always send

    if frequency == 'once':
        return False # Only send once

    with open(alert_file_path, "r") as f:
        first_line = f.readline()
        if "Alert sent" in first_line:
            try:
                last_alert_str = first_line.split('(')[1].split(')')[0]
                last_alert_date = datetime.datetime.strptime(last_alert_str, '%Y-%m-%d %H:%M:%S')
                now = datetime.datetime.now()

                # Calendar-based checks
                if frequency == 'daily' and now.date() > last_alert_date.date():
                    return True
                # For weekly and monthly, we need to consider the year as well
                if frequency == 'weekly':
                    # Check if it's a different week or a different year
                    if now.isocalendar().year != last_alert_date.isocalendar().year or \
                       now.isocalendar().week != last_alert_date.isocalendar().week:
                        return True
                if frequency == 'monthly':
                    # Check if it's a different month or a different year
                    if now.year != last_alert_date.year or now.month != last_alert_date.month:
                        return True
            except (ValueError, IndexError):
                # If the file is malformed, allow sending the alert
                return True
    
    return False

def log_alert(message, ticker, frequency):
    """
    Logs an alert message to the console, to a log file, and sends a push notification.
    If an alert is skipped due to frequency, it still prints the current price and relevant details.
    Only creates an alert file if Pushover notification is successful.
    """
    should_send = should_send_alert(ticker, frequency)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry_message = f"[{timestamp}] {message}" # This is what goes into the log file

    if not should_send:
        print(f"Alert for {ticker} already sent according to frequency '{frequency}'. Skipping.")
        # Print the details that would have been in the alert.
        print(f"Details: {message}")
        # Always append to LOG_FILE, even if skipped
        with open(LOG_FILE, "a") as f:
            f.write(log_entry_message + "\n")
        return # Exit after handling skipped alert

    # If we reach here, the alert should be sent.
    print(log_entry_message) # Print the timestamped log message to console
    
    # Send Pushover notification and check for success
    pushover_success = send_pushover_notification(message)

    # Always append to LOG_FILE if should_send is True
    with open(LOG_FILE, "a") as f:
        f.write(log_entry_message + "\n")

    # Only create alert file if Pushover was successful
    if pushover_success:
        create_alert_file(ticker, message)
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
    Hardened for robustness.
    """
    watchlist = {}
    try:
        with open("watchlist.txt", "r") as f:
            # 1. Use skipinitialspace=True
            reader = csv.reader(f, skipinitialspace=True)
            
            # Read all rows into a list to allow multiple passes if needed
            all_rows = list(reader)
            
            header_index = -1
            # Find the header row index
            for i, row in enumerate(all_rows):
                if row and row[0].strip() == 'TICKER':
                    header_index = i
                    break
            
            rows_to_process = all_rows
            if header_index != -1:
                # If header found, process rows after it
                rows_to_process = all_rows[header_index + 1:]
            else:
                print("Warning: 'TICKER' header not found in watchlist.txt. Processing all rows as data.")
                # If no header, process all rows. `rows_to_process` is already `all_rows`.

            # Process the relevant rows
            for row in rows_to_process:
                # Skip comments and blank lines
                if not row or row[0].strip().startswith('#'):
                    continue

                # 4. Compute and use stripped ticker once, reject if empty
                ticker = row[0].strip()
                if not ticker:
                    print(f"Warning: Skipping row with empty ticker: {row}")
                    continue

                # Parse threshold
                try:
                    # 3. Guarded float conversion for threshold
                    threshold_str = row[1].strip() if len(row) > 1 else None
                    if threshold_str:
                        threshold = float(threshold_str)
                    else:
                        threshold = DEFAULT_THRESHOLD # Default if missing
                except ValueError:
                    print(f"Warning: Invalid threshold '{row[1].strip()}' for ticker {ticker}. Using default threshold {DEFAULT_THRESHOLD}.")
                    threshold = DEFAULT_THRESHOLD

                direction = row[2].strip().lower() if len(row) > 2 and row[2].strip() else 'both'
                
                # 3. Wrap parsing of price_below and price_above in guarded float conversion
                price_below = None
                try:
                    price_below_str = row[3].strip() if len(row) > 3 else None
                    if price_below_str:
                        price_below = float(price_below_str)
                except ValueError:
                    print(f"Warning: Invalid price_below '{row[3].strip()}' for ticker {ticker}. Defaulting to None.")
                    price_below = None # Explicitly set to None on failure

                price_above = None
                try:
                    price_above_str = row[4].strip() if len(row) > 4 else None
                    if price_above_str:
                        price_above = float(price_above_str)
                except ValueError:
                    print(f"Warning: Invalid price_above '{row[4].strip()}' for ticker {ticker}. Defaulting to None.")
                    price_above = None # Explicitly set to None on failure

                alert_frequency = row[5].strip().lower() if len(row) > 5 and row[5].strip() else DEFAULT_ALERT_FREQUENCY

                if direction not in ['gain', 'drop', 'both']:
                    print(f"Invalid direction '{direction}' for ticker {ticker}. Defaulting to 'both'.")
                    direction = 'both'
                
                if alert_frequency not in ['once', 'daily', 'weekly', 'monthly']:
                    print(f"Invalid alert frequency '{alert_frequency}' for ticker {ticker}. Defaulting to '{DEFAULT_ALERT_FREQUENCY}'.")
                    alert_frequency = DEFAULT_ALERT_FREQUENCY

                watchlist[ticker] = {
                    "threshold": threshold,
                    "direction": direction,
                    "price_below": price_below,
                    "price_above": price_above,
                    "alert_frequency": alert_frequency
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

def get_market_session():
    """
    Determines the current market session (pre-market, regular, post-market).
    """
    now = datetime.datetime.now(ZoneInfo("America/New_York")).time()
    pre_market_start = datetime.time(4, 0)
    market_start = datetime.time(9, 30)
    market_end = datetime.time(16, 0)
    post_market_end = datetime.time(20, 0)

    if pre_market_start <= now < market_start:
        return "pre-market"
    elif market_start <= now < market_end:
        return "regular"
    elif market_end <= now < post_market_end:
        return "post-market"
    else:
        return "closed"

def get_current_price(ticker, session):
    """
    Gets the current price of a ticker based on the market session.
    """
    try:
        stock_info = yf.Ticker(ticker).info
        ask_price = stock_info.get('ask')
        if ask_price:
            return ask_price
        elif session == 'pre-market':
            return stock_info.get('preMarketPrice')
        elif session == 'post-market':
            return stock_info.get('postMarketPrice')
        else:
            return stock_info.get('regularMarketPrice')
    except Exception as e:
        print(f"Could not get current price for {ticker}: {e}")
        return None

def check_stock_price_change(verbose=False, apilog=False):
    """
    Checks for unusual price changes in stocks listed in watchlist.txt.
    """
    watchlist = parse_watchlist()
    if not watchlist:
        print("Watchlist is empty or not found.")
        return

    session = get_market_session()

    if session == 'closed':
        print("Market is closed. No checks will be performed.")
        return

    print(f"Checking {session} prices...")

    for ticker, config in watchlist.items():
        threshold = config["threshold"]
        direction = config["direction"]
        price_below = config["price_below"]
        price_above = config["price_above"]
        alert_frequency = config["alert_frequency"]

        current_price = get_current_price(ticker, session)

        if current_price is None:
            print(f"Could not get current price for {ticker}, skipping.")
            continue

        # Get previous day's close
        try:
            if apilog:
                log_api(f"Request: yf.download(ticker={ticker}, period=\"2d\")")
            data = yf.download(ticker, period="2d", auto_adjust=True, progress=False)
            if apilog:
                log_api(f"Response: Received {len(data)} rows of data.")
            
            if data.empty or len(data) < 2:
                print(f"Could not get enough historical data for {ticker}, skipping.")
                continue

            previous_close = data['Close'].iloc[-2].item()
        except Exception as e:
            print(f"Could not get previous day's close for {ticker}: {e}")
            continue

        percent_change = ((current_price - previous_close) / previous_close) * 100

        if verbose:
            print(f"--- {ticker} ---")
            print(f"Previous Close: {previous_close:.2f}")
            print(f"Current Price: {current_price:.2f}")
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
            message = f"Unusual price change detected for {ticker}: {'+' if percent_change > 0 else ''}{percent_change:.2f}% (Threshold: {threshold}%, Direction: {direction}). Current Price: {current_price:.2f}"
            log_alert(message, ticker, alert_frequency)

        # Price target alerts
        if price_below is not None and current_price < price_below:
            message = f"{ticker} has dropped below your target of {price_below:.2f}. Current price: {current_price:.2f}"
            log_alert(message, ticker, alert_frequency)
        
        if price_above is not None and current_price > price_above:
            message = f"{ticker} has gone above your target of {price_above:.2f}. Current price: {current_price:.2f}"
            log_alert(message, ticker, alert_frequency)

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
