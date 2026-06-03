from copy import deepcopy


class FakeLiveMarketDataProvider:
    def __init__(self):
        self.prices = {
            "AAPL": 215.18,
            "MSFT": 449.87,
            "BND": 72.50,
            "JPM": 250.41,
            "NVDA": 135.92,
            "GME": 30.30,
            "600519.SH": 1520.00,
            "000001.SZ": 10.50,
            "0700.HK": 456.40,
            "9988.HK": 119.30,
            "SPX_20260619_6000C": 12.50,
            "STRUCT_NOTE_NDX_BUFFER_2027": 1000.00,
        }
        self.sectors = {
            "AAPL": "Information Technology",
            "MSFT": "Information Technology",
            "BND": "Fixed Income",
            "JPM": "Financials",
            "NVDA": "Information Technology",
            "GME": "Consumer Discretionary",
            "600519.SH": "Consumer Staples",
            "000001.SZ": "Financials",
            "0700.HK": "Communication Services",
            "9988.HK": "Consumer Discretionary",
        }
        self.risk = {
            "AAPL": {"annual_volatility": 0.22, "market_beta": 1.15},
            "MSFT": {"annual_volatility": 0.20, "market_beta": 1.10},
            "BND": {"annual_volatility": 0.06, "market_beta": 0.10},
            "JPM": {"annual_volatility": 0.26, "market_beta": 1.05},
            "NVDA": {"annual_volatility": 0.38, "market_beta": 1.30},
            "GME": {"annual_volatility": 0.70, "market_beta": 1.45},
            "600519.SH": {"annual_volatility": 0.28, "market_beta": 1.00},
            "000001.SZ": {"annual_volatility": 0.32, "market_beta": 1.05},
            "0700.HK": {"annual_volatility": 0.34, "market_beta": 1.10},
            "9988.HK": {"annual_volatility": 0.40, "market_beta": 1.20},
        }

    def get_market_price(self, ticker: str, as_of_date: str | None = None) -> dict:
        ticker = ticker.upper()
        price_date = as_of_date or "2026-05-15"
        data_source = self._data_source("market_price", price_date, self._provider(ticker), ticker)
        return {
            "ticker": ticker,
            "date": price_date,
            "open": self.prices[ticker],
            "high": self.prices[ticker],
            "low": self.prices[ticker],
            "close": self.prices[ticker],
            "volume": 1000000,
            "currency": self._currency(ticker),
            "data_source": data_source,
        }

    def get_price_history(self, ticker: str, start_date: str, end_date: str) -> dict:
        ticker = ticker.upper()
        data_source = self._data_source("historical_prices", end_date, self._provider(ticker), ticker)
        return {
            "ticker": ticker,
            "currency": self._currency(ticker),
            "prices": [
                {
                    "date": end_date,
                    "open": self.prices[ticker],
                    "high": self.prices[ticker],
                    "low": self.prices[ticker],
                    "close": self.prices[ticker],
                    "volume": 1000000,
                }
            ],
            "data_source": data_source,
        }

    def get_company_fundamentals(self, ticker: str) -> dict:
        ticker = ticker.upper()
        data_source = self._data_source("company_fundamentals", "2026-05-15", self._provider(ticker), ticker)
        return {
            "ticker": ticker,
            "company_name": f"{ticker} Test Company",
            "sector": self.sectors.get(ticker, "Information Technology"),
            "industry": "Test Industry",
            "currency": self._currency(ticker),
            "statements": {
                "income": {
                    "FY2025": {
                        "revenue": 1000000000.0,
                        "net_income": 100000000.0,
                    }
                },
                "balance_sheet": {
                    "FY2025": {
                        "total_assets": 2000000000.0,
                        "total_liabilities": 1000000000.0,
                    }
                },
            },
            "valuation_multiples": {
                "2026-05-15": {
                    "price_to_earnings": 31.4,
                    "price_to_sales": 7.5,
                }
            },
            "data_source": data_source,
        }

    def get_live_ticker_risk(self, ticker: str) -> dict:
        ticker = ticker.upper()
        values = self.risk.get(ticker, {"annual_volatility": 0.30, "market_beta": 1.0})
        data_source = self._data_source("derived_ticker_risk", "2026-05-15", self._provider(ticker), ticker)
        return {
            "ticker": ticker,
            "annual_volatility": values["annual_volatility"],
            "market_beta": values["market_beta"],
            "factors": {
                "market_beta": values["market_beta"],
                "size": 0.0,
                "value": 0.0,
                "momentum": 0.0,
            },
            "data_source": data_source,
        }

    @staticmethod
    def _currency(ticker: str) -> str:
        if ticker.endswith(".SH") or ticker.endswith(".SZ"):
            return "CNY"
        if ticker.endswith(".HK"):
            return "HKD"
        return "USD"

    @staticmethod
    def _provider(ticker: str) -> str:
        return "akshare" if ticker.endswith((".SH", ".SZ", ".HK")) else "fmp"

    @staticmethod
    def _data_source(dataset: str, data_date: str, provider: str = "fmp", ticker: str = "") -> dict:
        return deepcopy({
            "data_source_id": f"live:{provider}:{dataset}:{ticker}:{data_date}",
            "data_source_type": "live_provider",
            "provider": provider,
            "dataset": dataset,
            "ticker": ticker,
            "data_date": data_date,
            "retrieved_at": "2026-05-15T00:00:00+00:00",
            "payload_sha256": "fake",
        })
