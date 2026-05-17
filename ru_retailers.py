"""Поиск цен и прямых ссылок на игру в российских магазинах."""

from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import quote, urljoin

import aiohttp

logger = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=18, connect=6)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_PRICE_RE = re.compile(r"(\d[\d\s]{2,9})\s*(?:₽|р\.?\b)", re.I)
_PRICE_CLEAN = re.compile(r"[\s₽р.]")

# Не игры: пополнения, валюта, подписки, карты
_JUNK_RE = re.compile(
    r"(?:"
    r"robux|v-?bucks|valorant\s*point|игровая\s*валют|game\s*currency|"
    r"popolnen|пополнен|avtopopolnen|steam\s*rub|steam\s*kzt|steam\s*uah|"
    r"shark\s*card|great\s*white|cash\s*card|gift\s*card|подарочн\w*\s*карт|"
    r"itunes|apple\s*id|playstation\s*(?:пополн|plus\s*pop)|xbox\s*game\s*pass|"
    r"chatgpt|подписк\w*\s+на|subscription|spotify|windows\s*11\s*pro|"
    r"telegram\s*premium|discord\s*nitro|"
    r"coins?\s+free|apex\s*coins|fc\s*points|vbucks|"
    r"\+games\b|\+ground\b|набор\s+из\s+\d|bundle\s+of\s+\d"
    r")",
    re.I,
)

_DLC_ONLY_RE = re.compile(
    r"(?:\bdlc\b|supporter\s*pack|expansion\s*pass|season\s*pass|"
    r"дополнен|расширен|upgrade\s*pack)",
    re.I,
)

_H1_RE = re.compile(r"<h1[^>]*>([^<]{4,120})</h1>", re.I)
_TITLE_TAG_RE = re.compile(r"<title>([^<]{4,160})</title>", re.I)
_GGSEL_PRODUCT_RE = re.compile(
    r'href="(?P<path>/catalog/product/[a-z0-9-]+)"',
    re.I,
)


def _parse_rub(text: str) -> float | None:
    m = _PRICE_RE.search(text)
    if not m:
        return None
    cleaned = _PRICE_CLEAN.sub("", m.group(1))
    try:
        return float(cleaned)
    except ValueError:
        return None


def _norm_title(text: str) -> str:
    return re.sub(r"[^a-z0-9а-яё]+", " ", text.lower()).strip()


def _query_tokens(query: str) -> list[str]:
    return [w for w in _norm_title(query).split() if len(w) >= 3]


def _slugify(query: str) -> str:
    s = query.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _title_score(query: str, title: str) -> float:
    q = _norm_title(query)
    t = _norm_title(title)
    if not q or not t:
        return 0.0
    if q in t or t in q:
        return 0.95
    q_words = _query_tokens(query)
    if q_words:
        hits = sum(1 for w in q_words if w in t)
        if hits >= len(q_words):
            return 0.9
        if hits >= max(1, len(q_words) - 1):
            return 0.78
    return SequenceMatcher(None, q, t).ratio()


def _matches_game(query: str, *texts: str, min_score: float = 0.55) -> bool:
    combined = " ".join(t for t in texts if t)
    if not combined.strip():
        return False
    if _JUNK_RE.search(combined):
        return False
    tokens = _query_tokens(query)
    if not tokens:
        return _title_score(query, combined) >= min_score
    flat = re.sub(r"[^a-z0-9а-яё]+", "", combined.lower())
    primary = max(tokens, key=len)
    primary_flat = re.sub(r"[^a-z0-9а-яё]+", "", primary)
    if primary_flat and primary_flat not in flat:
        return _title_score(query, combined) >= min_score + 0.12
    hits = sum(1 for w in tokens if w in _norm_title(combined))
    if hits < max(1, int(len(tokens) * 0.7)):
        return _title_score(query, combined) >= min_score + 0.1
    return True


def _skip_dlc(query: str, title: str) -> bool:
    if _DLC_ONLY_RE.search(title) and not _DLC_ONLY_RE.search(query):
        qn = _norm_title(query)
        tn = _norm_title(title)
        if qn and qn.split()[0] not in tn.split()[:3]:
            return True
    return False


def _clean_product_title(raw: str, query: str) -> str:
    t = re.sub(r"\s+", " ", raw).strip()
    t = re.sub(r"^(?:купить|buy)\s+", "", t, flags=re.I)
    t = re.sub(r"\s*[-|].*?(?:kupikod|ggsel|steambuy|plati).*$", "", t, flags=re.I)
    if len(t) > 72:
        t = t[:69] + "…"
    return t or query.strip()


async def _fetch(session: aiohttp.ClientSession, url: str) -> str | None:
    try:
        async with session.get(url, timeout=_TIMEOUT, headers=_HEADERS) as resp:
            if resp.status != 200:
                logger.debug("RU store %s -> HTTP %s", url, resp.status)
                return None
            return await resp.text(errors="ignore")
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
        logger.debug("RU store fetch %s: %s", url, exc)
        return None


def _page_title(html: str, fallback: str) -> str:
    m = _H1_RE.search(html)
    if m:
        return _clean_product_title(m.group(1), fallback)
    m = _TITLE_TAG_RE.search(html)
    if m:
        return _clean_product_title(m.group(1), fallback)
    return fallback


def _offer(
    store: str,
    product: str,
    url: str,
    price_rub: float | None,
    *,
    score: float = 0.0,
) -> dict[str, Any]:
    return {
        "store": store,
        "product": product,
        "title": product,
        "price_rub": price_rub,
        "url": url,
        "_score": score,
    }


def _best_per_store(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for o in offers:
        store = str(o.get("store", ""))
        if not store:
            continue
        cur = best.get(store)
        if cur is None:
            best[store] = o
            continue
        o_score = float(o.get("_score", 0))
        c_score = float(cur.get("_score", 0))
        o_price = o.get("price_rub")
        c_price = cur.get("price_rub")
        if o_score > c_score + 0.05:
            best[store] = o
        elif abs(o_score - c_score) < 0.06:
            if o_price is not None and (c_price is None or o_price < c_price):
                best[store] = o
    out = list(best.values())
    for o in out:
        o.pop("_score", None)
    out.sort(key=lambda x: (x.get("price_rub") is None, x.get("price_rub") or 10**9))
    return out


async def search_kupikod(
    query: str,
    *,
    steam_app_id: str | None = None,
    limit: int = 1,
) -> list[dict[str, Any]]:
    q = query.strip()
    if not q:
        return []

    slug = _slugify(q)
    if not slug:
        return []

    paths = [
        f"{slug}-steam-rucis",
        f"{slug}-steam-gl",
        f"{slug}-steam",
    ]
    if steam_app_id:
        paths.insert(0, f"{slug}-steam-rucis")

    offers: list[dict[str, Any]] = []
    async with aiohttp.ClientSession(trust_env=True) as session:
        for path in paths:
            url = f"https://kupikod.com/shop/{path}"
            html = await _fetch(session, url)
            if not html:
                continue
            if "404" in html[:800] and "не найден" in html.lower():
                continue
            product = _page_title(html, q)
            if not _matches_game(q, product, path.replace("-", " ")):
                continue
            if _skip_dlc(q, product):
                continue
            price = _parse_rub(html[:12_000])
            offers.append(
                _offer(
                    "Kupikod",
                    product,
                    url,
                    price,
                    score=_title_score(q, product) + (0.05 if price else 0),
                )
            )
            break

    return offers[:limit]


async def search_plati(query: str, limit: int = 1) -> list[dict[str, Any]]:
    q = query.strip()
    if not q:
        return []

    api_url = (
        "https://plati.io/api/search.ashx?"
        f"query={quote(q)}&pagesize=20&pagenum=1"
    )
    offers: list[dict[str, Any]] = []

    try:
        async with aiohttp.ClientSession(trust_env=True) as session:
            async with session.get(
                api_url, timeout=_TIMEOUT, headers=_HEADERS
            ) as resp:
                if resp.status != 200:
                    return []
                raw = await resp.text(errors="ignore")
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
        logger.debug("Plati API: %s", exc)
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        logger.debug("Plati API: invalid XML")
        return []

    for item in root.findall("item"):
        name_el = item.find("name")
        url_el = item.find("url")
        price_el = item.find("price_rur")
        translit_el = item.find("name_translit")
        if name_el is None or url_el is None:
            continue
        name = (name_el.text or "").strip()
        url = (url_el.text or "").strip()
        slug = (translit_el.text or "").strip() if translit_el is not None else ""
        if not name or not url:
            continue
        if not _matches_game(q, name, slug):
            continue
        if _skip_dlc(q, name):
            continue
        price: float | None = None
        if price_el is not None and price_el.text:
            try:
                price = float(price_el.text.strip())
            except ValueError:
                price = None
        if not url.startswith("http"):
            url = urljoin("https://plati.market", url)
        score = _title_score(q, name)
        if price is not None:
            score += 0.02
        offers.append(_offer("Plati.market", _clean_product_title(name, q), url, price, score=score))

    offers.sort(key=lambda x: (-float(x.get("_score", 0)), x.get("price_rub") or 10**9))
    return offers[:limit]


async def search_ggsel(query: str, limit: int = 1) -> list[dict[str, Any]]:
    q = query.strip()
    if not q:
        return []

    slug = _slugify(q)
    urls = [
        f"https://ggsel.net/catalog/{slug}-steam",
        f"https://ggsel.net/catalog/{slug}",
        f"https://ggsel.net/catalog/search?search={quote(q)}",
    ]
    headers = {
        **_HEADERS,
        "Referer": "https://ggsel.net/",
    }

    async with aiohttp.ClientSession(trust_env=True) as session:
        for url in urls:
            try:
                async with session.get(url, timeout=_TIMEOUT, headers=headers) as resp:
                    if resp.status != 200:
                        continue
                    html = await resp.text(errors="ignore")
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                continue

            candidates: list[dict[str, Any]] = []
            for m in _GGSEL_PRODUCT_RE.finditer(html):
                path = m.group("path")
                slug_hint = path.rsplit("/", 1)[-1].replace("-", " ")
                chunk = html[max(0, m.start() - 500) : m.end() + 300]
                title_m = re.search(r'alt="([^"]{8,120})"', chunk)
                title = title_m.group(1) if title_m else slug_hint
                if not _matches_game(q, title, slug_hint):
                    continue
                if _skip_dlc(q, title):
                    continue
                price = _parse_rub(chunk)
                full = urljoin("https://ggsel.net", path)
                candidates.append(
                    _offer(
                        "GGSEL",
                        _clean_product_title(title, q),
                        full,
                        price,
                        score=_title_score(q, title),
                    )
                )

            if candidates:
                candidates.sort(
                    key=lambda x: (-float(x.get("_score", 0)), x.get("price_rub") or 10**9)
                )
                return candidates[:limit]

    return []


async def search_steambuy(query: str, limit: int = 1) -> list[dict[str, Any]]:
    q = query.strip()
    if not q:
        return []

    slug = _slugify(q)
    urls = [
        f"https://steambuy.com/steam/{slug}-russia/",
        f"https://steambuy.com/steam/{slug}/",
    ]

    async with aiohttp.ClientSession(trust_env=True) as session:
        for url in urls:
            html = await _fetch(session, url)
            if not html:
                continue
            if "НЕ НАЙДЕНО" in html and f"Купить {q}" not in html and slug not in html.lower():
                continue
            product = _page_title(html, q)
            if not _matches_game(q, product, slug):
                continue
            if _skip_dlc(q, product):
                continue
            price = _parse_rub(html[:15_000])
            return [
                _offer(
                    "Steambuy",
                    product,
                    url,
                    price,
                    score=_title_score(q, product),
                )
            ][:limit]

    return []


async def collect_ru_store_offers(
    query: str,
    steam_app_id: str | None = None,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """Параллельный поиск; одно лучшее предложение на магазин."""
    q = query.strip()
    if not q:
        return []

    kupikod, ggsel, plati, steambuy = await asyncio.gather(
        search_kupikod(q, steam_app_id=steam_app_id, limit=1),
        search_ggsel(q, limit=1),
        search_plati(q, limit=1),
        search_steambuy(q, limit=1),
    )

    merged = _best_per_store([*kupikod, *ggsel, *plati, *steambuy])
    return merged[:limit]
