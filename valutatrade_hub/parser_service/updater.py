import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.parser_service.api_clients import BaseApiClient
from valutatrade_hub.parser_service.storage import RatesStorage

logger = setup_logging()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RatesUpdater:
    def __init__(self, clients: List[BaseApiClient], storage: RatesStorage):
        self.clients = clients
        self.storage = storage

    def run_update(self, source: Optional[str] = None) -> Dict[str, Any]:
        logger.info(
            "Parser Service: старт обновления курсов (source=%s)", source or "все"
        )
        timestamp = _utc_now_iso()

        merged: Dict[str, Dict[str, Any]] = {}
        history_records: List[Dict[str, Any]] = []
        errors: List[str] = []

        for client in self.clients:
            if source and client.name.lower() != source.lower():
                continue

            started = time.perf_counter()
            try:
                rates = client.fetch_rates()
            except ApiRequestError as exc:
                logger.error("Ошибка при получении курсов от %s: %s", client.name, exc)
                errors.append(f"{client.name}: {exc}")
                continue

            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "Получено курсов от %s: %d (%.0f мс)",
                client.name,
                len(rates),
                elapsed_ms,
            )

            for pair, rate in rates.items():
                record_id = f"{pair}_{timestamp}"
                merged[pair] = {
                    "rate": rate,
                    "updated_at": timestamp,
                    "source": client.name,
                }
                history_records.append(
                    {
                        "id": record_id,
                        "from_currency": pair.split("_")[0],
                        "to_currency": pair.split("_")[1],
                        "rate": rate,
                        "timestamp": timestamp,
                        "source": client.name,
                        "meta": {
                            "request_ms": round(elapsed_ms),
                            "status_code": 200,
                        },
                    }
                )

        added = 0
        if merged:
            added = self.storage.append_history(history_records)
            self.storage.update_snapshot(merged)
            logger.info("Записано в историю: %d, в кеш: %d пар", added, len(merged))
        else:
            logger.warning("Ни один клиент не вернул данные — снимок не обновлён")

        return {
            "updated": len(merged),
            "last_refresh": timestamp,
            "errors": errors,
        }

