import aiosqlite

from config import DATABASE_PATH


async def init_db() -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tracked_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                game_title TEXT NOT NULL,
                store TEXT NOT NULL,
                store_url TEXT NOT NULL,
                app_id TEXT,
                cheapshark_id TEXT,
                target_price REAL NOT NULL,
                currency TEXT DEFAULT 'RUB',
                last_price REAL,
                last_checked TEXT,
                alert_sent INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_key TEXT NOT NULL,
                game_title TEXT NOT NULL,
                price REAL NOT NULL,
                currency TEXT DEFAULT 'RUB',
                store TEXT,
                recorded_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                game_title TEXT NOT NULL,
                app_id TEXT NOT NULL,
                last_patch_guid TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(telegram_id, app_id)
            );

            CREATE TABLE IF NOT EXISTS freebie_cache (
                offer_key TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                store TEXT NOT NULL,
                url TEXT,
                notified_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_price_history_game
                ON price_history(game_key);
            CREATE INDEX IF NOT EXISTS idx_tracked_user
                ON tracked_games(telegram_id);
            """
        )
        await db.commit()
    await _migrate_users_language()


async def _migrate_users_language() -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "language" not in columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ru'"
            )
            await db.commit()


async def ensure_user(telegram_id: int, username: str | None = None) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)",
            (telegram_id, username),
        )
        await db.commit()


async def get_user_language(telegram_id: int) -> str:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT language FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        if row and row[0]:
            return str(row[0])
    return "ru"


async def set_user_language(telegram_id: int, language: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (telegram_id, language) VALUES (?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET language = excluded.language
            """,
            (telegram_id, language),
        )
        await db.commit()

async def add_tracked_game(
    telegram_id: int,
    game_title: str,
    store: str,
    store_url: str,
    target_price: float,
    app_id: str | None = None,
    cheapshark_id: str | None = None,
    currency: str = "RUB",
) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO tracked_games (
                telegram_id, game_title, store, store_url, app_id,
                cheapshark_id, target_price, currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                telegram_id,
                game_title,
                store,
                store_url,
                app_id,
                cheapshark_id,
                target_price,
                currency,
            ),
        )
        await db.commit()
        return cursor.lastrowid or 0


async def list_tracked_games(telegram_id: int) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, game_title, store, store_url, app_id, cheapshark_id,
                   target_price, currency, last_price, last_checked, alert_sent
            FROM tracked_games
            WHERE telegram_id = ?
            ORDER BY id DESC
            """,
            (telegram_id,),
        )
        return await cursor.fetchall()


async def remove_tracked_game(telegram_id: int, game_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM tracked_games WHERE id = ? AND telegram_id = ?",
            (game_id, telegram_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def remove_tracked_by_position(telegram_id: int, position: int) -> bool:
    rows = await list_tracked_games(telegram_id)
    if position < 1 or position > len(rows):
        return False
    return await remove_tracked_game(telegram_id, int(rows[position - 1]["id"]))


async def clear_wishlist(telegram_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM tracked_games WHERE telegram_id = ?",
            (telegram_id,),
        )
        await db.commit()
        return cursor.rowcount


async def get_all_tracked_for_monitoring() -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, telegram_id, game_title, store, store_url, app_id,
                   cheapshark_id, target_price, currency, last_price, alert_sent
            FROM tracked_games
            """
        )
        return await cursor.fetchall()


async def update_tracked_ids(
    tracked_id: int,
    *,
    app_id: str | None = None,
    cheapshark_id: str | None = None,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if app_id is not None:
            await db.execute(
                "UPDATE tracked_games SET app_id = ? WHERE id = ?",
                (app_id, tracked_id),
            )
        if cheapshark_id is not None:
            await db.execute(
                "UPDATE tracked_games SET cheapshark_id = ? WHERE id = ?",
                (cheapshark_id, tracked_id),
            )
        await db.commit()


async def update_tracked_price(
    tracked_id: int,
    price: float,
    alert_sent: bool | None = None,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if alert_sent is None:
            await db.execute(
                """
                UPDATE tracked_games
                SET last_price = ?, last_checked = datetime('now')
                WHERE id = ?
                """,
                (price, tracked_id),
            )
        else:
            await db.execute(
                """
                UPDATE tracked_games
                SET last_price = ?, last_checked = datetime('now'),
                    alert_sent = ?
                WHERE id = ?
                """,
                (price, int(alert_sent), tracked_id),
            )
        await db.commit()


async def add_price_record(
    game_key: str,
    game_title: str,
    price: float,
    store: str | None = None,
    currency: str = "RUB",
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO price_history (game_key, game_title, price, currency, store)
            VALUES (?, ?, ?, ?, ?)
            """,
            (game_key, game_title, price, currency, store),
        )
        await db.commit()


async def get_price_history(game_key: str, limit: int = 90) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT price, currency, store, recorded_at, game_title
            FROM price_history
            WHERE game_key = ?
            ORDER BY recorded_at ASC
            LIMIT ?
            """,
            (game_key, limit),
        )
        return await cursor.fetchall()


async def add_favorite(telegram_id: int, game_title: str, app_id: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute(
                """
                INSERT INTO favorites (telegram_id, game_title, app_id)
                VALUES (?, ?, ?)
                """,
                (telegram_id, game_title, app_id),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def list_favorites() -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, telegram_id, game_title, app_id, last_patch_guid FROM favorites"
        )
        return await cursor.fetchall()


async def update_favorite_patch_guid(favorite_id: int, guid: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE favorites SET last_patch_guid = ? WHERE id = ?",
            (guid, favorite_id),
        )
        await db.commit()


async def is_freebie_cache_empty() -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM freebie_cache")
        row = await cursor.fetchone()
        return (row[0] if row else 0) == 0


async def is_freebie_known(offer_key: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM freebie_cache WHERE offer_key = ?",
            (offer_key,),
        )
        return await cursor.fetchone() is not None


async def mark_freebie_notified(
    offer_key: str, title: str, store: str, url: str | None
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO freebie_cache (offer_key, title, store, url)
            VALUES (?, ?, ?, ?)
            """,
            (offer_key, title, store, url),
        )
        await db.commit()


async def get_users_with_tracked() -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT DISTINCT telegram_id FROM tracked_games"
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_all_user_ids() -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT telegram_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
