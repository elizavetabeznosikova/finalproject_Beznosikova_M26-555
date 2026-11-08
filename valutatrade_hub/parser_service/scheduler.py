import time

from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater

logger = setup_logging()


def build_updater() -> RatesUpdater:
    config = ParserConfig()
    storage = RatesStorage(config.RATES_FILE_PATH, config.HISTORY_FILE_PATH)
    clients = [CoinGeckoClient(config)]
    try:
        clients.append(ExchangeRateApiClient(config))
    except Exception:
        pass
    return RatesUpdater(clients, storage)


def run_forever(interval_seconds: int = 300) -> None:
    """Обновляет курсы каждые interval_seconds секунд до прерывания (Ctrl+C)."""
    updater = build_updater()
    logger.info("Планировщик запущен: интервал %d сек", interval_seconds)
    while True:
        try:
            updater.run_update()
        except Exception as exc:  # планировщик не должен падать
            logger.error("Сбой цикла обновления: %s", exc)
        time.sleep(interval_seconds)


if __name__ == "__main__":
    try:
        run_forever()
    except KeyboardInterrupt:
        logger.info("Планировщик остановлен")

