"""Центральна конфігурація проєкту: шляхи, часовий пояс, маппінг колонок, регіони.

Якщо реальна схема CSV відрізняється від очікуваної — достатньо оновити
``COLUMN_ALIASES`` тут, і весь конвеєр підхопить зміни.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Шляхи ---------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# Очікуваний сирий файл (можна покласти будь-який *.csv у data/raw/ —
# data_loader візьме перший, якщо точного імені немає).
RAW_CSV_NAME = "alerts.csv"
PROCESSED_EVENTS = PROCESSED_DIR / "events.parquet"

# Дані, отримані з живого API (окремий кеш, щоб не змішувати з історичними).
PROCESSED_EVENTS_API = PROCESSED_DIR / "events_api.parquet"
API_SYNC_META = PROCESSED_DIR / "api_sync_meta.json"

# --- Часовий пояс --------------------------------------------------------
TIMEZONE = "Europe/Kyiv"

# --- Канонічна схема таблиці подій --------------------------------------
# Усі модулі працюють із цими назвами колонок.
COL_REGION = "region"
COL_START = "start_dt"
COL_END = "end_dt"
COL_DURATION = "duration_min"

# Можливі назви колонок у сирих CSV → канонічна назва.
# Інспекція реальної схеми (крок 2 плану) дозволяє розширити цей словник.
COLUMN_ALIASES: dict[str, str] = {
    # регіон
    "region": COL_REGION,
    "oblast": COL_REGION,
    "область": COL_REGION,
    "region_title": COL_REGION,
    "location": COL_REGION,
    "name": COL_REGION,
    # початок
    "start": COL_START,
    "started_at": COL_START,
    "start_time": COL_START,
    "date_start": COL_START,
    "began_at": COL_START,
    "start_dt": COL_START,
    # кінець
    "end": COL_END,
    "finished_at": COL_END,
    "end_time": COL_END,
    "date_end": COL_END,
    "ended_at": COL_END,
    "end_dt": COL_END,
}

# --- Параметри аналізу/прогнозу -----------------------------------------
# Скільки останніх днів відкладаємо в тест при оцінці прогнозу.
TEST_DAYS = 7
# Горизонт прогнозу (годин) для відображення на дашборді.
FORECAST_HORIZON_H = 48
# Добова сезонність для Holt-Winters / сезонного baseline.
SEASONAL_PERIOD_H = 24

# Фільтр розумних меж тривалості тривоги (хв): відсікаємо сміття.
MIN_DURATION_MIN = 0
MAX_DURATION_MIN = 24 * 60  # тривога довша за добу вважається аномалією даних

# Нормалізація назв регіонів: прибираємо суфікси/префікси, що заважають
# зведенню до 1 області.
REGION_STRIP_TOKENS = ["область", "обл.", "oblast", "регіон", "м.", "місто"]

# --- alerts.in.ua API ----------------------------------------------------
ALERTS_API_BASE = "https://api.alerts.in.ua/v1"
ALERTS_TOKEN_ENV = "ALERTS_TOKEN"  # назва змінної у .env
ENV_FILE = PROJECT_ROOT / ".env"

# Період історії: "week_ago" або "month_ago".
API_PERIOD = "month_ago"
# Скільки днів реально лишати після sync (відсікаємо «вічні» тривоги
# окупованих територій, що почалися у 2022 і не завершені).
API_PERIOD_DAYS = {"week_ago": 8, "month_ago": 32}
# Тип тривоги, що нас цікавить (повітряна).
API_ALERT_TYPE = "air_raid"

# Ліміт API: не більше 30 запитів / 10 хв. Тримаємо запас.
API_RATE_LIMIT = 30
API_RATE_WINDOW_S = 600
API_MIN_INTERVAL_S = 1.0          # мінімальна пауза між запитами
API_MAX_RETRY_WAIT_S = 90         # макс. очікування на 429 перш ніж здатися

# Дисковий кеш сирих JSON-відповідей (щоб не палити ліміт).
API_CACHE_DIR = PROCESSED_DIR / "api_cache"
API_CACHE_TTL_S = 30 * 60         # відповідь свіжа 30 хв

# UID областей у alerts.in.ua (location_type == oblast).
# Верифіковано проти живого API (13, 16, 29, 31) — решта зі сталого довідника.
OBLAST_UIDS: dict[int, str] = {
    3: "Хмельницька область",
    4: "Вінницька область",
    5: "Рівненська область",
    8: "Волинська область",
    9: "Дніпропетровська область",
    10: "Житомирська область",
    11: "Закарпатська область",
    12: "Запорізька область",
    13: "Івано-Франківська область",
    14: "Київська область",
    15: "Кіровоградська область",
    16: "Луганська область",
    17: "Львівська область",
    18: "Миколаївська область",
    19: "Одеська область",
    20: "Полтавська область",
    21: "Сумська область",
    22: "Тернопільська область",
    23: "Харківська область",
    24: "Херсонська область",
    25: "Черкаська область",
    26: "Чернігівська область",
    27: "Чернівецька область",
    28: "Донецька область",
    29: "Автономна Республіка Крим",
    30: "м. Севастополь",
    31: "м. Київ",
}


def get_alerts_token() -> str:
    """Читає ALERTS_TOKEN з .env (або з оточення). Кидає помилку, якщо немає."""
    from dotenv import load_dotenv

    load_dotenv(ENV_FILE)
    token = os.getenv(ALERTS_TOKEN_ENV)
    if not token:
        raise RuntimeError(
            f"Не знайдено {ALERTS_TOKEN_ENV}. Додайте рядок "
            f"`{ALERTS_TOKEN_ENV}=ваш_токен` у файл {ENV_FILE}."
        )
    return token.strip()
