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
            return cache_data["value"]
        else:
            return None
    except Exception:
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
    except Exception:
        pass


def get_latest_share_price(ticker: str) -> tuple[Decimal, str]:
    """
    Fetch the latest share price and currency for a given ticker from Yahoo Finance.
    Returns (Decimal("0"), "USD") if failed.
    Uses 24-hour cache to prevent throttling.
    """
    if not ticker:
        return Decimal("0"), "USD"

    # Check cache first
    cache_key = f"price_v2_{ticker}"
    cached = _get_cached_value(cache_key)
    if cached is not None:
        # cache value is now a dict { "price": float, "currency": str }
        return Decimal(str(cached.get("price", 0))), cached.get("currency", "USD")

    try:
        # Use yfinance to get ticker data
        ticker_obj = yf.Ticker(ticker)

        # Try to get fast info first (often faster/more reliable for price)
        price = getattr(ticker_obj.fast_info, "last_price", None)
        currency = getattr(ticker_obj.fast_info, "currency", None)

        if price is None:
            # Fallback to history
            hist = ticker_obj.history(period="1d")
            if not hist.empty:
                price = hist["Close"].iloc[-1]

        if currency is None:
            # Fallback to info
            currency = ticker_obj.info.get("currency", "USD")

        if price is not None:
            # Cache the result as a dict
            cache_val = {"price": float(price), "currency": currency or "USD"}
            _set_cached_value(cache_key, cache_val)
            return Decimal(str(price)), currency or "USD"

        return Decimal("0"), "USD"
    except Exception:
        return Decimal("0"), "USD"


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
    except Exception:
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
    except Exception:
        return Decimal("0")


def get_currency_rate(from_currency: str, to_currency: str = "USD") -> Decimal:
    """
    Fetch the exchange rate from Yahoo Finance.
    e.g. from_currency="CNY", to_currency="USD" -> Ticker "CNYUSD=X"
    Returns Decimal("1.0") if failed or if currencies match.
    """
    if not from_currency or from_currency.upper() == to_currency.upper():
        return Decimal("1.0")

    # Map common currency aliases to Yahoo Finance codes
    currency_aliases = {
        "RMB": "CNY",  # Chinese Yuan Renminbi
    }

    # Normalize currency codes
    from_curr = currency_aliases.get(from_currency.upper(), from_currency.upper())
    to_curr = currency_aliases.get(to_currency.upper(), to_currency.upper())

    # Check cache first
    cache_key = f"currency_{from_curr}_{to_curr}"
    cached = _get_cached_value(cache_key)
    if cached is not None:
        return Decimal(str(cached))

    try:
        # Ticker format usually "EURUSD=X"
        ticker = f"{from_curr}{to_curr}=X"

        data = yf.Ticker(ticker)

        # Try fast_info first
        price = getattr(data.fast_info, "last_price", None)

        if price is None:
            # Fallback to history
            hist = data.history(period="1d")
            if not hist.empty:
                price = hist["Close"].iloc[-1]

        if price:
            # Cache the result
            _set_cached_value(cache_key, float(price))
            result = Decimal(str(price))
            return result

        return Decimal("1.0")
    except Exception:
        return Decimal("1.0")


def get_yahoo_company_info(ticker: str) -> str | None:
    """
    Fetch the shortName for a given ticker from Yahoo Finance.
    Falls back to longName if shortName is not available.
    Returns None if the lookup fails for any reason.
    Uses 24-hour cache to prevent throttling.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL")

    Returns:
        Yahoo Finance shortName (or longName) string, or None on failure
    """
    if not ticker:
        return None

    cache_key = f"shortname_{ticker}"
    cached = _get_cached_value(cache_key)
    if cached is not None:
        return cached

    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        short_name = info.get("shortName") or info.get("longName")
        if short_name:
            _set_cached_value(cache_key, short_name)
            return short_name
        return None
    except Exception:
        return None
