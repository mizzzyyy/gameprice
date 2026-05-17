import time
from typing import Any

import aiohttp

import i18n
from config import CBR_DAILY_URL, DEFAULT_CURRENCY

_FREE_EPSILON = 0.001

_rate_cache: tuple[float, float] | None = None
_CACHE_TTL_SEC = 6 * 60 * 60


def user_currency(lang: str) -> str:
    return "RUB" if lang == "ru" else "USD"


async def get_usd_rub_rate() -> float:
    global _rate_cache
    now = time.time()
    if _rate_cache and now - _rate_cache[1] < _CACHE_TTL_SEC:
        return _rate_cache[0]

    fallback = 92.0
    try:
        async with aiohttp.ClientSession(trust_env=True) as session:
            async with session.get(
                CBR_DAILY_URL, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data: dict[str, Any] = await resp.json(content_type=None)
        rate = float(data["Valute"]["USD"]["Value"])
        _rate_cache = (rate, now)
        return rate
    except (aiohttp.ClientError, KeyError, TypeError, ValueError):
        if _rate_cache:
            return _rate_cache[0]
        return fallback


async def usd_to_rub(amount_usd: float) -> float:
    return amount_usd * await get_usd_rub_rate()


async def rub_to_usd(amount_rub: float) -> float:
    return amount_rub / await get_usd_rub_rate()


async def convert(amount: float, from_currency: str, to_currency: str) -> float:
    src = from_currency.upper()
    dst = to_currency.upper()
    if src == dst:
        return amount
    if src == "USD" and dst == "RUB":
        return await usd_to_rub(amount)
    if src == "RUB" and dst == "USD":
        return await rub_to_usd(amount)
    return amount


async def to_user_currency(amount: float, currency: str, lang: str) -> tuple[float, str]:
    return await convert(amount, currency, user_currency(lang)), user_currency(lang)


def _is_free_amount(amount: float, currency: str) -> bool:
    return currency.upper() == "FREE" or amount <= _FREE_EPSILON


def format_price(
    amount: float, currency: str = DEFAULT_CURRENCY, *, lang: str | None = None
) -> str:
    cur = currency.upper()
    if _is_free_amount(amount, cur):
        if lang:
            return i18n.t("price_free", lang)
        return i18n.t("price_free", "ru")
    if cur in ("RUB", "₽"):
        whole = round(amount)
        text = f"{whole:,}".replace(",", " ") if whole >= 1000 else str(whole)
        return f"{text} ₽"
    if cur == "USD":
        return f"${amount:.2f}"
    return f"{amount:.2f} {currency}"


async def format_for_user(
    amount: float,
    currency: str,
    lang: str,
    *,
    show_alt_hint: bool = False,
) -> str:
    lng = lang if lang in ("ru", "en") else "ru"
    target = user_currency(lng)
    src = currency.upper()

    if _is_free_amount(amount, src):
        return i18n.t("price_free", lng)

    converted = await convert(amount, src, target)
    if _is_free_amount(converted, target):
        return i18n.t("price_free", lng)
    main = format_price(converted, target, lang=lng)

    if not show_alt_hint or src == target:
        return main

    if src == "USD" and target == "RUB":
        return f"{main} (~${amount:.2f})"
    if src == "RUB" and target == "USD":
        return f"{main} ({format_price(amount, 'RUB')} in RU)"
    return main


async def format_price_ru(
    amount: float, currency: str, *, show_usd_hint: bool = False
) -> str:
    return await format_for_user(
        amount, currency, "ru", show_alt_hint=show_usd_hint
    )
