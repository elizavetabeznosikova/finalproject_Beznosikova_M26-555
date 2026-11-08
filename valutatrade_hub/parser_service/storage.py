"""
Хранилище Parser Service:
- exchange_rates.json — журнал всех измерений (история);
- rates.json — снимок последних курсов (кеш для Core Service).

Все записи атомарны: пишем во временный файл, затем os.replace().
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from valutatrade_hub.logging_config import setup_logging

logger = setup_logging()


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)  # атомарная замена на POSIX и Windows


class RatesStorage:
    def __init__(self, rates_path: str, history_path: str):
        self.rates_path = Path(rates_path)
        self.history_path = Path(history_path)

    # ------------------ История (exchange_rates.json) ------------------

    def load_history(self) -> List[Dict[str, Any]]:
        if not self.history_path.exists():
            return []
        try:
            with self.history_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            logger.warning(
                "История %s повреждена — начинаем с пустой",
                self.history_path,
            )
            return []

    def append_history(self, records: List[Dict[str, Any]]) -> int:
        """Добавляет записи в журнал. Дубликаты по id не пишутся.
        Возвращает число добавленных записей."""
        existing_ids = {r.get("id") for r in self.load_history()}
        fresh = [r for r in records if r.get("id") not in existing_ids]
        if not fresh:
            return 0
        history = self.load_history() + fresh
        _atomic_write_json(self.history_path, history)
        return len(fresh)

    # ------------------ Снимок (rates.json) ------------------

    def load_snapshot(self) -> Dict[str, Any]:
        if not self.rates_path.exists():
            return {"pairs": {}, "last_refresh": None}
        try:
            with self.rates_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"pairs": {}, "last_refresh": None}
        data.setdefault("pairs", {})
        return data

    def update_snapshot(self, new_pairs: Dict[str, Dict[str, Any]]) -> None:
        """
        Обновляет кеш. Правило из ТЗ: апдейт побеждает,
        если его updated_at свежее текущего значения пары.
        """
        snapshot = self.load_snapshot()
        pairs = snapshot["pairs"]

        for pair, entry in new_pairs.items():
            current = pairs.get(pair)
            if current is None or entry["updated_at"] > current.get(
                "updated_at", ""
            ):
                pairs[pair] = entry
            else:
                logger.info(
                    "Пара %s: пропуск — существующее значение свежее", pair
                )

        snapshot["last_refresh"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        _atomic_write_json(self.rates_path, snapshot)

