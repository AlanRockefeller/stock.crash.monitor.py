# Stock Crash Monitor

This program helps keep an eye on stock prices and sends you an audible notification on your phone if something interesting happens.

## How it works

This script fetches the latest stock data from Yahoo Finance and checks for two things:

1.  **Sudden price changes:** It looks at the percentage change between the last two data points (e.g., in a 5-minute interval) and alerts you if it's above a certain threshold.
2.  **Price targets:** It can also notify you if a stock goes above or below a specific price that you've set.

When an alert is triggered, the script will print a message to the console, log it to `stock_monitor.log`, and send you a push notification via Pushover.  The Pushover app on your phone can instantly alert you.

The Yahoo Finance API allows 8000 requests per day per IP, so you should be fine running this script even every minute via cron.

## Setup

1.  **Install the dependencies:**
    ```bash
    pip install yfinance requests pandas
    ```

2.  **Create your watchlist:**
    Create a file named `watchlist.txt` in the same directory as the script. This is where you'll list the stocks you want to monitor. See the "The `watchlist.txt` file" section below for more details.

3.  **Enable cron**
    Set up a cron job to run this code periodically.    
    My crontab line is:
    * * * * * /home/alan/stock.crash.monitor/stock_monitor.py

3.  **Set up Pushover (optional):**
    If you want to receive push notifications, you'll need to get a Pushover User Key and API Token.
    -   Go to [pushover.net](https://pushover.net) and create an account if you don't have one.
    -   Create a new application to get an API token.
    -   Find your User Key on your Pushover dashboard.
    -   Open `stock_monitor.py` and replace the placeholder values for `PUSHOVER_USER_KEY` and `PUSHOVER_API_TOKEN` with your own.

## Usage

You can run the script from your terminal:

```bash
python stock_monitor.py
```

By default, it will check the stocks in your watchlist once. You can set up a cron job or a similar scheduler to run it at regular intervals.

### Options

-   `-v`, `--verbose`: Print detailed stock data, including the prices and percentage change.
-   `--analyze`: Analyze the stocks in your watchlist to see how many alerts would have been triggered in the last month at different thresholds. Very useful for tuning your thresholds.
-   `--testpush`: Send a test notification to Pushover to check if your configuration is correct.
-   `--apilog`: Log API calls to api_log.txt

## The `watchlist.txt` file

This file is the heart of the monitor. It's a CSV file where each line represents a stock you want to watch. The format is:

`TICKER,THRESHOLD,DIRECTION,PRICE_BELOW,PRICE_ABOVE`

-   `TICKER`: The stock ticker symbol (e.g., `NVDA`, `^DJI`).
-   `THRESHOLD`: The percentage change that will trigger an alert.
-   `DIRECTION`: The direction of the change that you care about.
    -   `both`: Alert on both gains and drops.
    -   `gain`: Alert only on gains.
    -   `drop`: Alert only on drops.
-   `PRICE_BELOW`: (Optional) The price below which you want to be notified.
-   `PRICE_ABOVE`: (Optional) The price above which you want to be notified.

### Examples

Here's an example of what your `watchlist.txt` might look like:

```
TICKER,THRESHOLD,DIRECTION,PRICE_BELOW,PRICE_ABOVE
^DJI,0.5,both,,
NVDA,1.5,both,400,500
MLTX,2.0,drop,10,
GOOG,1.0,both,170,180
```

-   `^DJI`: Will trigger an alert if the Dow Jones Industrial Average moves more than 0.5% in either direction.
-   `NVDA`: Will trigger an alert if NVIDIA's stock price moves more than 1.5% in either direction, or if it drops below $400 or goes above $500.
-   `MLTX`: Will trigger an alert if MLTX stock price drops more than 2.0%, or if it drops below $10.
-   `GOOG`: Will trigger an alert if Google's stock price moves more than 1.0% in either direction, or if it drops below $170 or goes above $180.

### Github

- http://github.com/AlanRockefeller/stock.crash.monitor.py

### License

Distributed under the MIT license.
