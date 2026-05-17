import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile, CallbackQuery, MenuButtonCommands, Message
from aiogram.client.default import DefaultBotProperties

import currency
import db
import i18n
import keyboards
import parser
import scheduler
from config import BOT_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)


class UserForm(StatesGroup):
    waiting_search = State()
    waiting_history = State()
    waiting_add = State()


async def user_lang(telegram_id: int) -> str:
    return i18n.normalize_lang(await db.get_user_language(telegram_id))


async def reply_menu(message: Message, lang: str, text: str, **kwargs) -> Message:
    kwargs.setdefault("reply_markup", keyboards.main_menu(lang))
    return await message.answer(text, **kwargs)


def _is_menu_text(text: str | None) -> bool:
    if not text:
        return False
    for key in ("search", "wishlist", "history", "settings", "help"):
        if text in i18n.all_menu_texts(key):
            return True
    return False


async def send_start(message: Message, lang: str) -> None:
    text = (
        f"🎮 <b>{i18n.t('bot_name', lang)}</b>\n\n"
        f"{i18n.t('start_body', lang)}\n\n"
        f"{i18n.t('menu_hint', lang)}"
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboards.main_menu(lang),
    )
    await message.answer(
        i18n.t("quick_actions_hint", lang),
        parse_mode="HTML",
        reply_markup=keyboards.quick_actions(lang),
    )


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await db.ensure_user(message.from_user.id, message.from_user.username)
    lang = await user_lang(message.from_user.id)
    await send_start(message, lang)


@dp.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    await cmd_start(message, state)


@dp.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    lang = await user_lang(message.from_user.id)
    await message.answer(
        f"{i18n.t('settings_title', lang)}\n"
        f"{i18n.t('settings_lang', lang, lang_name=i18n.lang_display(lang))}\n\n"
        f"{i18n.t('settings_lang_pick', lang)}",
        parse_mode="HTML",
        reply_markup=keyboards.settings_keyboard(lang),
    )


@dp.callback_query(F.data.startswith("lang:"))
async def on_language(callback: CallbackQuery) -> None:
    new_lang = callback.data.split(":", 1)[1]
    if new_lang not in i18n.SUPPORTED_LANGS:
        await callback.answer()
        return
    await db.ensure_user(callback.from_user.id, callback.from_user.username)
    await db.set_user_language(callback.from_user.id, new_lang)
    lang_label = i18n.lang_display(new_lang)
    await callback.answer(i18n.t("lang_changed", new_lang, lang_name=lang_label))
    try:
        await callback.message.edit_text(
            f"{i18n.t('settings_title', new_lang)}\n"
            f"{i18n.t('settings_lang', new_lang, lang_name=lang_label)}",
            parse_mode="HTML",
            reply_markup=keyboards.settings_keyboard(new_lang),
        )
    except Exception:
        pass
    await reply_menu(
        callback.message,
        new_lang,
        i18n.t("lang_changed", new_lang, lang_name=lang_label),
        parse_mode="HTML",
    )


async def run_search(message: Message, query: str, lang: str) -> None:
    await reply_menu(message, lang, i18n.t("search_loading", lang))
    try:
        text = await parser.format_search_results(query, lang)
        await reply_menu(
            message,
            lang,
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as exc:
        logger.exception("search failed")
        await reply_menu(message, lang, i18n.t("search_error", lang, error=exc))


async def _prompt_search(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(UserForm.waiting_search)
    await reply_menu(message, lang, i18n.t("search_wait_name", lang))


async def _prompt_history(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(UserForm.waiting_history)
    await reply_menu(message, lang, i18n.t("history_wait_name", lang))


@dp.message(Command("search"))
async def cmd_search(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
    lang = await user_lang(message.from_user.id)
    query = (command.args or "").strip()
    if not query:
        await _prompt_search(message, state, lang)
        return
    await run_search(message, query, lang)


@dp.message(F.text.in_(i18n.all_menu_texts("search")))
async def menu_search(message: Message, state: FSMContext) -> None:
    lang = await user_lang(message.from_user.id)
    await state.clear()
    await _prompt_search(message, state, lang)


@dp.message(F.text.in_(i18n.all_menu_texts("wishlist")))
async def menu_wishlist(message: Message, state: FSMContext) -> None:
    await state.clear()
    await cmd_list(message)


@dp.message(F.text.in_(i18n.all_menu_texts("history")))
async def menu_history(message: Message, state: FSMContext) -> None:
    lang = await user_lang(message.from_user.id)
    await state.clear()
    await _prompt_history(message, state, lang)


@dp.message(F.text.in_(i18n.all_menu_texts("settings")))
async def menu_settings(message: Message, state: FSMContext) -> None:
    await state.clear()
    await cmd_settings(message)


@dp.message(F.text.in_(i18n.all_menu_texts("help")))
async def menu_help(message: Message, state: FSMContext) -> None:
    await state.clear()
    await cmd_start(message, state)


@dp.message(StateFilter(UserForm.waiting_search))
async def state_search(message: Message, state: FSMContext) -> None:
    if _is_menu_text(message.text):
        return
    lang = await user_lang(message.from_user.id)
    query = (message.text or "").strip()
    await state.clear()
    if not query:
        await reply_menu(message, lang, i18n.t("search_empty", lang), parse_mode="HTML")
        return
    await run_search(message, query, lang)


async def process_add(
    message: Message, url: str, target_price: float, lang: str
) -> None:
    parsed = parser.parse_store_url(url)
    if parsed["store"] == "Unknown":
        await reply_menu(message, lang, i18n.t("add_stores", lang))
        return

    user_cur = currency.user_currency(lang)
    store_url = str(parsed["store_url"] or url)
    app_id = parser.ensure_app_id(url, parsed)
    await reply_menu(message, lang, i18n.t("add_loading", lang))
    title = await parser.resolve_game_title_from_url(url, parsed, ui_lang=lang)
    cheapshark_id = await parser.find_cheapshark_id(
        title, app_id=app_id, ui_lang=lang
    )

    rows_before = await db.list_tracked_games(message.from_user.id)
    list_pos = len(rows_before) + 1

    game_id = await db.add_tracked_game(
        telegram_id=message.from_user.id,
        game_title=title,
        store=str(parsed["store"]),
        store_url=store_url,
        target_price=target_price,
        app_id=app_id,
        cheapshark_id=cheapshark_id,
        currency=user_cur,
    )

    price_info = await parser.fetch_price_for_wishlist(
        store_url, app_id, cheapshark_id, ui_lang=lang
    )
    current = i18n.t("add_price_unknown", lang)
    already_below = False
    if price_info:
        price_val = float(price_info["price"])
        cur = str(price_info.get("currency", user_cur))
        game_key = parser.normalize_game_key(title)
        await db.add_price_record(
            game_key, title, price_val, store=str(parsed["store"]), currency=cur
        )
        await db.update_tracked_price(game_id, price_val)
        current = await currency.format_for_user(
            price_val, cur, lang, show_alt_hint=bool(price_info.get("price_usd"))
        )
        if price_val <= target_price + 0.01:
            already_below = True
            await db.update_tracked_price(game_id, price_val, alert_sent=True)

    await db.ensure_user(message.from_user.id, message.from_user.username)
    target_str = currency.format_price(target_price, user_cur)
    text = i18n.t(
        "add_done",
        lang,
        pos=list_pos,
        title=title,
        store=parsed["store"],
        target=target_str,
        current=current,
    )
    if already_below and price_info:
        text += "\n\n" + i18n.t(
            "add_already_below",
            lang,
            current=current,
            target=target_str,
        )
    await reply_menu(message, lang, text, parse_mode="HTML")


@dp.message(Command("add"))
async def cmd_add(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
    lang = await user_lang(message.from_user.id)
    args = (command.args or "").strip()
    if not args:
        await reply_menu(message, lang, i18n.t("add_format", lang), parse_mode="HTML")
        return

    parts = args.rsplit(maxsplit=1)
    if len(parts) < 2:
        await reply_menu(message, lang, i18n.t("add_no_price", lang))
        return

    url, price_raw = parts[0], parts[1]
    try:
        target_price = float(price_raw.replace(",", "."))
    except ValueError:
        await reply_menu(message, lang, i18n.t("add_price_error", lang), parse_mode="HTML")
        return

    await process_add(message, url, target_price, lang)


@dp.message(StateFilter(UserForm.waiting_add))
async def state_add(message: Message, state: FSMContext) -> None:
    if _is_menu_text(message.text):
        return
    lang = await user_lang(message.from_user.id)
    parts = (message.text or "").strip().rsplit(maxsplit=1)
    await state.clear()
    if len(parts) < 2:
        await reply_menu(message, lang, i18n.t("add_format", lang), parse_mode="HTML")
        return
    url, price_raw = parts[0], parts[1]
    try:
        target_price = float(price_raw.replace(",", "."))
    except ValueError:
        await reply_menu(message, lang, i18n.t("add_price_error", lang), parse_mode="HTML")
        return
    await process_add(message, url, target_price, lang)


@dp.message(Command("list"))
async def cmd_list(message: Message) -> None:
    lang = await user_lang(message.from_user.id)
    rows = await db.list_tracked_games(message.from_user.id)
    if not rows:
        await reply_menu(message, lang, i18n.t("list_empty", lang))
        return

    await message.answer(
        i18n.t("list_header", lang),
        parse_mode="HTML",
        reply_markup=keyboards.main_menu(lang),
    )

    user_cur = currency.user_currency(lang)
    for pos, row in enumerate(rows, start=1):
        app_id = row["app_id"] or parser.extract_steam_app_id(row["store_url"])
        if app_id and not row["app_id"]:
            await db.update_tracked_ids(int(row["id"]), app_id=str(app_id))

        price_info = await parser.fetch_price_for_wishlist(
            row["store_url"],
            str(app_id) if app_id else None,
            row["cheapshark_id"],
            ui_lang=lang,
        )
        target = float(row["target_price"])
        last = "—"
        below_note = ""
        if price_info:
            price_val = float(price_info["price"])
            cur = str(price_info.get("currency", user_cur))
            await db.update_tracked_price(int(row["id"]), price_val)
            last = await currency.format_for_user(price_val, cur, lang)
            if price_val <= target + 0.01:
                below_note = "\n" + i18n.t("list_below_target", lang)
        elif row["last_price"] is not None:
            price_val = float(row["last_price"])
            last = await currency.format_for_user(
                price_val,
                str(row["currency"] or user_cur),
                lang,
            )
            if price_val <= target + 0.01:
                below_note = "\n" + i18n.t("list_below_target", lang)

        caption = (
            i18n.t(
                "list_row",
                lang,
                pos=pos,
                title=row["game_title"],
                store=row["store"],
                target=currency.format_price(target, user_cur),
                last=last,
                url=row["store_url"],
            )
            + below_note
        )
        if app_id:
            icon = await parser.load_steam_icon(str(app_id))
            if icon:
                try:
                    await message.answer_photo(
                        photo=BufferedInputFile(icon.read(), filename=f"{app_id}.jpg"),
                        caption=caption,
                        parse_mode="HTML",
                    )
                    continue
                except Exception:
                    logger.warning("list photo upload failed app_id=%s", app_id)
            try:
                await message.answer_photo(
                    photo=parser.steam_header_url(str(app_id)),
                    caption=caption,
                    parse_mode="HTML",
                )
                continue
            except Exception:
                logger.warning("list photo url failed app_id=%s", app_id)
        await message.answer(caption, parse_mode="HTML", disable_web_page_preview=True)


@dp.message(Command("remove"))
async def cmd_remove(message: Message, command: CommandObject) -> None:
    lang = await user_lang(message.from_user.id)
    arg = (command.args or "").strip()
    if not arg or not arg.isdigit():
        await reply_menu(message, lang, i18n.t("remove_usage", lang), parse_mode="HTML")
        return
    ok = await db.remove_tracked_by_position(message.from_user.id, int(arg))
    await reply_menu(message, lang, i18n.t("remove_ok" if ok else "remove_fail", lang))


@dp.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    lang = await user_lang(message.from_user.id)
    count = await db.clear_wishlist(message.from_user.id)
    await reply_menu(
        message,
        lang,
        i18n.t("clear_ok" if count else "clear_empty", lang),
    )


@dp.callback_query(F.data.startswith("quick:"))
async def on_quick_action(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":", 1)[1]
    lang = await user_lang(callback.from_user.id)
    await callback.answer()

    if action == "search":
        await state.set_state(UserForm.waiting_search)
        await reply_menu(callback.message, lang, i18n.t("search_wait_name", lang))
    elif action == "list":
        await state.clear()
        await cmd_list(callback.message)
    elif action == "add":
        await state.set_state(UserForm.waiting_add)
        await reply_menu(callback.message, lang, i18n.t("add_format", lang), parse_mode="HTML")
    elif action == "clear":
        await state.clear()
        count = await db.clear_wishlist(callback.from_user.id)
        await reply_menu(
            callback.message,
            lang,
            i18n.t("clear_ok" if count else "clear_empty", lang),
        )


async def run_history(message: Message, query: str, lang: str) -> None:
    game_key = parser.normalize_game_key(query)
    title = query
    rows = await db.get_price_history(game_key)
    game_id = ""

    if len(rows) < 2:
        games = await parser.search_games(query, limit=1, ui_lang=lang)
        if games:
            title = str(games[0].get("external", query))
            game_id = str(games[0].get("gameID", "") or "")
            game_key = parser.normalize_game_key(title)
            rows = await db.get_price_history(game_key)
            if len(rows) < 2 and game_id:
                deals = await parser.get_game_deals(game_id, limit=1)
                if deals:
                    price_usd = float(deals[0].get("price", 0))
                    user_cur = currency.user_currency(lang)
                    price_val, _ = await currency.to_user_currency(price_usd, "USD", lang)
                    await db.add_price_record(
                        game_key, title, price_val, store="CheapShark", currency=user_cur
                    )
                    rows = await db.get_price_history(game_key)

    if len(rows) < 2:
        await reply_menu(message, lang, i18n.t("history_low_data", lang))
        return

    if rows and rows[0]["game_title"]:
        title = str(rows[0]["game_title"])

    caption = i18n.t("history_caption", lang, title=title, count=len(rows))
    if not game_id:
        games = await parser.search_games(title, limit=1, ui_lang=lang)
        if games:
            game_id = str(games[0].get("gameID", "") or "")
    if parser.use_foreign_key_stores(lang):
        savings = await parser.best_deal_savings_percent(game_id)
        if savings > 0:
            caption += i18n.t("history_on_sale", lang, pct=savings)

    try:
        chart = parser.build_history_chart(title, rows)
        photo = BufferedInputFile(chart.read(), filename="history.png")
        await message.answer_photo(
            photo,
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboards.main_menu(lang),
        )
    except Exception as exc:
        logger.exception("chart failed")
        await reply_menu(message, lang, i18n.t("chart_error", lang, error=exc))


@dp.message(Command("history"))
async def cmd_history(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
    lang = await user_lang(message.from_user.id)
    query = (command.args or "").strip()
    if not query:
        await _prompt_history(message, state, lang)
        return
    await run_history(message, query, lang)


@dp.message(StateFilter(UserForm.waiting_history))
async def state_history(message: Message, state: FSMContext) -> None:
    if _is_menu_text(message.text):
        return
    lang = await user_lang(message.from_user.id)
    query = (message.text or "").strip()
    await state.clear()
    if not query:
        await reply_menu(message, lang, i18n.t("history_empty", lang), parse_mode="HTML")
        return
    await run_history(message, query, lang)


@dp.message(Command("favorite"))
async def cmd_favorite(message: Message, command: CommandObject) -> None:
    lang = await user_lang(message.from_user.id)
    arg = (command.args or "").strip()
    if not arg or not arg.isdigit():
        await reply_menu(message, lang, i18n.t("favorite_usage", lang), parse_mode="HTML")
        return

    app_id = arg
    info = await parser.get_steam_price(app_id, ui_lang=lang)
    title = (info or {}).get("title") or f"Steam App {app_id}"
    added = await db.add_favorite(message.from_user.id, title, app_id)
    if added:
        await reply_menu(
            message,
            lang,
            i18n.t("favorite_ok", lang, title=title, app_id=app_id),
            parse_mode="HTML",
        )
    else:
        await reply_menu(message, lang, i18n.t("favorite_exists", lang))


@dp.message(F.text.contains("store.steampowered.com"))
async def handle_steam_link(message: Message) -> None:
    lang = await user_lang(message.from_user.id)
    url = next(
        (w for w in message.text.split() if "store.steampowered.com" in w),
        None,
    )
    if not url:
        return
    await reply_menu(
        message,
        lang,
        i18n.t("steam_link_hint", lang, url=url),
        parse_mode="HTML",
    )


async def setup_bot_commands(bot: Bot) -> None:
    for lng in i18n.SUPPORTED_LANGS:
        await bot.set_my_commands(keyboards.bot_commands(lng), language_code=lng)


async def main() -> None:
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не задан. Создай файл .env с BOT_TOKEN=...")
        sys.exit(1)

    await db.init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    await setup_bot_commands(bot)
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    sched = scheduler.setup_scheduler(bot)
    sched.start()

    logger.info("Bot started")
    try:
        await dp.start_polling(bot)
    finally:
        sched.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
