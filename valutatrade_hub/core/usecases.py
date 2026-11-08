from datetime import datetime, timezone
from typing import Any, Dict

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    AuthenticationError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    UsernameTakenError,
    UserNotFoundError,
)
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater

logger = setup_logging()
settings = SettingsLoader()
db = DatabaseManager()

STARTING_BALANCE_USD: float = 1000.00  # стартовый капитал при регистрации (из ТЗ)


@log_action("REGISTER", verbose=True)
def register_user(username: str, password: str) -> User:
    """Регистрирует пользователя и создаёт его портфель со стартовым балансом.

    Ошибки: UsernameTakenError.
    """
    if db.find_user_by_username(username):
        raise UsernameTakenError(username)

    salt = User.generate_salt()
    pwd_hash = User.hash_password(password, salt)
    reg_date = datetime.now()

    db.add_user(
        {
            "username": username,
            "hashed_password": pwd_hash,
            "salt": salt,
            "registration_date": reg_date.isoformat(),
        }
    )

    stored = db.find_user_by_username(username)
    user = User(
        user_id=stored["user_id"],
        username=stored["username"],
        hashed_password=stored["hashed_password"],
        salt=stored["salt"],
        registration_date=datetime.fromisoformat(stored["registration_date"]),
    )

    portfolio = Portfolio(user_id=user.user_id)
    usd_wallet = portfolio.add_currency("USD")
    usd_wallet.deposit(STARTING_BALANCE_USD)
    db.upsert_portfolio(portfolio.to_dict())

    return user


@log_action("LOGIN", verbose=True)
def login_user(username: str, password: str) -> User:
    """
    Аутентифицирует пользователя: ищет по username и сверяет пароль.
    Ошибки: UserNotFoundError, AuthenticationError.
    """
    stored = db.find_user_by_username(username)
    if not stored:
        raise UserNotFoundError(username)

    user = User(
        user_id=stored["user_id"],
        username=stored["username"],
        hashed_password=stored["hashed_password"],
        salt=stored["salt"],
        registration_date=datetime.fromisoformat(stored["registration_date"]),
    )
    if not user.verify_password(password):
        raise AuthenticationError("Неверный пароль.")

    return user


def get_portfolio(user: User) -> Portfolio:
    """Возвращает портфель пользователя; если его нет — создаёт пустой."""
    p_data = db.find_portfolio_by_user_id(user.user_id)
    if p_data:
        return Portfolio.from_dict(p_data)

    portfolio = Portfolio(user_id=user.user_id)
    db.upsert_portfolio(portfolio.to_dict())
    return portfolio


STUB_RATES: Dict[str, float] = {
    "BTC": 59337.21,
    "ETH": 3720.00,
    "SOL": 150.00,
    "EUR": 1.0786,
    "GBP": 1.2500,
    "RUB": 0.01016,
}


def _pair_age_seconds(updated_at: str) -> float:
    ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - ts).total_seconds()


def _refresh_cache() -> None:
    config = ParserConfig()
    storage = RatesStorage(config.RATES_FILE_PATH, config.HISTORY_FILE_PATH)
    updater = RatesUpdater(
        [CoinGeckoClient(config), ExchangeRateApiClient(config)], storage
    )
    updater.run_update()


def get_rate_entry(currency_code: str) -> Dict[str, Any]:
    """Возвращает запись курса (rate, updated_at, source) с учётом TTL кеша."""
    code = currency_code.upper()
    pair = f"{code}_USD"
    entry = db.get_rates().get("pairs", {}).get(pair)

    if entry is not None:
        ttl = settings.get("rates_ttl_seconds", 300)
        if _pair_age_seconds(entry["updated_at"]) <= ttl:
            return entry

        logger.info("Кеш %s устарел (>%d c) — обновляем", pair, ttl)
        try:
            _refresh_cache()
        except Exception as exc:
            logger.warning(
                "Обновление %s не удалось, использую устаревший курс: %s",
                pair, exc,
            )
        entry = db.get_rates().get("pairs", {}).get(pair)
        if entry is None:
            raise CurrencyNotFoundError(code)
        return entry

    if code in STUB_RATES:
        logger.info("Пары %s нет в кеше — используется заглушка", pair)
        return {
            "rate": STUB_RATES[code],
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "stub",
        }

    raise CurrencyNotFoundError(code)


def get_exchange_rate(currency_code: str) -> float:
    """Обёртка для совместимости: возвращает только число курса к USD."""
    return float(get_rate_entry(currency_code)["rate"])


@log_action("BUY", verbose=True)
def buy_currency(
    user: User,
    portfolio: Portfolio,
    currency_code: str,
    amount: float,
    rate: float,
) -> Dict[str, Any]:
    """
    Покупка валюты за USD:
    - списываем USD с USD-кошелька;
    - начисляем валюту на целевой кошелёк.

    rate — курс в USD за 1 единицу валюты.
    """
    # Валидация кода валюты (может выбросить CurrencyNotFoundError)
    get_currency(currency_code)

    usd_wallet = portfolio.add_currency("USD")
    target_wallet = portfolio.add_currency(currency_code)

    cost_usd = amount * rate
    if usd_wallet.balance < cost_usd:
        raise InsufficientFundsError(
            available=usd_wallet.balance,
            required=cost_usd,
            code="USD",
        )

    was_usd = usd_wallet.balance
    usd_wallet.withdraw(cost_usd)
    target_wallet.deposit(amount)

    db.upsert_portfolio(portfolio.to_dict())

    return {
        "currency": currency_code,
        "amount": amount,
        "rate": rate,
        "cost_usd": cost_usd,
        "verbose": (
            f"{currency_code}: +{amount:.4f} | "
            f"USD: {was_usd:.4f}->{usd_wallet.balance:.4f}"
        ),
    }


@log_action("SELL", verbose=True)
def sell_currency(
    user: User,
    portfolio: Portfolio,
    currency_code: str,
    amount: float,
    rate: float,
) -> Dict[str, Any]:
    """
    Продажа валюты за USD:
    - списываем валюту с её кошелька;
    - начисляем USD на USD-кошелёк.

    rate — курс в USD за 1 единицу валюты.
    """
    # Валидация кода валюты (может выбросить CurrencyNotFoundError)
    get_currency(currency_code)

    target_wallet = portfolio.get_wallet(currency_code)
    if target_wallet is None:
        raise CurrencyNotFoundError(currency_code)

    revenue_usd = amount * rate
    was = target_wallet.balance

    try:
        target_wallet.withdraw(amount)
    except ValueError:
        raise InsufficientFundsError(
            available=was,
            required=amount,
            code=currency_code,
        )

    usd_wallet = portfolio.add_currency("USD")
    usd_wallet.deposit(revenue_usd)

    db.upsert_portfolio(portfolio.to_dict())

    return {
        "currency": currency_code,
        "amount": amount,
        "rate": rate,
        "revenue_usd": revenue_usd,
        "verbose": (
            f"{currency_code}: {was:.4f}->{target_wallet.balance:.4f} | "
            f"USD: +{revenue_usd:.4f}"
        ),
    }

