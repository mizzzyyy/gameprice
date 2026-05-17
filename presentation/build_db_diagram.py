"""Схема БД → presentation/db_schema.png"""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).parent / "db_schema.png"

TABLES = {
    "users": [
        "telegram_id INTEGER PK",
        "username TEXT",
        "language TEXT  (ru/en)",
        "created_at TEXT",
    ],
    "tracked_games": [
        "id INTEGER PK",
        "telegram_id INTEGER FK → users",
        "game_title TEXT",
        "store, store_url TEXT",
        "app_id, cheapshark_id TEXT",
        "target_price REAL",
        "currency TEXT",
        "last_price REAL",
        "last_checked, alert_sent",
        "created_at TEXT",
    ],
    "price_history": [
        "id INTEGER PK",
        "game_key TEXT  (index)",
        "game_title TEXT",
        "price REAL, currency TEXT",
        "store TEXT",
        "recorded_at TEXT",
    ],
    "favorites": [
        "id INTEGER PK",
        "telegram_id INTEGER",
        "game_title TEXT",
        "app_id TEXT",
        "last_patch_guid TEXT",
        "UNIQUE(telegram_id, app_id)",
    ],
    "freebie_cache": [
        "offer_key TEXT PK",
        "title, store TEXT",
        "url TEXT",
        "notified_at TEXT",
    ],
}

RELATIONS = [
    ("users", "tracked_games", "1 : N"),
    ("users", "favorites", "1 : N"),
]


def draw_table(ax, x, y, w, h, name: str, cols: list[str], color: str) -> None:
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        facecolor=color,
        edgecolor="#58a6ff",
        linewidth=2,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2,
        y + h - 0.35,
        name,
        ha="center",
        va="top",
        fontsize=13,
        fontweight="bold",
        color="#e6edf3",
    )
    body = "\n".join(f"  {c}" for c in cols)
    ax.text(
        x + 0.15,
        y + h - 0.7,
        body,
        ha="left",
        va="top",
        fontsize=9,
        color="#c9d1d9",
        family="monospace",
    )


def main() -> None:
    fig, ax = plt.subplots(figsize=(14, 9), facecolor="#0d1117")
    ax.set_facecolor("#0d1117")
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 9)
    ax.axis("off")

    ax.text(
        7,
        8.5,
        "GamePrice Watcher — SQLite (gameprice.db)",
        ha="center",
        fontsize=18,
        fontweight="bold",
        color="#58a6ff",
    )
    ax.text(
        7,
        8.05,
        "Файл в корне проекта · aiosqlite",
        ha="center",
        fontsize=11,
        color="#8b949e",
    )

    positions = {
        "users": (0.4, 5.2, 4.0, 2.5, "#161b22"),
        "tracked_games": (5.0, 5.0, 4.3, 3.0, "#1a2332"),
        "price_history": (9.6, 5.2, 4.0, 2.6, "#161b22"),
        "favorites": (0.4, 1.2, 4.0, 2.4, "#1a2332"),
        "freebie_cache": (5.0, 1.0, 4.3, 2.2, "#161b22"),
    }

    for name, (x, y, w, h, col) in positions.items():
        draw_table(ax, x, y, w, h, name, TABLES[name], col)

    for t1, t2, label in RELATIONS:
        p1 = positions[t1]
        p2 = positions[t2]
        x1, y1, w1, h1 = p1[0], p1[1], p1[2], p1[3]
        x2, y2, w2, h2 = p2[0], p2[1], p2[2], p2[3]
        ax.annotate(
            "",
            xy=(x2, y2 + h2 / 2),
            xytext=(x1 + w1, y1 + h1 / 2),
            arrowprops=dict(arrowstyle="->", color="#3fb950", lw=2),
        )
        mx = (x1 + w1 + x2) / 2
        my = (y1 + h1 / 2 + y2 + h2 / 2) / 2
        ax.text(mx, my + 0.15, label, fontsize=9, color="#3fb950", ha="center")

    ax.text(
        7,
        0.35,
        "Индексы: idx_price_history_game(game_key) · idx_tracked_user(telegram_id)",
        ha="center",
        fontsize=10,
        color="#8b949e",
    )

    plt.tight_layout()
    plt.savefig(OUT, dpi=150, facecolor="#0d1117", bbox_inches="tight")
    plt.close()
    print(OUT)


if __name__ == "__main__":
    main()
