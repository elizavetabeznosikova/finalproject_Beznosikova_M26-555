class ValutaTradeError(Exception):
    pass


class InsufficientFundsError(ValutaTradeError):
    def __init__(self, available: float, required: float, code: str):
        self.available = available
        self.required = required
        self.currency_code = code
        super().__init__(
            f"Недостаточно средств: доступно {available:.4f} {code}, "
            f"требуется {required:.4f} {code}"
        )


class CurrencyNotFoundError(ValutaTradeError):
    def __init__(self, code: str):
        self.currency_code = code
        super().__init__(f"Неизвестная валюта '{code}'")


class ApiRequestError(ValutaTradeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")


class AuthenticationError(ValutaTradeError):
    pass


class ValidationError(ValutaTradeError):
    pass


class UserNotFoundError(ValutaTradeError):
    def __init__(self, username: str):
        self.username = username
        super().__init__(f"Пользователь '{username}' не найден")


class UsernameTakenError(ValutaTradeError):
    def __init__(self, username: str):
        self.username = username
        super().__init__(f"Имя пользователя '{username}' уже занято")

