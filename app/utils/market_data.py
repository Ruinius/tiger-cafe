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


def get_currency_rate(from_currency: str, to_currency: str = "USD") -> Decimal:
    """
    Fetch the exchange rate from Yahoo Finance.
    e.g. from_currency="CNY", to_currency="USD" -> Ticker "CNYUSD=X"
    Returns Decimal("1.0") if failed or if currencies match.
    """
    print(
        f"[get_currency_rate] Called with from_currency={from_currency}, to_currency={to_currency}"
    )

    if not from_currency or from_currency.upper() == to_currency.upper():
        print("[get_currency_rate] Currencies match or from_currency is empty, returning 1.0")
        return Decimal("1.0")

    # Map common currency aliases to Yahoo Finance codes
    currency_aliases = {
        "RMB": "CNY",  # Chinese Yuan Renminbi
    }

    # Normalize currency codes
    from_curr = currency_aliases.get(from_currency.upper(), from_currency.upper())
    to_curr = currency_aliases.get(to_currency.upper(), to_currency.upper())

    print(
        f"[get_currency_rate] Normalized: {from_currency} -> {from_curr}, {to_currency} -> {to_curr}"
    )

    try:
        # Ticker format usually "EURUSD=X"
        ticker = f"{from_curr}{to_curr}=X"
        print(f"[get_currency_rate] Fetching ticker: {ticker}")

        data = yf.Ticker(ticker)

        # Try fast_info first
        price = getattr(data.fast_info, "last_price", None)
        print(f"[get_currency_rate] fast_info.last_price = {price}")

        if price is None:
            # Fallback to history
            print("[get_currency_rate] fast_info failed, trying history...")
            hist = data.history(period="1d")
            print(f"[get_currency_rate] History data: {hist}")
            if not hist.empty:
                price = hist["Close"].iloc[-1]
                print(f"[get_currency_rate] Got price from history: {price}")

        if price:
            result = Decimal(str(price))
            print(f"[get_currency_rate] Successfully fetched rate: {result}")
            return result

        print("[get_currency_rate] No price found, returning default 1.0")
        return Decimal("1.0")
    except Exception as e:
        print(
            f"[get_currency_rate] ERROR fetching currency rate for {from_currency}/{to_currency}: {e}"
        )
        import traceback

        traceback.print_exc()
        return Decimal("1.0")
