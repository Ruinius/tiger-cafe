import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import yfinance as yf

# Cache configuration
CACHE_DIR = Path("data/cache/yfinance")
CACHE_EXPIRY_HOURS = 24


def _get_cache_path(cache_key: str) -> Path:
    """Get the cache file path for a given key."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Sanitize the key to be filesystem-safe
    safe_key = cache_key.replace("/", "_").replace("\\", "_").replace(":", "_")
    return CACHE_DIR / f"{safe_key}.json"


def _get_cached_value(cache_key: str):
    """
    Retrieve a cached value if it exists and hasn't expired.
    Returns None if cache miss or expired.
    """
    cache_path = _get_cache_path(cache_key)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path) as f:
            cache_data = json.load(f)

        # Check expiration
        cached_time = datetime.fromisoformat(cache_data["timestamp"])
        expiry_time = cached_time + timedelta(hours=CACHE_EXPIRY_HOURS)

        if datetime.now() < expiry_time:
            print(f"[CACHE HIT] {cache_key}")
            return cache_data["value"]
        else:
            print(f"[CACHE EXPIRED] {cache_key}")
            return None
    except Exception as e:
        print(f"[CACHE ERROR] Failed to read cache for {cache_key}: {e}")
        return None


def _set_cached_value(cache_key: str, value):
    """
    Store a value in the cache with current timestamp.
    """
    cache_path = _get_cache_path(cache_key)

    try:
        cache_data = {"timestamp": datetime.now().isoformat(), "value": value}
        with open(cache_path, "w") as f:
            json.dump(cache_data, f, indent=2)
        print(f"[CACHE SET] {cache_key}")
    except Exception as e:
        print(f"[CACHE ERROR] Failed to write cache for {cache_key}: {e}")


def get_latest_share_price(ticker: str) -> Decimal:
    """
    Fetch the latest share price for a given ticker from Yahoo Finance.
    Returns Decimal("0") if failed.
    Uses 24-hour cache to prevent throttling.
    """
    if not ticker:
        return Decimal("0")

    # Check cache first
    cache_key = f"price_{ticker}"
    cached = _get_cached_value(cache_key)
    if cached is not None:
        return Decimal(str(cached))

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
            # Cache the result
            _set_cached_value(cache_key, float(price))
            return Decimal(str(price))

        return Decimal("0")
    except Exception as e:
        print(f"Error fetching share price for {ticker}: {e}")
        return Decimal("0")


def get_beta(ticker: str) -> Decimal:
    """
    Fetch the beta for a given ticker from Yahoo Finance.
    Returns Decimal("1.0") if failed (market beta).
    Uses 24-hour cache to prevent throttling.
    """
    if not ticker:
        return Decimal("1.0")

    # Check cache first
    cache_key = f"beta_{ticker}"
    cached = _get_cached_value(cache_key)
    if cached is not None:
        return Decimal(str(cached))

    try:
        ticker_obj = yf.Ticker(ticker)

        # Try to get beta from info
        info = ticker_obj.info
        beta = info.get("beta")

        if beta is not None:
            # Cache the result
            _set_cached_value(cache_key, float(beta))
            return Decimal(str(beta))

        return Decimal("1.0")  # Default to market beta
    except Exception as e:
        print(f"Error fetching beta for {ticker}: {e}")
        return Decimal("1.0")


def get_market_cap(ticker: str) -> Decimal:
    """
    Fetch the market capitalization for a given ticker from Yahoo Finance.
    Returns Decimal("0") if failed.
    Uses 24-hour cache to prevent throttling.
    """
    if not ticker:
        return Decimal("0")

    # Check cache first
    cache_key = f"market_cap_{ticker}"
    cached = _get_cached_value(cache_key)
    if cached is not None:
        return Decimal(str(cached))

    try:
        ticker_obj = yf.Ticker(ticker)

        # Try to get market cap from fast_info or info
        mkt_cap = getattr(ticker_obj.fast_info, "market_cap", None)

        if mkt_cap is None:
            info = ticker_obj.info
            mkt_cap = info.get("marketCap")

        if mkt_cap is not None:
            # Cache the result
            _set_cached_value(cache_key, float(mkt_cap))
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

    # Check cache first
    cache_key = f"currency_{from_curr}_{to_curr}"
    cached = _get_cached_value(cache_key)
    if cached is not None:
        print(f"[get_currency_rate] Returning cached rate: {cached}")
        return Decimal(str(cached))

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
            # Cache the result
            _set_cached_value(cache_key, float(price))
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
