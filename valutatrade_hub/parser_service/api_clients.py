from abc import ABC, abstractmethod
from typing import Dict

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    name: str = "base"

    @abstractmethod
    def fetch_rates(self) -> Dict[str, float]:
        pass


class CoinGeckoClient(BaseApiClient):
    name = "coingecko"

    def __init__(self, config: ParserConfig):
        self.config = config

    def fetch_rates(self) -> Dict[str, float]:
        ids = ",".join(
            self.config.CRYPTO_ID_MAP[code] for code in self.config.CRYPTO_CURRENCIES
        )
        try:
            response = requests.get(
                self.config.COINGECKO_URL,
                params={"ids": ids, "vs_currencies": "usd"},
                timeout=self.config.REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(f"CoinGecko: сетевая ошибка ({exc})")

        if response.status_code != 200:
            raise ApiRequestError(f"CoinGecko: HTTP {response.status_code}")

        try:
            data = response.json()
        except ValueError:
            raise ApiRequestError("CoinGecko: некорректный JSON в ответе")

        result: Dict[str, float] = {}
        for code, coin_id in self.config.CRYPTO_ID_MAP.items():
            usd = data.get(coin_id, {}).get("usd")
            if isinstance(usd, (int, float)):
                result[f"{code}_USD"] = float(usd)
        return result


class ExchangeRateApiClient(BaseApiClient):
    """Курсы фиатных валют. Требует API-ключ."""

    name = "exchangerate"

    def __init__(self, config: ParserConfig):
        self.config = config

    def fetch_rates(self) -> Dict[str, float]:
        if not self.config.EXCHANGERATE_API_KEY:
            raise ApiRequestError(
                "ExchangeRate-API: ключ не задан "
                "(переменная окружения EXCHANGERATE_API_KEY)"
            )

        url = (
            f"{self.config.EXCHANGERATE_API_URL}/"
            f"{self.config.EXCHANGERATE_API_KEY}/latest/{self.config.BASE_CURRENCY}"
        )
        try:
            response = requests.get(url, timeout=self.config.REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(f"ExchangeRate-API: сетевая ошибка ({exc})")

        if response.status_code == 401:
            raise ApiRequestError("ExchangeRate-API: неверный API-ключ")
        if response.status_code == 429:
            raise ApiRequestError("ExchangeRate-API: превышен лимит запросов (429)")
        if response.status_code != 200:
            raise ApiRequestError(f"ExchangeRate-API: HTTP {response.status_code}")

        try:
            data = response.json()
        except ValueError:
            raise ApiRequestError("ExchangeRate-API: некорректный JSON в ответе")

        if data.get("result") != "success":
            raise ApiRequestError(
                f"ExchangeRate-API: ответ со статусом '{data.get('result')}'"
            )

        rates = data.get("conversion_rates", {})
        result: Dict[str, float] = {}
        for code in self.config.FIAT_CURRENCIES:
            per_usd = rates.get(code)
            if isinstance(per_usd, (int, float)) and per_usd > 0:
                result[f"{code}_USD"] = round(1.0 / float(per_usd), 8)
        return result

