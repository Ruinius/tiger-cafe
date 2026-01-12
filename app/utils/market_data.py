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


def get_beta(ticker: str) -> Decimal:
    """
    Fetch the beta for a given ticker from Yahoo Finance.
    Returns Decimal("1.0") if failed (market beta).
    """
    if not ticker:
        return Decimal("1.0")

    try:
        ticker_obj = yf.Ticker(ticker)

        # Try to get beta from info
        info = ticker_obj.info
        beta = info.get("beta")

        if beta is not None:
            return Decimal(str(beta))

        return Decimal("1.0")  # Default to market beta
    except Exception as e:
        print(f"Error fetching beta for {ticker}: {e}")
        return Decimal("1.0")


def get_market_cap(ticker: str) -> Decimal:
    """
    Fetch the market capitalization for a given ticker from Yahoo Finance.
    Returns Decimal("0") if failed.
    """
    if not ticker:
        return Decimal("0")

    try:
        ticker_obj = yf.Ticker(ticker)

        # Try to get market cap from fast_info or info
        mkt_cap = getattr(ticker_obj.fast_info, "market_cap", None)

        if mkt_cap is None:
            info = ticker_obj.info
            mkt_cap = info.get("marketCap")

        if mkt_cap is not None:
            return Decimal(str(mkt_cap))

        return Decimal("0")
    except Exception as e:
        print(f"Error fetching market cap for {ticker}: {e}")
        return Decimal("0")
