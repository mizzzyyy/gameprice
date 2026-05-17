import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_PATH = BASE_DIR / "gameprice.db"
CHARTS_DIR = BASE_DIR / "charts"

CHEAPSHARK_API = "https://www.cheapshark.com/api/1.0"
STEAM_STORE_API = "https://store.steampowered.com/api"
STEAM_SEARCH_API = "https://store.steampowered.com/api/storesearch/"

# Сокращения (EN/RU) -> полные названия для CheapShark
SEARCH_ALIASES: dict[str, list[str]] = {
    "gta v": ["Grand Theft Auto V", "Grand Theft Auto V Enhanced"],
    "gta 5": ["Grand Theft Auto V", "Grand Theft Auto V Enhanced"],
    "gta5": ["Grand Theft Auto V Enhanced"],
    "gtav": ["Grand Theft Auto V Enhanced"],
    "гта 5": ["Grand Theft Auto V", "Grand Theft Auto V Enhanced"],
    "гта в": ["Grand Theft Auto V", "Grand Theft Auto V Enhanced"],
    "rdr 2": ["Red Dead Redemption 2"],
    "rdr2": ["Red Dead Redemption 2"],
    "рдр 2": ["Red Dead Redemption 2"],
    "cs2": ["Counter-Strike 2"],
    "cs go": ["Counter-Strike 2"],
    "кс 2": ["Counter-Strike 2"],
    "кс2": ["Counter-Strike 2"],
    "контра": ["Counter-Strike 2"],
    "witcher 3": ["The Witcher 3: Wild Hunt"],
    "ведьмак 3": ["The Witcher 3: Wild Hunt"],
    "ведьмак": ["The Witcher 3: Wild Hunt"],
    "cyberpunk": ["Cyberpunk 2077"],
    "киберпанк": ["Cyberpunk 2077"],
    "киберпанк 2077": ["Cyberpunk 2077"],
    "elden ring": ["Elden Ring"],
    "элден ринг": ["Elden Ring"],
    "раст": ["Rust"],
    "хогвартс": ["Hogwarts Legacy"],
    "старфилд": ["Starfield"],
    "ddnet": ["DDraceNetwork"],
    "dd net": ["DDraceNetwork"],
    "дднет": ["DDraceNetwork"],
    "дд нет": ["DDraceNetwork"],
    "дота 2": ["Dota 2"],
    "дота2": ["Dota 2"],
    "пабг": ["PUBG BATTLEGROUNDS"],
    "фортнайт": ["Fortnite"],
    "валорант": ["VALORANT"],
    "спайдермен": ["Marvel's Spider-Man Remastered"],
    "god of war": ["God of War"],
    "бог войны": ["God of War"],
    "хеллдайверс": ["HELLDIVERS 2"],
    "балдурс гейт": ["Baldur's Gate 3"],
    "балдурс гейт 3": ["Baldur's Gate 3"],
    "сая": ["The Song of Saya", "Saya no Uta"],
    "песня сая": ["The Song of Saya"],
    "song of saya": ["The Song of Saya"],
}
EPIC_FREE_API = (
    "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
    "?locale=ru&country=RU&allowCountries=RU"
)
STEAM_NEWS_RSS = "https://store.steampowered.com/feeds/news/app/{app_id}/"

WISHLIST_CHECK_HOURS = 2
FREEBIE_CHECK_HOURS = 24
PATCH_CHECK_HOURS = 6

STORE_NAMES = {
    "1": "Steam",
    "2": "GamersGate",
    "3": "GreenManGaming",
    "7": "GOG",
    "11": "Humble",
    "13": "Uplay/Ubisoft",
    "23": "GameBillet",
    "25": "Epic Games Store",
    "27": "Gamesplanet",
    "28": "Gamesload",
    "30": "IndieGala",
}

DEFAULT_REGION = "ru"
DEFAULT_CURRENCY = "RUB"
LOCALE = "russian"
CBR_DAILY_URL = "https://www.cbr-xml-daily.ru/daily_json.js"

# Поиск/RSS Steam (может таймаутить без VPN)
STEAM_API_ENABLED = os.getenv("STEAM_API_ENABLED", "0").lower() in ("1", "true", "yes")

# Цена в российском Steam — отдельно, по умолчанию включена
STEAM_PRICE_LOOKUP_ENABLED = os.getenv("STEAM_PRICE_LOOKUP", "1").lower() in (
    "1",
    "true",
    "yes",
)

