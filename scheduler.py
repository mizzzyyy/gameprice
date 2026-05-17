import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import currency
import db
import i18n
import parser
from config import FREEBIE_CHECK_HOURS, PATCH_CHECK_HOURS, WISHLIST_CHECK_HOURS

logger = logging.getLogger(__name__)


async def check_wishlist(bot: Bot) -> None:
    items = await db.get_all_tracked_for_monitoring()
    for row in items:
        lang = i18n.normalize_lang(await db.get_user_language(row["telegram_id"]))
        user_cur = currency.user_currency(lang)
        app_id = row["app_id"] or parser.extract_steam_app_id(row["store_url"])
        price_info = await parser.fetch_price_for_wishlist(
            row["store_url"],
            str(app_id) if app_id else None,
            row["cheapshark_id"],
            ui_lang=lang,
        )
        if not price_info:
            continue

        price_val = float(price_info["price"])
        cur = str(price_info.get("currency", user_cur))
        game_key = parser.normalize_game_key(row["game_title"])

        await db.add_price_record(
            game_key,
            row["game_title"],
            price_val,
            store=row["store"],
            currency=cur,
        )
        await db.update_tracked_price(row["id"], price_val)

        target = float(row["target_price"])
        if price_val <= target and not row["alert_sent"]:
            url = price_info.get("url") or row["store_url"]
            now_str = await currency.format_for_user(price_val, cur, lang)
            target_str = currency.format_price(target, user_cur)
            text = (
                f"{i18n.t('alert_drop', lang)}\n\n"
                f"🎮 {row['game_title']}\n"
                f"{i18n.t('alert_now', lang, now=now_str, target=target_str)}\n"
                f"<a href='{url}'>{i18n.t('alert_open', lang)}</a>"
            )
            try:
                await bot.send_message(row["telegram_id"], text, parse_mode="HTML")
                await db.update_tracked_price(row["id"], price_val, alert_sent=True)
            except Exception:
                logger.exception("Failed to send wishlist alert to %s", row["telegram_id"])


async def check_freebies(bot: Bot) -> None:
    freebies = await parser.fetch_all_freebies()
    user_ids = await db.get_all_user_ids()
    seed_only = await db.is_freebie_cache_empty()

    for item in freebies:
        if await db.is_freebie_known(item["key"]):
            continue
        await db.mark_freebie_notified(
            item["key"], item["title"], item["store"], item.get("url")
        )
        if seed_only or not user_ids:
            continue
        end = item.get("end_date", "")
        for uid in user_ids:
            lang = i18n.normalize_lang(await db.get_user_language(uid))
            end_line = f"\n{i18n.t('freebie_until', lang, date=end[:10])}" if end else ""
            text = (
                f"{i18n.t('freebie', lang)}\n\n"
                f"{item['title']}\n"
                f"{i18n.t('freebie_store', lang, store=item['store'])}{end_line}\n"
            )
            if item.get("url"):
                text += f"<a href='{item['url']}'>{i18n.t('freebie_get', lang)}</a>"
            try:
                await bot.send_message(uid, text, parse_mode="HTML")
            except Exception:
                logger.exception("Failed freebie notify %s", uid)


async def check_patches(bot: Bot) -> None:
    favorites = await db.list_favorites()
    for fav in favorites:
        lang = i18n.normalize_lang(await db.get_user_language(fav["telegram_id"]))
        news = await parser.fetch_steam_news(fav["app_id"], count=1)
        if not news:
            continue
        latest = news[0]
        guid = latest["guid"]
        if fav["last_patch_guid"] == guid:
            continue

        if fav["last_patch_guid"]:
            text = f"{i18n.t('patch_title', lang, game=fav['game_title'])}\n\n{latest['title']}\n"
            if latest.get("link"):
                text += f"<a href='{latest['link']}'>{i18n.t('patch_read', lang)}</a>"
            try:
                await bot.send_message(fav["telegram_id"], text, parse_mode="HTML")
            except Exception:
                logger.exception("Patch notify failed for %s", fav["telegram_id"])

        await db.update_favorite_patch_guid(fav["id"], guid)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_wishlist,
        "interval",
        hours=WISHLIST_CHECK_HOURS,
        args=[bot],
        id="wishlist",
        replace_existing=True,
    )
    scheduler.add_job(
        check_freebies,
        "interval",
        hours=FREEBIE_CHECK_HOURS,
        args=[bot],
        id="freebies",
        replace_existing=True,
    )
    scheduler.add_job(
        check_patches,
        "interval",
        hours=PATCH_CHECK_HOURS,
        args=[bot],
        id="patches",
        replace_existing=True,
    )
    return scheduler
