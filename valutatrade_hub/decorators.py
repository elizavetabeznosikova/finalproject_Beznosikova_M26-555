import functools
import inspect
import time
from typing import Any, Callable

from valutatrade_hub.logging_config import setup_logging

logger = setup_logging()


def _pretty(value: Any) -> Any:
    """Объект User превращает в имя пользователя, остальное возвращает как есть."""
    if hasattr(value, "username"):
        return value.username
    return value


def log_action(action: str, verbose: bool = False) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Привязываем фактические аргументы к именам параметров —
            # неважно, как вызвали usecase: позиционно или по ключевым словам
            try:
                bound = inspect.signature(func).bind(*args, **kwargs)
                bound.apply_defaults()
                values = bound.arguments
            except TypeError:
                values = {}

            raw_user = values.get("username") or values.get("user")
            username = _pretty(raw_user)
            currency_code = values.get("currency_code")
            amount = values.get("amount")
            rate = values.get("rate")
            base = values.get("base", "USD")

            started_at = time.perf_counter()

            try:
                result = func(*args, **kwargs)

                parts = [
                    f"{action}",
                    f"user='{username}'",
                ]
                if currency_code is not None:
                    parts.append(f"currency='{currency_code}'")
                if amount is not None:
                    parts.append(f"amount={amount}")
                if rate is not None:
                    parts.append(f"rate={rate} base='{base}'")
                parts.append("result=OK")
                if verbose and isinstance(result, dict) and result.get("verbose"):
                    parts.append(f"context={result['verbose']}")

                elapsed_ms = (time.perf_counter() - started_at) * 1000
                parts.append(f"elapsed={elapsed_ms:.1f}ms")

                logger.info(" ".join(parts))
                return result

            except Exception as exc:
                logger.error(
                    "%s user='%s' currency='%s' amount=%s result=ERROR "
                    "error_type=%s error_message=%s",
                    action, username, currency_code, amount,
                    type(exc).__name__, exc,
                )
                raise

        return wrapper

    return decorator


def confirm_action(prompt: str = "Подтвердить операцию? [y/n]: ") -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            answer = input(prompt).strip().lower()
            if answer not in ("y", "yes", "да", "д"):
                logger.info("OPERATION_CANCELLED action='%s'", func.__name__)
                print("Операция отменена пользователем.")
                return None
            return func(*args, **kwargs)

        return wrapper

    return decorator

