from typing import Any

SUPPORTED_LANGS = ("ru", "en")
DEFAULT_LANG = "ru"

_STRINGS: dict[str, dict[str, str]] = {
    "ru": {
        "bot_name": "GamePrice Watcher",
        "start_body": (
            "Мониторинг цен, сбор ключей, халява и графики.\n"
            "Регион по умолчанию: <b>Россия (₽)</b>."
        ),
        "menu_hint": "Кнопки меню ниже. Команды: <b>/search</b>, <b>/history</b>, <b>/list</b>",
        "quick_actions_hint": "Быстрые действия (нажми):",
        "btn_search": "🔍 Поиск",
        "btn_wishlist": "📋 Список",
        "btn_history": "📜 История",
        "btn_settings": "⚙️ Настройки",
        "btn_help": "❓ Справка",
        "cmd_start": "Запуск и меню",
        "cmd_search": "Найти игру",
        "cmd_add": "Добавить в список",
        "cmd_list": "Мой список",
        "cmd_remove": "Удалить из списка",
        "cmd_clear": "Очистить список",
        "cmd_history": "График цен",
        "btn_quick_search": "🔍 Поиск",
        "btn_quick_list": "📋 Список",
        "btn_quick_add": "➕ Добавить",
        "btn_quick_clear": "🗑 Очистить",
        "cmd_settings": "Язык и настройки",
        "cmd_help": "Помощь",
        "cmd_favorite": "Патчи Steam",
        "search_wait_name": "Напиши название игры или ссылку Steam следующим сообщением.",
        "search_prompt": (
            "Введи название, ссылку Steam или: <code>/search название</code>\n"
            "Пример ссылки: <code>https://store.steampowered.com/app/1091500/</code>"
        ),
        "search_empty": "Укажи название или ссылку Steam: <code>/search GTA V</code>",
        "search_loading": "🔍 Ищу лучшие цены...",
        "search_error": "Ошибка поиска: {error}",
        "history_wait_name": "Напиши название игры для графика следующим сообщением.",
        "history_prompt": "Введи название для графика или: <code>/history название</code>",
        "history_empty": "Укажи название: <code>/history Cyberpunk</code>",
        "ru_stores_header": "🇷🇺 Российские магазины:",
        "ru_store_price": "  • <b>{store}</b> — {product}: {price} (<a href='{url}'>{open}</a>)",
        "ru_store_link": "  • <b>{store}</b> — {product} (<a href='{url}'>{open}</a>)",
        "ru_store_open": "открыть",
        "ru_stores_empty": "  <i>Цены на RU-площадках не найдены — попробуй полное название.</i>",
        "history_low_data": (
            "Мало данных для графика.\n"
            "Добавь игру через /add и подожди проверки, или сделай /search."
        ),
        "history_caption": "📈 История цен: {title} ({count} записей)",
        "history_last_drop": (
            "\n📉 Последнее снижение: <b>{date}</b>\n"
            "{from_p} → {to_p} (−{pct:.0f}%)"
        ),
        "history_on_sale": "\n🔥 Сейчас скидка до <b>{pct:.0f}%</b> на ключи",
        "search_on_sale": "🔥 Скидка до <b>{pct:.0f}%</b> на ключи",
        "search_best_price": "💰 <b>от {price}</b>",
        "search_price_row": "  {label} — {price}",
        "search_price_row_link": "  {label} — {price} (<a href='{url}'>{open}</a>)",
        "price_row_keys": "Ключи (заруб.)",
        "price_row_steam_foreign": "Steam (заруб.)",
        "chart_error": "Не удалось построить график: {error}",
        "settings_title": "⚙️ <b>Настройки</b>",
        "settings_lang": "Язык интерфейса: <b>{lang_name}</b>",
        "settings_lang_pick": "Выбери язык / Choose language:",
        "lang_changed": "✅ Язык изменён на <b>{lang_name}</b>",
        "add_already_below": (
            "🎉 <b>Цена уже ниже порога!</b>\n"
            "Сейчас: <b>{current}</b> — ты указал ≤ <b>{target}</b>\n"
            "Можно покупать или ждать ещё большей скидки."
        ),
        "lang_ru": "🇷🇺 Русский",
        "lang_en": "🇬🇧 English",
        "add_format": (
            "Формат: <code>/add ссылка цена_в_рублях</code>\n"
            "Пример: <code>/add https://store.steampowered.com/app/1091500/ 1500</code>"
        ),
        "add_price_error": "Цена в рублях, например: <code>1500</code>",
        "add_no_price": "Не хватает цены в конце команды.",
        "add_loading": "⏳ Добавляю в список...",
        "add_stores": "Поддерживаются ссылки Steam и Epic Games Store.",
        "add_done": (
            "✅ Добавлено (№{pos} в списке)\n\n"
            "🎮 <b>{title}</b>\n"
            "Магазин: {store}\n"
            "Порог: <b>{target}</b>\n"
            "Сейчас: {current}\n\n"
            "Проверка каждые 2 ч. Уведомление, когда цена ниже порога."
        ),
        "add_price_unknown": "не удалось получить",
        "list_empty": "Список пуст. Добавь: /add ссылка цена",
        "list_header": "📋 <b>Твой список желаемого:</b>",
        "list_row": "<b>#{pos}</b> {title}\n  {store} | порог: {target} | сейчас: {last}\n  <a href='{url}'>ссылка</a>",
        "list_below_target": "🎉 <i>уже ниже порога — можно покупать</i>",
        "remove_usage": "Номер из /list: <code>/remove 1</code> (первая строка = 1)",
        "clear_ok": "Список очищен.",
        "clear_empty": "Список уже пуст.",
        "remove_ok": "Удалено.",
        "remove_fail": "Игра не найдена.",
        "favorite_usage": (
            "Укажи Steam AppID: <code>/favorite 1091500</code>\n"
            "(число из URL store.steampowered.com/app/<b>ID</b>/)"
        ),
        "favorite_ok": "⭐ Патчи: <b>{title}</b> (AppID {app_id})",
        "favorite_exists": "Уже в избранном.",
        "steam_link_hint": (
            "Чтобы отслеживать цену:\n"
            "<code>/add {url} 1500</code>\n(замени 1500 на желаемую цену в ₽)"
        ),
        "not_found": (
            "Игры не найдены.\n"
            "Попробуй полное название, например: <code>Grand Theft Auto V</code>"
        ),
        "rate_cbr": "Курс ЦБ: 1 $ = {rate:.2f} ₽",
        "steam_ru_price": "🇷🇺 Steam (магазин РФ): {price}",
        "steam_us_price": "🇺🇸 Steam (US store): {price}",
        "price_free": "бесплатно",
        "steam_ru_free": "🇷🇺 Steam (магазин РФ): бесплатно",
        "steam_us_free": "🇺🇸 Steam (US store): free",
        "steam_buy": "Купить в Steam",
        "steam_open": "Открыть в Steam",
        "steam_unavailable": "🚫 <b>Нет в Steam (РФ)</b> — игра не продаётся в российском регионе",
        "steam_unavailable_us": "🚫 <b>Not on Steam (US)</b> — no US store listing",
        "steam_foreign_only": "🌍 Только зарубежный Steam: от {price}",
        "dlc_header": "📦 DLC (Steam РФ):",
        "was_price": "было {price}",
        "steam_error": (
            "⚠️ Steam (РФ): не удалось загрузить цену — "
            "нужен доступ к store.steampowered.com (VPN) или укажи HTTP_PROXY в .env"
        ),
        "keys_from": "Ключи (зарубежные, от)",
        "keys_min": "Мин. цена (ключи, от)",
        "other_stores": "Другие магазины (ключи, пересчёт по курсу ЦБ):",
        "keys_foreign_note": "Зарубежные ключи (для сравнения с Steam РФ):",
        "best_deal": "Лучшая сделка",
        "deal_buy": "Купить ключ",
        "foreign_key_hint": "Зарубежный ключ, не цена российского Steam",
        "steam_key_hint": "Ключ для другого региона Steam, не магазин РФ",
        "steam_appid": "Steam AppID",
        "alert_drop": "🔔 <b>Цена упала!</b>",
        "alert_now": "Сейчас: <b>{now}</b> (порог: {target})",
        "alert_open": "Открыть в магазине",
        "freebie": "🎁 <b>Бесплатная раздача!</b>",
        "freebie_store": "Магазин: {store}",
        "freebie_until": "⏳ До: {date}",
        "freebie_get": "Забрать",
        "patch_title": "📰 <b>Обновление: {game}</b>",
        "patch_read": "Читать патчноут",
    },
    "en": {
        "bot_name": "GamePrice Watcher",
        "start_body": (
            "Price tracking, key shop deals, freebies and charts.\n"
            "Steam RU prices in ₽; key shops in <b>USD</b>."
        ),
        "menu_hint": "Use the menu below. Commands: <b>/search</b>, <b>/history</b>, <b>/list</b>",
        "quick_actions_hint": "Quick actions (tap):",
        "btn_search": "🔍 Search",
        "btn_wishlist": "📋 Wishlist",
        "btn_history": "📜 History",
        "btn_settings": "⚙️ Settings",
        "btn_help": "❓ Help",
        "cmd_start": "Start & menu",
        "cmd_search": "Find a game",
        "cmd_add": "Add to wishlist",
        "cmd_list": "My wishlist",
        "cmd_remove": "Remove from list",
        "cmd_clear": "Clear wishlist",
        "cmd_history": "Price chart",
        "btn_quick_search": "🔍 Search",
        "btn_quick_list": "📋 List",
        "btn_quick_add": "➕ Add",
        "btn_quick_clear": "🗑 Clear",
        "cmd_settings": "Language & settings",
        "cmd_help": "Help",
        "cmd_favorite": "Steam patch news",
        "search_wait_name": "Send the game name or Steam link in your next message.",
        "search_prompt": (
            "Send a game name, Steam link, or: <code>/search name</code>\n"
            "Link example: <code>https://store.steampowered.com/app/1091500/</code>"
        ),
        "search_empty": "Enter a name or Steam link: <code>/search GTA V</code>",
        "search_loading": "🔍 Searching best prices...",
        "search_error": "Search error: {error}",
        "history_wait_name": "Send the game name for the chart in your next message.",
        "history_prompt": "Send a title for the chart, or: <code>/history name</code>",
        "history_empty": "Enter a title: <code>/history Cyberpunk</code>",
        "ru_stores_header": "🇷🇺 Russian stores:",
        "ru_store_price": "  • <b>{store}</b> — {product}: {price} (<a href='{url}'>{open}</a>)",
        "ru_store_link": "  • <b>{store}</b> — {product} (<a href='{url}'>{open}</a>)",
        "ru_store_open": "open",
        "ru_stores_empty": "  <i>No RU store listings found — try the full game title.</i>",
        "history_low_data": "Not enough data. Use /add and wait, or /search first.",
        "history_caption": "📈 Price history: {title} ({count} points)",
        "history_last_drop": (
            "\n📉 Last price drop: <b>{date}</b>\n"
            "{from_p} → {to_p} (−{pct:.0f}%)"
        ),
        "history_on_sale": "\n🔥 On sale now: up to <b>{pct:.0f}%</b> off keys",
        "search_on_sale": "🔥 Up to <b>{pct:.0f}%</b> off keys",
        "search_best_price": "💰 <b>from {price}</b>",
        "search_price_row": "  {label} — {price}",
        "search_price_row_link": "  {label} — {price} (<a href='{url}'>{open}</a>)",
        "price_row_keys": "Keys (intl.)",
        "price_row_steam_foreign": "Steam (intl.)",
        "chart_error": "Chart failed: {error}",
        "settings_title": "⚙️ <b>Settings</b>",
        "settings_lang": "Interface language: <b>{lang_name}</b>",
        "settings_lang_pick": "Choose language / Выбери язык:",
        "lang_changed": "✅ Language set to <b>{lang_name}</b>",
        "add_already_below": (
            "🎉 <b>Price is already below your target!</b>\n"
            "Now: <b>{current}</b> — you wanted ≤ <b>{target}</b>\n"
            "Good time to buy or wait for an even lower price."
        ),
        "lang_ru": "🇷🇺 Русский",
        "lang_en": "🇬🇧 English",
        "add_format": (
            "Format: <code>/add url target_price_usd</code>\n"
            "Example: <code>/add https://store.steampowered.com/app/1091500/ 15</code>"
        ),
        "add_price_error": "Price in USD, e.g. <code>15</code>",
        "add_no_price": "Missing target price at the end.",
        "add_loading": "⏳ Adding to wishlist...",
        "add_stores": "Steam and Epic Games Store links are supported.",
        "add_done": (
            "✅ Added (list #{pos})\n\n"
            "🎮 <b>{title}</b>\n"
            "Store: {store}\n"
            "Target: <b>{target}</b>\n"
            "Now: {current}\n\n"
            "Checked every 2 h. Alert when price drops below target."
        ),
        "add_price_unknown": "could not fetch",
        "list_empty": "Wishlist is empty. Use /add url price",
        "list_header": "📋 <b>Your wishlist:</b>",
        "list_row": "<b>#{pos}</b> {title}\n  {store} | target: {target} | now: {last}\n  <a href='{url}'>link</a>",
        "list_below_target": "🎉 <i>already below target — good time to buy</i>",
        "remove_usage": "Number from /list: <code>/remove 1</code> (first row = 1)",
        "clear_ok": "Wishlist cleared.",
        "clear_empty": "Wishlist is already empty.",
        "remove_ok": "Removed.",
        "remove_fail": "Game not found.",
        "favorite_usage": (
            "Steam AppID: <code>/favorite 1091500</code>\n"
            "(from store.steampowered.com/app/<b>ID</b>/)"
        ),
        "favorite_ok": "⭐ Patch alerts: <b>{title}</b> (AppID {app_id})",
        "favorite_exists": "Already in favorites.",
        "steam_link_hint": (
            "To track price:\n"
            "<code>/add {url} 1500</code>\n(replace 1500 with your target in ₽)"
        ),
        "not_found": (
            "No games found.\n"
            "Try the full title, e.g. <code>Grand Theft Auto V</code>"
        ),
        "rate_cbr": "CBR rate: 1 $ = {rate:.2f} ₽",
        "steam_ru_price": "🇷🇺 Steam (RU store): {price}",
        "steam_us_price": "🇺🇸 Steam (US store): {price}",
        "price_free": "free",
        "steam_ru_free": "🇷🇺 Steam (RU store): free",
        "steam_us_free": "🇺🇸 Steam (US store): free",
        "steam_buy": "Buy on Steam",
        "steam_open": "Open on Steam",
        "steam_unavailable": "🚫 <b>Not sold on Steam (RU)</b> — no RU store listing",
        "steam_unavailable_us": "🚫 <b>Not on Steam (US)</b> — no US store listing",
        "steam_foreign_only": "🌍 Foreign Steam only: from {price}",
        "dlc_header": "📦 DLC (Steam RU):",
        "was_price": "was {price}",
        "steam_error": (
            "⚠️ Steam (RU): could not load price — "
            "need access to store.steampowered.com (VPN) or HTTP_PROXY in .env"
        ),
        "keys_from": "Keys (foreign, from)",
        "keys_min": "Min. key price (from)",
        "other_stores": "Other stores (foreign keys):",
        "keys_foreign_note": "Foreign keys (compare with your Steam store):",
        "best_deal": "Best deal",
        "deal_buy": "Buy key",
        "steam_appid": "Steam AppID",
        "alert_drop": "🔔 <b>Price drop!</b>",
        "alert_now": "Now: <b>{now}</b> (target: {target})",
        "alert_open": "Open store",
        "freebie": "🎁 <b>Free giveaway!</b>",
        "freebie_store": "Store: {store}",
        "freebie_until": "⏳ Until: {date}",
        "freebie_get": "Claim",
        "patch_title": "📰 <b>Update: {game}</b>",
        "patch_read": "Read patch notes",
    },
}


def normalize_lang(lang: str | None) -> str:
    if lang and lang.lower() in SUPPORTED_LANGS:
        return lang.lower()
    return DEFAULT_LANG


def t(key: str, lang: str | None = None, /, **kwargs: Any) -> str:
    lng = normalize_lang(lang)
    text = _STRINGS.get(lng, _STRINGS[DEFAULT_LANG]).get(
        key, _STRINGS[DEFAULT_LANG].get(key, key)
    )
    if kwargs:
        return text.format(**kwargs)
    return text


def lang_display(lang: str) -> str:
    return "Русский" if normalize_lang(lang) == "ru" else "English"


def menu_labels(lang: str) -> dict[str, str]:
    lng = normalize_lang(lang)
    return {
        "search": t("btn_search", lng),
        "wishlist": t("btn_wishlist", lng),
        "history": t("btn_history", lng),
        "settings": t("btn_settings", lng),
        "help": t("btn_help", lng),
    }


_LEGACY_MENU: dict[str, list[str]] = {
    "search": ["🔍 /search", "/search"],
    "history": ["📜 /history", "/history", "📈 История", "📈 History"],
}


def all_menu_texts(key: str) -> list[str]:
    texts = [menu_labels(l)[key] for l in SUPPORTED_LANGS]
    texts.extend(_LEGACY_MENU.get(key, []))
    return texts
