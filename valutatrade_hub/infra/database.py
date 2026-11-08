import json
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar

T = TypeVar("T")

class DatabaseManager:
    """
    Singleton-менеджер для работы с JSON-хранилищем.
    Отвечает за безопасное чтение/запись users.json, portfolios.json, rates.json.
    """

    _instance: Optional["DatabaseManager"] = None

    def __new__(cls, data_dir: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Инициализация при первом создании
            cls._instance._initialized = False
            cls._instance.data_dir = Path(data_dir) if data_dir else Path("data")
            cls._instance._ensure_dirs()
        return cls._instance

    def _ensure_dirs(self) -> None:
        """Создать директорию data, если её нет."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def users_path(self) -> Path:
        return self.data_dir / "users.json"

    @property
    def portfolios_path(self) -> Path:
        return self.data_dir / "portfolios.json"

    @property
    def rates_path(self) -> Path:
        return self.data_dir / "rates.json"

    # ------------------------------------------------------------------
    # Базовые операции: load / save
    # ------------------------------------------------------------------

    def load_json(self, path: Path, default: T) -> T:
        """Безопасно загрузить JSON. Если файла нет — вернуть default."""
        if not path.exists():
            return default
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                # Простая валидация: если не список/словарь, вернём default
                if isinstance(default, list) and not isinstance(data, list):
                    return default
                if isinstance(default, dict) and not isinstance(data, dict):
                    return default
                return data  # type: ignore
        except (json.JSONDecodeError, IOError):
            # При ошибке чтения — возвращаем пустую структуру (защита от падения)
            return default

    def save_json(self, path: Path, data: Any) -> None:
        """Сохранить JSON с отступами и UTF-8."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Обертки под сущности (users, portfolios, rates)
    # ------------------------------------------------------------------

    def get_users(self) -> List[Dict[str, Any]]:
        return self.load_json(self.users_path, [])

    def save_users(self, users: List[Dict[str, Any]]) -> None:
        self.save_json(self.users_path, users)

    def get_portfolios(self) -> List[Dict[str, Any]]:
        return self.load_json(self.portfolios_path, [])

    def save_portfolios(self, portfolios: List[Dict[str, Any]]) -> None:
        self.save_json(self.portfolios_path, portfolios)

    def get_rates(self) -> Dict[str, Any]:
        return self.load_json(self.rates_path, {})

    def save_rates(self, rates: Dict[str, Any]) -> None:
        self.save_json(self.rates_path, rates)

    # ------------------------------------------------------------------
    # Вспомогательные CRUD-методы (чтобы в CLI/usecases не дублировать логику)
    # ------------------------------------------------------------------

    def find_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        users = self.get_users()
        for u in users:
            if u.get("username") == username:
                return u
        return None

    def add_user(self, user_dict: Dict[str, Any]) -> None:
        users = self.get_users()
        # Проверка уникальности user_id (простая автоинкрементная логика)
        max_id = 0
        for u in users:
            uid = u.get("user_id", 0)
            if uid > max_id:
                max_id = uid
        user_dict["user_id"] = max_id + 1
        users.append(user_dict)
        self.save_users(users)

    def find_portfolio_by_user_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        portfolios = self.get_portfolios()
        for p in portfolios:
            if p.get("user_id") == user_id:
                return p
        return None

    def upsert_portfolio(self, portfolio_dict: Dict[str, Any]) -> None:
        portfolios = self.get_portfolios()
        user_id = portfolio_dict.get("user_id")
        # Ищем существующий
        found = False
        for i, p in enumerate(portfolios):
            if p.get("user_id") == user_id:
                portfolios[i] = portfolio_dict
                found = True
                break
        if not found:
            portfolios.append(portfolio_dict)
        self.save_portfolios(portfolios)

