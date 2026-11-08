import hashlib
import os
from datetime import datetime
from typing import Any, Dict, Optional


class User:
    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ):
        self._user_id = user_id
        self._username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not value or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым.")
        self._username = value.strip()

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    @staticmethod
    def generate_salt() -> str:
        return os.urandom(16).hex()

    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    def verify_password(self, password: str) -> bool:
        candidate = self.hash_password(password, self._salt)
        return candidate == self._hashed_password

    def change_password(self, new_password: str) -> None:
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов.")
        new_salt = self.generate_salt()
        new_hash = self.hash_password(new_password, new_salt)

        self._salt = new_salt
        self._hashed_password = new_hash

    def get_user_info(self) -> Dict[str, Any]:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        reg_date = datetime.fromisoformat(data["registration_date"])
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=reg_date,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }


class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = currency_code.upper()
        self._balance = balance

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом.")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным.")
        self._balance = float(value)

    def deposit(self, amount: float) -> float:
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной.")
        self._balance += amount
        return self._balance

    def withdraw(self, amount: float) -> float:
        if amount <= 0:
            raise ValueError("Сумма снятия должна быть положительной.")
        if amount > self._balance:
            raise ValueError(
                f"Недостаточно средств: доступно {self._balance}, "
                f"требуется {amount}."
            )
        self._balance -= amount
        return self._balance

    def get_balance_info(self) -> Dict[str, Any]:
        return {
            "currency_code": self.currency_code,
            "balance": self._balance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Wallet":
        return cls(currency_code=data["currency_code"], balance=data["balance"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "currency_code": self.currency_code,
            "balance": self._balance,
        }


class Portfolio:
    def __init__(self, user_id: int):
        self._user_id = user_id
        self._wallets: Dict[str, Wallet] = {}

    @property
    def user(self) -> int:
        return self._user_id

    @property
    def wallets(self) -> Dict[str, Any]:
        return {code: w.get_balance_info() for code, w in self._wallets.items()}

    def add_currency(self, currency_code: str) -> Wallet:
        code = currency_code.upper()
        if code in self._wallets:
            return self._wallets[code]
        wallet = Wallet(currency_code=code, balance=0.0)
        self._wallets[code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Optional[Wallet]:
        return self._wallets.get(currency_code.upper())

    def get_total_value(
        self,
        base_currency: str = "USD",
        exchange_rates: Optional[Dict[str, float]] = None,
    ) -> float:
        base_currency = base_currency.upper()

        if exchange_rates is None:
            exchange_rates = {
                "BTC_USD": 59337.21,
                "ETH_USD": 3720.00,
                "EUR_USD": 1.0786,
                "RUB_USD": 0.01016,
            }

        total = 0.0
        for code, wallet in self._wallets.items():
            if wallet.balance == 0:
                continue
            pair = f"{code}_{base_currency}"
            rate = exchange_rates.get(pair)
            if rate is None:
                reverse_pair = f"{base_currency}_{code}"
                rev_rate = exchange_rates.get(reverse_pair)
                if rev_rate is not None and rev_rate > 0:
                    rate = 1.0 / rev_rate
                else:
                    continue
            total += wallet.balance * rate
        return total

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Portfolio":
        portfolio = cls(user_id=data["user_id"])
        for currency_code, wallet_data in data.get("wallets", {}).items():
            wallet = Wallet.from_dict(wallet_data)
            portfolio._wallets[currency_code.upper()] = wallet
        return portfolio

    def to_dict(self) -> Dict[str, Any]:
        wallets_data = {
            code: wallet.to_dict()
            for code, wallet in self._wallets.items()
        }
        return {
            "user_id": self._user_id,
            "wallets": wallets_data,
        }

