import yfinance as yf


def check_ticker_currency(ticker_symbol):
    print(f"Checking ticker: {ticker_symbol}")
    try:
        ticker = yf.Ticker(ticker_symbol)

        # Check info dict
        info = ticker.info
        currency = info.get("currency")
        financialCurrency = info.get("financialCurrency")
        print(f"Info Currency: {currency}")
        print(f"Info Financial Currency: {financialCurrency}")

        # Check fast_info if available (some versions of yfinance)
        if hasattr(ticker, "fast_info"):
            print(f"Fast Info Currency: {getattr(ticker.fast_info, 'currency', 'N/A')}")

        print("-" * 20)
    except Exception as e:
        print(f"Error checking {ticker_symbol}: {e}")


if __name__ == "__main__":
    check_ticker_currency("BIDU")  # NASDAQ listed ADR
    check_ticker_currency("0700.HK")  # Hong Kong listed
    check_ticker_currency("AAPL")  # US listed
