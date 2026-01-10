from decimal import Decimal

import yfinance as yf


def get_latest_share_price(ticker: str) -> Decimal:
    """
    Fetch the latest share price for a given ticker from Yahoo Finance.
    Returns Decimal("0") if failed.
    """
    if not ticker:
        return Decimal("0")

    try:
        # Use yfinance to get ticker data
        ticker_obj = yf.Ticker(ticker)

        # Try to get fast info first (often faster/more reliable for price)
        price = ticker_obj.fast_info.last_price

        if price is None:
            # Fallback to history
            hist = ticker_obj.history(period="1d")
            if not hist.empty:
                price = hist["Close"].iloc[-1]

        if price is not None:
            return Decimal(str(price))

        return Decimal("0")
    except Exception as e:
        print(f"Error fetching share price for {ticker}: {e}")
        return Decimal("0")
