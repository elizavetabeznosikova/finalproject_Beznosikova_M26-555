import json
from pathlib import Path
from typing import Any, Dict, Optional

from valutatrade_hub.logging_config import setup_logging

logger = setup_logging()

DEFAULTS: Dict[str, Any] = {
    "data_dir": "data",
    "users_file": "data/users.json",
    "portfolios_file": "data/portfolios.json",
    "rates_file": "data/rates.json",
    "history_file": "data/exchange_rates.json",
    "rates_ttl_seconds": 300,       # срок годности кеша курсов: 5 минут
    "base_currency": "USD",
    "log_level": "INFO",
    "log_file": "logs/actions.log",
    "log_max_bytes": 1_000_000,
    "log_backup_count": 5,
}


class SettingsLoader:
    _instance: Optional["SettingsLoader"] = None

    def __new__(cls) -> "SettingsLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        # Повторные вызовы SettingsLoader() не перечитывают конфиг —
        # это видно по _initialized, чтобы избежать лишнего IO
        if self._initialized:
            return
        self._config: Dict[str, Any] = dict(DEFAULTS)
        self._load()
        self._initialized = True

    def _load(self) -> None:
        path = Path("config.json")
        if not path.exists():
            logger.info(
                "config.json не найден — используются значения по умолчанию"
            )
            return
        try:
            with path.open("r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            if isinstance(user_cfg, dict):
                self._config.update(user_cfg)
            else:
                logger.warning("config.json должен быть JSON-объектом")
        except (json.JSONDecodeError, IOError) as exc:
            logger.warning("Не удалось прочитать config.json: %s", exc)

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def reload(self) -> None:
        """Перечитывает config.json (удобно при ручной правке настроек)."""
        self._load()
        logger.info("Конфигурация перезагружена")

