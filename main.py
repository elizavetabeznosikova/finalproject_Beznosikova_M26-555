from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import CurrencyNotFoundError

print(get_currency("USD").get_display_info())
print(get_currency("BTC").get_display_info())

try:
    get_currency("ABC")
except CurrencyNotFoundError as e:
    print("Перехвачено:", e)

