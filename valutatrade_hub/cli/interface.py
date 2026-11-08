import shlex
from typing import List, Optional

from prettytable import PrettyTable

from valutatrade_hub.core.exceptions import ValutaTradeError
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.usecases import (
    buy_currency,
    get_portfolio,
    get_rate_entry,
    login_user,
    register_user,
    sell_currency,
)
from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater

logger = setup_logging()


class CLI:
    def __init__(self):
        self.user: Optional[dict] = None
        self.portfolio: Optional[dict] = None
        self._running = True

    @staticmethod
    def _parse_args(raw: str) -> List[str]:
        try:
            return shlex.split(raw)
        except ValueError:
            return raw.split()

    @staticmethod
    def _get_flag(args: List[str], flag: str):
        if flag in args:
            i = args.index(flag)
            if i + 1 < len(args):
                return args[i + 1]
        return None

    def handle_command(self, line: str) -> None:
        args = self._parse_args(line.strip())
        if not args:
            return

        cmd = args[0].lower()

        try:
            if cmd == "register":
                self.cmd_register(args)
            elif cmd == "login":
                self.cmd_login(args)
            elif cmd == "show-portfolio":
                self.cmd_show_portfolio()
            elif cmd == "buy":
                self.cmd_buy(args)
            elif cmd == "sell":
                self.cmd_sell(args)
            elif cmd == "get-rate":
                self.cmd_get_rate(args)
            elif cmd == "update-rates":
                self.cmd_update_rates(args)
            elif cmd == "show-rates":
                self.cmd_show_rates(args)
            elif cmd == "logout":
                self.cmd_logout()
            elif cmd == "help":
                self.cmd_help(args)
            elif cmd == "exit":
                self._running = False
            else:
                print(
                    f"Неизвестная команда: {cmd}. Доступные: register, login, "
                    "show-portfolio, buy, sell, get-rate, update-rates, "
                    "show-rates, logout, exit"
                )
        except ValutaTradeError as e:
            print(e)
        except Exception:
            logger.exception("Неожиданная ошибка в CLI")
            print("Произошла непредвиденная ошибка. Проверьте логи.")

    def cmd_help(self, args: List[str]) -> None:
        print("Доступные команды:")
        print("  register <username> <password>  — регистрация нового пользователя")
        print("  login <username> <password>     — вход в систему")
        print("  logout                          — выход из аккаунта")
        print("  show-portfolio                  — показать портфель с курсами")
        print("  buy <currency> <amount> [rate]  — купить валюту за USD")
        print("  sell <currency> <amount> [rate] — продать валюту за USD")
        print("  get-rate <currency>             — курс валюты к USD")
        print("  update-rates                    — обновить курсы из API")
        print("  show-rates                      — показать текущий кеш курсов")
        print("  exit                            — завершить работу")

    def cmd_register(self, args: List[str]) -> None:
        if len(args) != 3:
            print("Использование: register <username> <password>")
            return
        _, username, password = args
        user = register_user(username, password)
        print(f"Пользователь '{user.username}' успешно зарегистрирован.")

    def cmd_login(self, args: List[str]) -> None:
        if len(args) != 3:
            print("Использование: login <username> <password>")
            return
        _, username, password = args
        user = login_user(username, password)
        self.user = user.to_dict()
        self.portfolio = get_portfolio(user).to_dict()
        print(f"Вы вошли как '{user.username}'. Портфель загружен.")

    def cmd_show_portfolio(self) -> None:
        if not self.user or not self.portfolio:
            print("Сначала войдите (login).")
            return

        wallets = self.portfolio.get("wallets", {})
        rate_entries = {}
        for code in wallets:
            try:
                rate_entries[code] = get_rate_entry(code)
            except Exception:
                rate_entries[code] = None

        table = PrettyTable()
        table.field_names = [
            "Валюта", "Баланс", "Курс (USD)",
            "Стоимость (USD)", "Обновлено",
        ]
        total_usd = 0.0

        for code, data in wallets.items():
            balance = data.get("balance", 0.0)
            entry = rate_entries.get(code)
            rate = entry["rate"] if entry else None
            value_usd = balance * rate if rate is not None else 0.0
            total_usd += value_usd
            updated = entry["updated_at"] if entry else "—"
            rate_str = f"{rate:.4f}" if rate is not None else "—"
            table.add_row(
                [code, f"{balance:.4f}", rate_str, f"{value_usd:.2f}", updated]
            )

        print("Портфель:")
        print(table)
        print(f"Общая стоимость портфеля: {total_usd:.2f} USD")

    def cmd_buy(self, args: List[str]) -> None:
        if not self.user:
            print("Сначала войдите (login).")
            return
        if len(args) not in (3, 4):
            print("Использование: buy <currency> <amount> [rate]")
            return

        _, currency, amount_str = args[:3]
        try:
            amount = float(amount_str)
        except ValueError:
            print("Сумма должна быть числом, например: buy BTC 0.01")
            return
        rate = (
            float(args[3]) if len(args) == 4 else get_rate_entry(currency)["rate"]
        )

        user = User.from_dict(self.user)
        portfolio = Portfolio.from_dict(self.portfolio)

        result = buy_currency(user, portfolio, currency, amount, rate)
        print(f"Покупка выполнена: {result['verbose']}")
        self.portfolio = portfolio.to_dict()

    def cmd_sell(self, args: List[str]) -> None:
        if not self.user:
            print("Сначала войдите (login).")
            return
        if len(args) not in (3, 4):
            print("Использование: sell <currency> <amount> [rate]")
            return

        _, currency, amount_str = args[:3]
        try:
            amount = float(amount_str)
        except ValueError:
            print("Сумма должна быть числом, например: sell BTC 0.01")
            return
        rate = (
            float(args[3]) if len(args) == 4 else get_rate_entry(currency)["rate"]
        )

        user = User.from_dict(self.user)
        portfolio = Portfolio.from_dict(self.portfolio)

        result = sell_currency(user, portfolio, currency, amount, rate)
        print(f"Продажа выполнена: {result['verbose']}")
        self.portfolio = portfolio.to_dict()

    def cmd_get_rate(self, args: List[str]) -> None:
        if len(args) != 2:
            print("Использование: get-rate <currency>")
            return
        entry = get_rate_entry(args[1])
        print(
            f"{args[1].upper()}_USD = {entry['rate']} "
            f"(обновлено: {entry['updated_at']}, источник: {entry['source']})"
        )

    def cmd_update_rates(self, args: List[str]) -> None:
        source = self._get_flag(args, "--source")
        config = ParserConfig()
        storage = RatesStorage(config.RATES_FILE_PATH, config.HISTORY_FILE_PATH)

        clients = []
        if source in (None, "coingecko"):
            clients.append(CoinGeckoClient(config))
        if source in (None, "exchangerate"):
            clients.append(ExchangeRateApiClient(config))

        print("INFO: Starting rates update...")
        updater = RatesUpdater(clients, storage)
        result = updater.run_update(source)

        for err in result["errors"]:
            print(f"ERROR: {err}")

        if result["updated"] > 0:
            print(
                f"Update successful. Total rates updated: {result['updated']}. "
                f"Last refresh: {result['last_refresh']}"
            )
        else:
            print(
                "Update completed with errors. Check logs/actions.log for details."
            )

    def cmd_show_rates(self, args: List[str]) -> None:
        config = ParserConfig()
        snapshot = RatesStorage(
            config.RATES_FILE_PATH, config.HISTORY_FILE_PATH
        ).load_snapshot()
        pairs: dict = snapshot.get("pairs", {})

        if not pairs:
            print(
                "Локальный кеш курсов пуст. Выполните 'update-rates', "
                "чтобы загрузить данные."
            )
            return

        currency = self._get_flag(args, "--currency")
        top = self._get_flag(args, "--top")
        base = (self._get_flag(args, "--base") or "USD").upper()

        if currency:
            currency = currency.upper()
            pair = f"{currency}_USD"
            if pair not in pairs:
                print(f"Курс для '{currency}' не найден в кеше.")
                return
            pairs = {pair: pairs[pair]}

        reverse = top is not None
        items = sorted(pairs.items(), key=lambda kv: kv[1]["rate"], reverse=reverse)
        if top is not None:
            try:
                items = items[: int(top)]
            except ValueError:
                print("--top должен быть целым числом")
                return

        if base != "USD":
            base_rate = pairs.get(f"{base}_USD", {}).get("rate")
            if not base_rate:
                print(f"Курс для '{base}' не найден в кеше.")
                return
            converted = {}
            for pair, entry in pairs.items():
                code = pair.split("_")[0]
                if code != base:
                    converted[f"{code}_{base}"] = {
                        "rate": round(entry["rate"] / base_rate, 8),
                        "updated_at": entry["updated_at"],
                        "source": entry["source"],
                    }
            pairs, items = converted, sorted(converted.items())

        print(
            f"Rates from cache (updated at {snapshot.get('last_refresh')}):"
        )
        for pair, entry in items:
            print(
                f"- {pair}: {entry['rate']} "
                f"({entry['source']}, {entry['updated_at']})"
            )

    def cmd_logout(self) -> None:
        self.user = None
        self.portfolio = None
        print("Вы вышли из системы.")

    def run(self) -> None:
        print("ValutaTrade Hub — CLI. Введите help или список команд.")
        while self._running:
            try:
                line = input("\n>>> Введите команду: ").strip()
                if not line:
                    continue
                self.handle_command(line)
            except EOFError:
                self._running = False
                print("\nВыход.")
            except KeyboardInterrupt:
                self._running = False
                print("\nПрервано пользователем.")


def main() -> None:
    cli = CLI()
    cli.run()

