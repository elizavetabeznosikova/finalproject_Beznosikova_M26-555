from abc import ABC, abstractmethod
from typing import Dict

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    def __init__(self, code: str, name: str):
        code = code.strip()

        if not code:
            raise ValueError("Код валюты не может быть пустым.")
        if not code.isupper():
            raise ValueError(f"Код валюты '{code}' должен быть в верхнем регистре.")
        if not (2 <= len(code) <= 5):
            raise ValueError(
                f"Код валюты '{code}' должен быть от 2 до 5 символов."
            )
        if any(ch.isspace() for ch in code):
            raise ValueError(f"Код валюты '{code}' не должен содержать пробелов.")

        if not name or not name.strip():
            raise ValueError("Название валюты не может быть пустым.")

        self.code = code
        self.name = name.strip()

    @abstractmethod
    def get_display_info(self) -> str:
        """Строковое представление валюты для UI/логов."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code='{self.code}', name='{self.name}')"


class FiatCurrency(Currency):
    def __init__(self, code: str, name: str, issuing_country: str):
        super().__init__(code, name)
        if not issuing_country or not issuing_country.strip():
            raise ValueError("Страна/зона эмиссии не может быть пустой.")
        self.issuing_country = issuing_country.strip()

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    def __init__(self, code: str, name: str, algorithm: str, market_cap: float):
        super().__init__(code, name)
        if not algorithm or not algorithm.strip():
            raise ValueError("Алгоритм не может быть пустым.")
        if market_cap < 0:
            raise ValueError("Капитализация не может быть отрицательной.")
        self.algorithm = algorithm.strip()
        self.market_cap = market_cap

    def get_display_info(self) -> str:
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"
        )


CURRENCIES: Dict[str, Currency] = {
    "USD": FiatCurrency("USD", "US Dollar", "United States"),
    "EUR": FiatCurrency("EUR", "Euro", "Eurozone"),
    "GBP": FiatCurrency("GBP", "British Pound", "United Kingdom"),
    "RUB": FiatCurrency("RUB", "Russian Ruble", "Russia"),
    "BTC": CryptoCurrency("BTC", "Bitcoin", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("ETH", "Ethereum", "Ethash", 4.20e11),
    "SOL": CryptoCurrency("SOL", "Solana", "Proof of History", 6.50e10),
}


def get_currency(code: str) -> Currency:
    if not code or not code.strip():
        raise CurrencyNotFoundError(code)

    normalized = code.strip().upper()
    currency = CURRENCIES.get(normalized)
    if currency is None:
        raise CurrencyNotFoundError(normalized)
    return currency

