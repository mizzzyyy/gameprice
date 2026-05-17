from aiogram.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

import i18n


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    labels = i18n.menu_labels(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=labels["search"]),
                KeyboardButton(text=labels["wishlist"]),
            ],
            [
                KeyboardButton(text=labels["history"]),
                KeyboardButton(text=labels["settings"]),
            ],
            [KeyboardButton(text=labels["help"])],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=(
            "Название игры или /search …"
            if lang == "ru"
            else "Game name or /search …"
        ),
    )


def quick_actions(lang: str) -> InlineKeyboardMarkup:
    lng = i18n.normalize_lang(lang)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.t("btn_quick_search", lng),
                    callback_data="quick:search",
                ),
                InlineKeyboardButton(
                    text=i18n.t("btn_quick_list", lng),
                    callback_data="quick:list",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t("btn_quick_add", lng),
                    callback_data="quick:add",
                ),
                InlineKeyboardButton(
                    text=i18n.t("btn_quick_clear", lng),
                    callback_data="quick:clear",
                ),
            ],
        ]
    )


def settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.t("lang_ru", lang),
                    callback_data="lang:ru",
                ),
                InlineKeyboardButton(
                    text=i18n.t("lang_en", lang),
                    callback_data="lang:en",
                ),
            ],
        ]
    )


def bot_commands(lang: str) -> list[BotCommand]:
    return [
        BotCommand(command="start", description=i18n.t("cmd_start", lang)),
        BotCommand(command="search", description=i18n.t("cmd_search", lang)),
        BotCommand(command="add", description=i18n.t("cmd_add", lang)),
        BotCommand(command="list", description=i18n.t("cmd_list", lang)),
        BotCommand(command="remove", description=i18n.t("cmd_remove", lang)),
        BotCommand(command="clear", description=i18n.t("cmd_clear", lang)),
        BotCommand(command="history", description=i18n.t("cmd_history", lang)),
        BotCommand(command="settings", description=i18n.t("cmd_settings", lang)),
        BotCommand(command="help", description=i18n.t("cmd_help", lang)),
    ]
