import asyncio
import difflib
import logging
import re
from datetime import datetime
from io import BytesIO
from typing import Any
from xml.etree import ElementTree

import aiohttp
import currency
import db
import i18n
import ru_retailers
import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from config import (
    CHARTS_DIR,
    CHEAPSHARK_API,
    DEFAULT_CURRENCY,
    DEFAULT_REGION,
    EPIC_FREE_API,
    SEARCH_ALIASES,
    STEAM_API_ENABLED,
    STEAM_NEWS_RSS,
    STEAM_PRICE_LOOKUP_ENABLED,
    STEAM_SEARCH_API,
    STEAM_STORE_API,
    STORE_NAMES,
)

logger = logging.getLogger(__name__)

CHEAPSHARK_TIMEOUT = aiohttp.ClientTimeout(total=20)
STEAM_TIMEOUT = aiohttp.ClientTimeout(total=12, connect=6)
STEAM_STORE_ID = "1"


def _http_session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(trust_env=True)

STEAM_URL_RE = re.compile(
    r"store\.steampowered\.com/app/(\d+)", re.IGNORECASE
)
EPIC_URL_RE = re.compile(
    r"store\.epicgames\.com/(?:[a-z-]+/)?(?:p|en-US/p)/([a-z0-9-]+)",
    re.IGNORECASE,
)


def normalize_game_key(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def steam_cc_for_lang(ui_lang: str) -> str:
    return "ru" if i18n.normalize_lang(ui_lang) == "ru" else "us"


def extract_steam_app_id(text: str) -> str | None:
    match = STEAM_URL_RE.search(text.strip())
    return match.group(1) if match else None


def use_foreign_key_stores(lang: str) -> bool:
    """Ключи CheapShark — для EN; для RU дополнительно блок RU-магазинов."""
    return True


def show_ru_retailer_block(lang: str) -> bool:
    return i18n.normalize_lang(lang) == "ru"


def steam_capsule_url(app_id: str) -> str:
    return (
        f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/"
        "capsule_231x87.jpg"
    )


def steam_header_url(app_id: str) -> str:
    return (
        f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg"
    )


async def load_steam_icon(app_id: str) -> BytesIO | None:
    urls = [
        steam_header_url(app_id),
        steam_capsule_url(app_id),
        f"https://steamcdn-a.akamaihd.net/steam/apps/{app_id}/header.jpg",
    ]
    async with _http_session() as session:
        for url in urls:
            try:
                async with session.get(
                    url, timeout=STEAM_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"}
                ) as resp:
                    if resp.status != 200:
                        continue
                    ctype = (resp.headers.get("Content-Type") or "").lower()
                    if not ctype.startswith("image/"):
                        continue
                    data = await resp.read()
                    if len(data) < 200:
                        continue
                    buf = BytesIO(data)
                    buf.seek(0)
                    return buf
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                continue
    return None


async def _amount_to_rub(amount: float, cur: str, lng: str) -> float:
    target = currency.user_currency(lng)
    return await currency.convert(amount, cur.upper(), target)


async def _build_search_price_rows(
    *,
    lng: str,
    steam_ru: dict[str, Any] | None,
    cheap_usd: float,
    cheapest_deal_id: str,
    ru_offers: list[dict[str, Any]],
    show_foreign: bool,
) -> list[dict[str, Any]]:
    """Строки цен для сортировки (price_rub — для сравнения)."""
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()

    def add(label: str, price_rub: float, display: str, url: str | None = None) -> None:
        key = (label, url)
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {"label": label, "price_rub": price_rub, "display": display, "url": url}
        )

    if show_ru_retailer_block(lng):
        for offer in ru_offers:
            price_rub = offer.get("price_rub")
            if price_rub is None:
                continue
            store = str(offer.get("store", ""))
            pr = float(price_rub)
            display = await currency.format_for_user(pr, "RUB", lng)
            add(store, pr, display, str(offer.get("url") or "") or None)

    if steam_ru:
        status = steam_ru.get("status")
        steam_url = str(steam_ru.get("url") or "")
        if status == "ok":
            amt = float(steam_ru.get("price", 0))
            cur = str(steam_ru.get("currency", "RUB"))
            rub = await _amount_to_rub(amt, cur, lng)
            label = "Steam РФ" if lng == "ru" else "Steam"
            display = await currency.format_for_user(amt, cur, lng)
            add(label, rub, display, steam_url or None)
        elif status == "free":
            display = i18n.t("price_free", lng)
            add("Steam", 0.0, display, steam_url or None)
        elif status == "foreign_only":
            amt = float(steam_ru.get("price", 0))
            cur = str(steam_ru.get("currency", "USD"))
            rub = await _amount_to_rub(amt, cur, lng)
            display = await currency.format_for_user(
                amt, cur, lng, show_alt_hint=True
            )
            add(i18n.t("price_row_steam_foreign", lng), rub, display, steam_url or None)

    if show_foreign:
        if cheap_usd <= 0:
            if not any(r["price_rub"] <= 0 for r in rows):
                add(
                    i18n.t("price_row_keys", lng),
                    0.0,
                    i18n.t("price_free", lng),
                    None,
                )
        else:
            rub = await currency.usd_to_rub(cheap_usd)
            display = await currency.format_for_user(
                cheap_usd, "USD", lng, show_alt_hint=True
            )
            url = (
                f"https://www.cheapshark.com/redirect.php?dealID={cheapest_deal_id}"
                if cheapest_deal_id
                else None
            )
            add(i18n.t("price_row_keys", lng), rub, display, url)

    rows.sort(key=lambda r: (r["price_rub"], r["label"]))
    return rows


def _plain_store_label(name: str) -> str:
    """Точка в названии (Plati.market) иначе автолинкуется Telegram'ом."""
    if "." not in name:
        return name
    return name.replace(".", ".\u200b")


async def _format_sorted_prices_block(
    rows: list[dict[str, Any]], lng: str
) -> str:
    if not rows:
        return ""
    open_lbl = i18n.t("ru_store_open", lng)
    lines = [i18n.t("search_best_price", lng, price=rows[0]["display"])]
    for row in rows[:6]:
        label = _plain_store_label(str(row["label"]))
        url = row.get("url")
        if url:
            lines.append(
                i18n.t(
                    "search_price_row_link",
                    lng,
                    label=label,
                    price=row["display"],
                    url=url,
                    open=open_lbl,
                )
            )
        else:
            lines.append(
                i18n.t(
                    "search_price_row",
                    lng,
                    label=label,
                    price=row["display"],
                )
            )
    return "\n".join(lines)


def ensure_app_id(url: str, parsed: dict[str, str | None]) -> str | None:
    if parsed.get("app_id"):
        return str(parsed["app_id"])
    return extract_steam_app_id(url)


def _steam_search_enabled() -> bool:
    return STEAM_API_ENABLED or STEAM_PRICE_LOOKUP_ENABLED


def parse_store_url(url: str) -> dict[str, str | None]:
    steam = STEAM_URL_RE.search(url)
    if steam:
        app_id = steam.group(1)
        return {
            "store": "Steam",
            "app_id": app_id,
            "store_url": url.split("?")[0],
            "slug": None,
        }
    epic = EPIC_URL_RE.search(url)
    if epic:
        return {
            "store": "Epic Games Store",
            "app_id": None,
            "store_url": url.split("?")[0],
            "slug": epic.group(1),
        }
    return {"store": "Unknown", "app_id": None, "store_url": url, "slug": None}


async def _get_json(
    session: aiohttp.ClientSession,
    url: str,
    *,
    timeout: aiohttp.ClientTimeout = CHEAPSHARK_TIMEOUT,
    **kwargs: Any,
) -> Any:
    async with session.get(url, timeout=timeout, **kwargs) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)


async def _get_json_safe(
    session: aiohttp.ClientSession,
    url: str,
    *,
    timeout: aiohttp.ClientTimeout = CHEAPSHARK_TIMEOUT,
    **kwargs: Any,
) -> Any | None:
    try:
        return await _get_json(session, url, timeout=timeout, **kwargs)
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
        logger.warning("Request failed %s: %s", url, exc)
        return None


def _expand_search_queries(title: str) -> list[str]:
    cleaned = title.strip()
    key = normalize_game_key(cleaned)
    queries = [cleaned]
    if key in SEARCH_ALIASES:
        queries.extend(SEARCH_ALIASES[key])
    if len(key) <= 6 and key.replace(" ", "") not in queries:
        queries.append(key.replace(" ", ""))
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        nq = q.strip()
        if nq and nq.lower() not in seen:
            seen.add(nq.lower())
            unique.append(nq)
    return unique


def _relevance_score(query: str, candidate: str) -> float:
    q = normalize_game_key(query)
    c = normalize_game_key(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    if q in c:
        return 0.95
    q_compact = q.replace(" ", "")
    c_compact = c.replace(" ", "")
    if q_compact and q_compact in c_compact:
        return 0.85
    q_tokens = set(q.split())
    c_tokens = set(c.split())
    if len(q_tokens) >= 2 and q_tokens <= c_tokens:
        return 0.9
    return difflib.SequenceMatcher(None, q, c).ratio()


async def _cheapshark_games_by_title(
    session: aiohttp.ClientSession, title: str, limit: int = 30
) -> list[dict[str, Any]]:
    data = await _get_json_safe(
        session,
        f"{CHEAPSHARK_API}/games",
        params={"title": title, "limit": limit, "exact": "0"},
    )
    return data if isinstance(data, list) else []


async def _steam_store_search(
    session: aiohttp.ClientSession, title: str, limit: int = 5, *, ui_lang: str = "ru"
) -> list[dict[str, Any]]:
    if not _steam_search_enabled():
        return []
    lng = i18n.normalize_lang(ui_lang)
    cc = steam_cc_for_lang(lng)
    data = await _get_json_safe(
        session,
        STEAM_SEARCH_API,
        timeout=STEAM_TIMEOUT,
        params={"term": title, "l": _steam_locale(lng), "cc": cc},
    )
    if not isinstance(data, dict):
        return []
    items = data.get("items", [])
    return [i for i in items if i.get("type") == "app"][:limit]


async def get_game_details(game_id: str) -> dict[str, Any] | None:
    """Сделки по игре — только через /games?id= (deals?gameID= не фильтрует)."""
    async with _http_session() as session:
        data = await _get_json_safe(
            session, f"{CHEAPSHARK_API}/games", params={"id": game_id}
        )
    if not isinstance(data, dict) or not data.get("info"):
        return None
    return data


async def get_game_deals(game_id: str, limit: int = 5) -> list[dict[str, Any]]:
    details = await get_game_details(game_id)
    if not details:
        return []
    deals = details.get("deals", [])
    if not isinstance(deals, list):
        return []
    return sorted(deals, key=lambda d: float(d.get("price", 9999)))[:limit]


async def search_games(
    title: str, limit: int = 5, *, ui_lang: str = "ru"
) -> list[dict[str, Any]]:
    return await search_games_smart(title, limit=limit, ui_lang=ui_lang)


async def search_games_smart(
    title: str, limit: int = 5, *, ui_lang: str = "ru"
) -> list[dict[str, Any]]:
    queries = _expand_search_queries(title)
    min_score = 0.35
    ranked: dict[str, tuple[float, dict[str, Any]]] = {}

    def best_score(name: str) -> float:
        return max(_relevance_score(q, name) for q in queries)

    async with _http_session() as session:
        for query in queries:
            for game in await _cheapshark_games_by_title(session, query, limit=40):
                name = str(game.get("external", ""))
                score = best_score(name)
                if score < min_score:
                    continue
                gid = str(game.get("gameID", ""))
                if not gid:
                    continue
                if gid not in ranked or score > ranked[gid][0]:
                    ranked[gid] = (score, game)

            for item in await _steam_store_search(
                session, query, limit=5, ui_lang=ui_lang
            ):
                steam_id = str(item.get("id", ""))
                steam_name = str(item.get("name", ""))
                if not steam_id:
                    continue
                cs = await find_game_by_steam_app_id(steam_id)
                if cs:
                    gid = str(cs.get("gameID", ""))
                    if gid:
                        score = max(best_score(str(cs.get("external", ""))), best_score(steam_name), 0.85)
                        if gid not in ranked or score > ranked[gid][0]:
                            ranked[gid] = (score, cs)
                    continue
                for game in await _cheapshark_games_by_title(session, steam_name, limit=40):
                    if str(game.get("steamAppID", "")) == steam_id:
                        score = max(
                            best_score(str(game.get("external", ""))),
                            best_score(steam_name),
                            0.8,
                        )
                        gid = str(game.get("gameID", ""))
                        if gid and (gid not in ranked or score > ranked[gid][0]):
                            ranked[gid] = (score, game)

    if not ranked:
        async with _http_session() as session:
            for query in queries:
                raw = await _cheapshark_games_by_title(session, query, limit=15)
                if raw:
                    raw.sort(
                        key=lambda g: best_score(str(g.get("external", ""))),
                        reverse=True,
                    )
                    return raw[:limit]

    if not ranked and _steam_search_enabled():
        lng = i18n.normalize_lang(ui_lang)
        async with _http_session() as session:
            for query in queries:
                for item in await _steam_store_search(
                    session, query, limit=8, ui_lang=ui_lang
                ):
                    steam_id = str(item.get("id", ""))
                    if not steam_id or steam_id in ranked:
                        continue
                    built = await _build_game_from_app_id(steam_id, lng)
                    if built:
                        score = max(
                            best_score(str(built.get("external", ""))),
                            best_score(str(item.get("name", ""))),
                            0.75,
                        )
                        ranked[steam_id] = (score, built)

    if not ranked:
        return []

    ordered = sorted(ranked.values(), key=lambda x: x[0], reverse=True)
    return [game for _, game in ordered[:limit]]


async def format_deal_line(deal: dict[str, Any], lang: str) -> str:
    store_id = str(deal.get("storeID", ""))
    store = STORE_NAMES.get(store_id, f"#{store_id}")
    price_usd = float(deal.get("price", deal.get("salePrice", 0)))
    retail_usd = float(deal.get("retailPrice", deal.get("normalPrice", 0)))
    savings = float(deal.get("savings", 0))
    url = f"https://www.cheapshark.com/redirect.php?dealID={deal.get('dealID', '')}"
    price_txt = await currency.format_for_user(price_usd, "USD", lang, show_alt_hint=True)
    if price_usd <= 0:
        lines = f"• <b>{store}</b>: <b>{price_txt}</b>\n"
    else:
        retail_txt = await currency.format_for_user(
            retail_usd, "USD", lang, show_alt_hint=True
        )
        lines = (
            f"• <b>{store}</b>: {price_txt}"
            f" ({i18n.t('was_price', lang, price=retail_txt)}, −{savings:.0f}%)\n"
        )
    if i18n.normalize_lang(lang) == "ru":
        hint_key = "steam_key_hint" if store_id == STEAM_STORE_ID else "foreign_key_hint"
        lines += f"  <i>{i18n.t(hint_key, lang)}</i>\n"
    lines += f"  <a href='{url}'>{i18n.t('deal_buy', lang)}</a>"
    return lines


def _steam_locale(ui_lang: str) -> str:
    return "russian" if i18n.normalize_lang(ui_lang) == "ru" else "english"


async def _fetch_appdetails(
    session: aiohttp.ClientSession, app_id: str, cc: str, ui_lang: str
) -> dict[str, Any] | None:
    data = await _get_json_safe(
        session,
        f"{STEAM_STORE_API}/appdetails",
        timeout=STEAM_TIMEOUT,
        params={"appids": app_id, "cc": cc, "l": _steam_locale(ui_lang)},
    )
    if not isinstance(data, dict):
        return None
    entry = data.get(app_id)
    if not entry:
        return None
    return entry


def _parse_steam_entry(entry: dict[str, Any], app_id: str, cc: str) -> dict[str, Any]:
    url = f"https://store.steampowered.com/app/{app_id}"
    if not entry.get("success"):
        return {"status": "no_store", "cc": cc, "url": url}

    game_data = entry.get("data", {})
    title = game_data.get("name", f"App {app_id}")
    price_info = game_data.get("price_overview") or {}

    if game_data.get("is_free"):
        return {
            "status": "free",
            "title": title,
            "price": 0.0,
            "currency": "FREE",
            "url": url,
            "cc": cc,
        }

    if price_info:
        return {
            "status": "ok",
            "title": title,
            "price": price_info.get("final", 0) / 100,
            "currency": price_info.get("currency", "RUB"),
            "url": url,
            "cc": cc,
        }

    return {"status": "no_price", "title": title, "url": url, "cc": cc}


async def get_steam_price(
    app_id: str, region: str | None = None, ui_lang: str = "ru"
) -> dict[str, Any] | None:
    if not STEAM_PRICE_LOOKUP_ENABLED:
        return None

    lng = i18n.normalize_lang(ui_lang)
    primary_cc = region or steam_cc_for_lang(lng)
    fallback_cc = "us" if primary_cc == "ru" else "ru"

    async with _http_session() as session:
        primary_entry = await _fetch_appdetails(session, app_id, primary_cc, lng)
        if primary_entry is None:
            return {"status": "error", "app_id": app_id}

        primary = _parse_steam_entry(primary_entry, app_id, primary_cc)
        if primary["status"] in ("ok", "free"):
            return primary

        fallback_entry = await _fetch_appdetails(session, app_id, fallback_cc, lng)
        if fallback_entry is None:
            return {"status": "error", "app_id": app_id}

        fallback = _parse_steam_entry(fallback_entry, app_id, fallback_cc)
        if fallback["status"] in ("ok", "free"):
            return {
                "status": "foreign_only",
                "title": fallback.get("title"),
                "price": fallback.get("price", 0),
                "currency": fallback.get("currency", "USD"),
                "url": primary.get("url") or fallback.get("url"),
                "cc": fallback_cc,
            }

        if primary["status"] == "no_store" and fallback["status"] == "no_store":
            return {
                "status": "unavailable",
                "title": fallback.get("title") or primary.get("title"),
                "url": primary.get("url") or fallback.get("url"),
                "cc": primary_cc,
            }

        return {"status": "error", "app_id": app_id}


async def get_steam_dlc(app_id: str, ui_lang: str = "ru", limit: int = 6) -> list[dict[str, Any]]:
    if not STEAM_PRICE_LOOKUP_ENABLED:
        return []

    lng = i18n.normalize_lang(ui_lang)
    cc = steam_cc_for_lang(lng)
    async with _http_session() as session:
        data = await _get_json_safe(
            session,
            f"{STEAM_STORE_API}/appdetails",
            timeout=STEAM_TIMEOUT,
            params={
                "appids": app_id,
                "cc": cc,
                "l": _steam_locale(lng),
            },
        )
    if not isinstance(data, dict):
        return []
    entry = data.get(app_id)
    if not entry or not entry.get("success"):
        return []

    dlc_ids = entry.get("data", {}).get("dlc") or []
    if not dlc_ids:
        return []

    results: list[dict[str, Any]] = []
    for dlc_id in dlc_ids[:limit]:
        dlc_info = await get_steam_price(str(dlc_id), ui_lang=lng)
        if not dlc_info or dlc_info.get("status") not in ("ok", "free"):
            continue
        results.append(dlc_info)
    return results


def _steam_price_label_key(steam: dict[str, Any], lng: str, *, free: bool = False) -> str:
    cc = str(steam.get("cc", steam_cc_for_lang(lng)))
    if free:
        return "steam_us_free" if cc == "us" else "steam_ru_free"
    return "steam_us_price" if cc == "us" else "steam_ru_price"


async def _format_steam_block(steam: dict[str, Any], lang: str) -> str:
    lng = i18n.normalize_lang(lang)
    status = steam.get("status", "error")
    lines: list[str] = []
    primary_cc = steam_cc_for_lang(lng)

    if status == "ok":
        price = await currency.format_for_user(
            float(steam["price"]),
            str(steam.get("currency", "RUB")),
            lng,
        )
        label = _steam_price_label_key(steam, lng)
        lines.append(f"<b>{i18n.t(label, lng, price=price)}</b>")
        lines.append(f"<a href='{steam['url']}'>{i18n.t('steam_buy', lng)}</a>")
    elif status == "free":
        label = _steam_price_label_key(steam, lng, free=True)
        lines.append(f"<b>{i18n.t(label, lng)}</b>")
        lines.append(f"<a href='{steam['url']}'>{i18n.t('steam_open', lng)}</a>")
    elif status == "foreign_only":
        fp = await currency.format_for_user(
            float(steam.get("price", 0)),
            str(steam.get("currency", "USD")),
            lng,
            show_alt_hint=True,
        )
        lines.append(f"<b>{i18n.t('steam_foreign_only', lng, price=fp)}</b>")
    elif status == "unavailable":
        key = (
            "steam_unavailable_us"
            if primary_cc == "us"
            else "steam_unavailable"
        )
        lines.append(i18n.t(key, lng))
    else:
        lines.append(f"<i>{i18n.t('steam_error', lng)}</i>")

    return "\n".join(lines)


async def _build_game_from_app_id(app_id: str, lng: str) -> dict[str, Any] | None:
    cs = await find_game_by_steam_app_id(app_id)
    if cs:
        return cs
    steam = await get_steam_price(app_id, ui_lang=lng)
    if not steam or steam.get("status") in ("error", "unavailable"):
        return None
    name = str(steam.get("title") or f"App {app_id}")
    cheapest = "0"
    if steam.get("status") == "free":
        cheapest = "0"
    elif steam.get("status") == "ok":
        cur = str(steam.get("currency", "USD"))
        if cur.upper() == "RUB":
            rate = await currency.get_usd_rub_rate()
            cheapest = str(float(steam.get("price", 0)) / rate)
        else:
            cheapest = str(steam.get("price", 0))
    return {
        "gameID": "",
        "external": name,
        "steamAppID": app_id,
        "cheapest": cheapest,
        "cheapestDealID": "",
    }


async def format_search_results(title: str, lang: str = "ru") -> str:
    lng = i18n.normalize_lang(lang)
    query = title.strip()
    app_id = extract_steam_app_id(query)
    if app_id:
        built = await _build_game_from_app_id(app_id, lng)
        games = [built] if built else []
    else:
        games = await search_games_smart(query, limit=3, ui_lang=lng)
    if not games:
        return i18n.t("not_found", lng)

    blocks: list[str] = []
    show_foreign = use_foreign_key_stores(lng)

    for game in games:
        game_id = str(game.get("gameID", ""))
        name = game.get("external", title)
        try:
            cheap_usd = float(game.get("cheapest") or 0)
        except (TypeError, ValueError):
            cheap_usd = 0.0
        steam_id = game.get("steamAppID")
        cheapest_deal_id = str(game.get("cheapestDealID") or "")

        steam_ru: dict[str, Any] | None = None
        if steam_id and STEAM_PRICE_LOOKUP_ENABLED:
            steam_ru = await get_steam_price(str(steam_id), ui_lang=lng)

        ru_offers: list[dict[str, Any]] = []
        if show_ru_retailer_block(lng):
            ru_offers = await ru_retailers.collect_ru_store_offers(
                name, steam_app_id=str(steam_id) if steam_id else None, limit=4
            )

        price_rows = await _build_search_price_rows(
            lng=lng,
            steam_ru=steam_ru,
            cheap_usd=cheap_usd,
            cheapest_deal_id=cheapest_deal_id,
            ru_offers=ru_offers,
            show_foreign=show_foreign,
        )

        parts = [f"🎮 <b>{name}</b>"]
        prices_block = await _format_sorted_prices_block(price_rows, lng)
        if prices_block:
            parts.append(prices_block)
        elif steam_ru:
            parts.append(await _format_steam_block(steam_ru, lng))
        elif show_ru_retailer_block(lng):
            parts.append(f"<i>{i18n.t('ru_stores_empty', lng)}</i>")

        if steam_ru and steam_ru.get("status") == "unavailable":
            key = (
                "steam_unavailable_us"
                if steam_cc_for_lang(lng) == "us"
                else "steam_unavailable"
            )
            parts.append(i18n.t(key, lng))
        elif steam_ru and steam_ru.get("status") == "error" and not price_rows:
            parts.append(f"<i>{i18n.t('steam_error', lng)}</i>")

        if steam_id and STEAM_PRICE_LOOKUP_ENABLED:
            dlcs = await get_steam_dlc(str(steam_id), ui_lang=lng)
            if dlcs:
                dlc_lines = [f"<b>{i18n.t('dlc_header', lng)}</b>"]
                for dlc in dlcs[:5]:
                    dlc_amount = float(dlc.get("price", 0))
                    dlc_cur = str(dlc.get("currency", "RUB"))
                    if dlc.get("status") == "free" or dlc_amount <= 0:
                        dlc_price = i18n.t("price_free", lng)
                    else:
                        dlc_price = await currency.format_for_user(
                            dlc_amount, dlc_cur, lng
                        )
                    dlc_lines.append(f"  • {dlc.get('title', 'DLC')}: {dlc_price}")
                parts.append("\n".join(dlc_lines))

        if steam_id:
            parts.append(f"{i18n.t('steam_appid', lng)}: <code>{steam_id}</code>")

        if show_foreign:
            savings = await best_deal_savings_percent(game_id)
            if savings > 0:
                parts.append(i18n.t("search_on_sale", lng, pct=savings))

        blocks.append("\n".join(parts))

        if show_foreign:
            deals = await get_game_deals(game_id, limit=8) if game_id else []
            if steam_ru and steam_ru.get("status") in ("ok", "free"):
                deals = [d for d in deals if str(d.get("storeID")) != STEAM_STORE_ID]
            if deals:
                blocks.append(i18n.t("other_stores", lng) + ":")
                for deal in deals[:5]:
                    blocks.append(await format_deal_line(deal, lng))
            elif cheapest_deal_id:
                blocks.append(
                    f"<a href='https://www.cheapshark.com/redirect.php?dealID={cheapest_deal_id}'>"
                    f"{i18n.t('best_deal', lng)}</a>"
                )
        blocks.append("")
    return "\n".join(blocks).strip()


async def find_game_by_steam_app_id(app_id: str) -> dict[str, Any] | None:
    async with _http_session() as session:
        data = await _get_json_safe(
            session,
            f"{CHEAPSHARK_API}/games",
            params={"steamAppID": app_id},
        )
    if isinstance(data, list) and data:
        return data[0]
    if isinstance(data, dict) and data.get("gameID"):
        return data
    return None


async def resolve_game_title_from_url(
    url: str, parsed: dict[str, str | None], *, ui_lang: str = "ru"
) -> str:
    if parsed.get("app_id"):
        app_id = str(parsed["app_id"])
        info = await get_steam_price(app_id, ui_lang=ui_lang)
        if info and info.get("title") and info.get("status") != "error":
            return str(info["title"])
        cs_game = await find_game_by_steam_app_id(app_id)
        if cs_game and cs_game.get("external"):
            return str(cs_game["external"])
    if parsed.get("slug"):
        return str(parsed["slug"]).replace("-", " ").title()
    return "Unknown game"


async def _snapshot_from_steam(steam: dict[str, Any], lng: str) -> dict[str, Any] | None:
    status = steam.get("status")
    user_cur = currency.user_currency(lng)
    if status == "free":
        return {
            "title": steam.get("title"),
            "price": 0.0,
            "currency": user_cur,
            "url": steam.get("url"),
            "source": "steam",
        }
    if status == "ok":
        amount, _ = await currency.to_user_currency(
            float(steam["price"]), str(steam.get("currency", "RUB")), lng
        )
        return {
            "title": steam.get("title"),
            "price": amount,
            "currency": user_cur,
            "url": steam.get("url"),
            "source": "steam",
        }
    if status == "foreign_only":
        amount, _ = await currency.to_user_currency(
            float(steam.get("price", 0)),
            str(steam.get("currency", "USD")),
            lng,
        )
        return {
            "title": steam.get("title"),
            "price": amount,
            "currency": user_cur,
            "url": steam.get("url"),
            "source": "steam_foreign",
        }
    return None


async def _steam_price_snapshot(
    app_id: str, lng: str, *, retries: int = 3
) -> dict[str, Any] | None:
    for attempt in range(retries):
        steam = await get_steam_price(app_id, ui_lang=lng)
        if steam:
            snap = await _snapshot_from_steam(steam, lng)
            if snap:
                return snap
        if attempt < retries - 1:
            await asyncio.sleep(0.4 * (attempt + 1))
    return None


async def fetch_price_for_wishlist(
    store_url: str,
    app_id: str | None,
    cheapshark_id: str | None,
    ui_lang: str = "ru",
) -> dict[str, Any] | None:
    lng = i18n.normalize_lang(ui_lang)
    resolved_app = app_id or extract_steam_app_id(store_url)
    if resolved_app and STEAM_PRICE_LOOKUP_ENABLED:
        snap = await _steam_price_snapshot(str(resolved_app), lng)
        if snap:
            return snap
    return await get_current_price_for_tracked(
        "Steam",
        store_url,
        resolved_app,
        cheapshark_id,
        ui_lang=lng,
    )


async def get_current_price_for_tracked(
    store: str,
    store_url: str,
    app_id: str | None,
    cheapshark_id: str | None,
    ui_lang: str = "ru",
) -> dict[str, Any] | None:
    lng = i18n.normalize_lang(ui_lang)
    user_cur = currency.user_currency(lng)

    resolved = app_id or extract_steam_app_id(store_url)
    if resolved and STEAM_PRICE_LOOKUP_ENABLED:
        steam_price = await _steam_price_snapshot(str(resolved), lng)
        if steam_price:
            return steam_price

    key_candidates: list[dict[str, Any]] = []

    if not cheapshark_id and resolved:
        cs_game = await find_game_by_steam_app_id(str(resolved))
        if cs_game:
            cheapshark_id = str(cs_game.get("gameID", "")) or None

    if cheapshark_id:
        deals = await get_game_deals(cheapshark_id, limit=5)
        for deal in deals:
            if str(deal.get("storeID")) == STEAM_STORE_ID:
                continue
            price_usd = float(deal.get("price", 0))
            amount, _ = await currency.to_user_currency(price_usd, "USD", lng)
            key_candidates.append(
                {
                    "title": None,
                    "price": amount,
                    "currency": user_cur,
                    "price_usd": price_usd,
                    "url": f"https://www.cheapshark.com/redirect.php?dealID={deal.get('dealID', '')}",
                    "source": "key",
                }
            )

    if key_candidates:
        return min(key_candidates, key=lambda c: float(c["price"]))

    return None


async def find_cheapshark_id(title: str, *, app_id: str | None = None, ui_lang: str = "ru") -> str | None:
    if app_id:
        cs = await find_game_by_steam_app_id(str(app_id))
        if cs and cs.get("gameID"):
            return str(cs["gameID"])
    games = await search_games_smart(title, limit=1, ui_lang=ui_lang)
    if games and games[0].get("gameID"):
        return str(games[0]["gameID"]) or None
    return None


async def fetch_epic_free_games() -> list[dict[str, str]]:
    async with _http_session() as session:
        data = await _get_json_safe(session, EPIC_FREE_API)
    if not isinstance(data, dict):
        return []

    results: list[dict[str, str]] = []
    catalog = data.get("data", {}).get("Catalog", {})
    search_store = catalog.get("searchStore", {})
    elements = search_store.get("elements", []) or []

    for item in elements:
        promotions = item.get("promotions") or {}
        promo_offers = promotions.get("promotionalOffers") or []
        if not promo_offers:
            continue
        offers = promo_offers[0].get("promotionalOffers") or []
        for offer in offers:
            if offer.get("discountSetting", {}).get("discountPercentage") != 0:
                continue
            title = item.get("title", "Unknown")
            slug = (item.get("productSlug") or item.get("urlSlug") or "").split("/")[0]
            url = f"https://store.epicgames.com/p/{slug}" if slug else ""
            end_date = offer.get("endDate", "")
            key = f"epic:{item.get('id', slug)}:{end_date}"
            results.append(
                {
                    "key": key,
                    "title": title,
                    "store": "Epic Games Store",
                    "url": url,
                    "end_date": end_date,
                }
            )
    return results


async def fetch_steam_free_weekend() -> list[dict[str, str]]:
    """CheapShark occasionally lists free Steam deals; also check featured specials."""
    results: list[dict[str, str]] = []
    async with _http_session() as session:
        data = await _get_json_safe(
            session,
            f"{CHEAPSHARK_API}/deals",
            params={"storeID": "1", "upperPrice": "0"},
        )
    if data is None:
        return results
    if not isinstance(data, list):
        return results
    for deal in data[:10]:
        price = float(deal.get("price", 1))
        if price > 0.01:
            continue
        title = deal.get("title", "Free game")
        game_id = deal.get("gameID", "")
        key = f"steam-free:{deal.get('dealID', game_id)}"
        url = f"https://www.cheapshark.com/redirect.php?dealID={deal.get('dealID', '')}"
        results.append(
            {
                "key": key,
                "title": title,
                "store": "Steam",
                "url": url,
                "end_date": "",
            }
        )
    return results


async def fetch_all_freebies() -> list[dict[str, str]]:
    epic = await fetch_epic_free_games()
    steam = await fetch_steam_free_weekend()
    seen: set[str] = set()
    merged: list[dict[str, str]] = []
    for item in epic + steam:
        if item["key"] in seen:
            continue
        seen.add(item["key"])
        merged.append(item)
    return merged


async def fetch_steam_news(app_id: str, count: int = 3) -> list[dict[str, str]]:
    if not STEAM_API_ENABLED:
        return []
    async with _http_session() as session:
        try:
            async with session.get(
                STEAM_NEWS_RSS.format(app_id=app_id),
                timeout=STEAM_TIMEOUT,
            ) as resp:
                text = await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            return []

    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return []

    items: list[dict[str, str]] = []
    for item in root.findall(".//item")[:count]:
        guid = (item.findtext("guid") or item.findtext("link") or "").strip()
        title = (item.findtext("title") or "Обновление").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        items.append({"guid": guid, "title": title, "link": link, "pub_date": pub})
    return items


def _format_recorded_date(raw_date: str) -> str:
    try:
        dt = datetime.fromisoformat(raw_date.replace("Z", ""))
    except ValueError:
        dt = datetime.strptime(raw_date[:19], "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%d.%m.%Y %H:%M")


async def analyze_last_price_drop(
    history_rows: list[Any], lang: str
) -> dict[str, str] | None:
    if len(history_rows) < 2:
        return None
    lng = i18n.normalize_lang(lang)
    last: dict[str, str] | None = None
    for i in range(1, len(history_rows)):
        prev_p = float(history_rows[i - 1]["price"])
        cur_p = float(history_rows[i]["price"])
        if cur_p < prev_p - 0.01:
            cur_cur = str(history_rows[i]["currency"] or currency.user_currency(lng))
            prev_cur = str(history_rows[i - 1]["currency"] or cur_cur)
            pct = (prev_p - cur_p) / prev_p * 100 if prev_p > 0 else 0.0
            last = {
                "date": _format_recorded_date(str(history_rows[i]["recorded_at"])),
                "from_p": await currency.format_for_user(prev_p, prev_cur, lng),
                "to_p": await currency.format_for_user(cur_p, cur_cur, lng),
                "pct": pct,
            }
    return last


async def best_deal_savings_percent(game_id: str) -> float:
    if not game_id:
        return 0.0
    deals = await get_game_deals(game_id, limit=12)
    best = 0.0
    for deal in deals:
        try:
            best = max(best, float(deal.get("savings", 0)))
        except (TypeError, ValueError):
            continue
    return best


async def format_sale_hint_for_game(
    game_id: str, game_title: str, lang: str
) -> str:
    lng = i18n.normalize_lang(lang)
    if not use_foreign_key_stores(lng):
        return ""
    savings = await best_deal_savings_percent(game_id)
    if savings > 0:
        return i18n.t("search_on_sale", lng, pct=savings)
    return ""


def build_history_chart(
    game_title: str,
    history_rows: list[Any],
    output_path: str | None = None,
) -> BytesIO | str:
    if not history_rows:
        raise ValueError("Нет данных для графика")

    dates: list[datetime] = []
    prices: list[float] = []
    for row in history_rows:
        raw_date = row["recorded_at"]
        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", ""))
        except ValueError:
            dt = datetime.strptime(raw_date[:19], "%Y-%m-%d %H:%M:%S")
        dates.append(dt)
        prices.append(float(row["price"]))

    cur = history_rows[-1]["currency"] if history_rows else DEFAULT_CURRENCY
    ylabel = "Цена (₽)" if str(cur).upper() == "RUB" else f"Цена ({cur})"

    try:
        plt.style.use("seaborn-v0_8-darkgrid")
    except OSError:
        plt.style.use("ggplot")
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, prices, marker="o", linewidth=2, color="#2ecc71")
    ax.fill_between(dates, prices, alpha=0.15, color="#2ecc71")
    ax.set_title(f"История цен: {game_title}", fontsize=14, fontweight="bold")
    ax.set_xlabel("Дата")
    ax.set_ylabel(ylabel)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    fig.autofmt_xdate()
    ax.grid(True, alpha=0.3)

    if len(prices) >= 2:
        min_p, max_p = min(prices), max(prices)
        min_lbl = currency.format_price(min_p, str(cur))
        max_lbl = currency.format_price(max_p, str(cur))
        ax.annotate(
            f"мин: {min_lbl}",
            xy=(dates[prices.index(min_p)], min_p),
            textcoords="offset points",
            xytext=(0, -15),
            ha="center",
        )
        ax.annotate(
            f"макс: {max_lbl}",
            xy=(dates[prices.index(max_p)], max_p),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
        )

    fig.tight_layout()
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    if output_path:
        fig.savefig(output_path, dpi=120)
        plt.close(fig)
        return output_path

    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=120)
    plt.close(fig)
    buffer.seek(0)
    return buffer
