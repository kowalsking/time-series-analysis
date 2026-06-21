"""Очищення сирих даних → канонічна таблиця подій тривог.

Результат: DataFrame з колонками [region, start_dt, end_dt, duration_min],
де start_dt/end_dt — timezone-aware (Europe/Kyiv).
"""

from __future__ import annotations

import pandas as pd

from . import config
from .data_loader import canonicalize_columns, load_raw


def normalize_region(name: str) -> str:
    """Зводить назву регіону до короткої форми (без «область», «обл.» тощо)."""
    if not isinstance(name, str):
        return name
    out = name.strip()
    for token in config.REGION_STRIP_TOKENS:
        out = out.replace(token, "").replace(token.capitalize(), "")
    return out.strip(" .,-")


def _to_kyiv(series: pd.Series) -> pd.Series:
    """Парсить дати і робить їх timezone-aware у Europe/Kyiv.

    Якщо вхідні дані без tz — локалізуємо як київський час; якщо з tz —
    конвертуємо у київський.
    """
    dt = pd.to_datetime(series, errors="coerce")
    if dt.dt.tz is None:
        return dt.dt.tz_localize(config.TIMEZONE, ambiguous="NaT", nonexistent="NaT")
    return dt.dt.tz_convert(config.TIMEZONE)


def build_events(raw: pd.DataFrame | None = None) -> pd.DataFrame:
    """Будує канонічну таблицю подій з сирого DataFrame (або з диска)."""
    df = canonicalize_columns(raw) if raw is not None else load_raw()

    missing = {config.COL_REGION, config.COL_START} - set(df.columns)
    if missing:
        raise ValueError(
            f"У даних бракує обов'язкових колонок: {missing}. "
            f"Наявні: {list(df.columns)}. Оновіть COLUMN_ALIASES у config.py."
        )

    out = pd.DataFrame()
    out[config.COL_REGION] = df[config.COL_REGION].map(normalize_region)
    out[config.COL_START] = _to_kyiv(df[config.COL_START])

    if config.COL_END in df.columns:
        out[config.COL_END] = _to_kyiv(df[config.COL_END])
    else:
        # Якщо кінця немає — тривалості невідомі (tz-aware NaT, щоб віднімання
        # з tz-aware start не падало).
        out[config.COL_END] = pd.Series(
            pd.NaT, index=out.index, dtype=f"datetime64[ns, {config.TIMEZONE}]"
        )

    out[config.COL_DURATION] = (
        out[config.COL_END] - out[config.COL_START]
    ).dt.total_seconds() / 60.0

    out = _clean(out)
    out = out.sort_values(config.COL_START).reset_index(drop=True)
    return out


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Відсіює некоректні рядки: без часу початку/регіону, з негативною/
    надмірною тривалістю."""
    df = df.dropna(subset=[config.COL_START, config.COL_REGION])
    df = df[df[config.COL_REGION].astype(str).str.len() > 0]

    dur = df[config.COL_DURATION]
    valid_dur = dur.isna() | (
        (dur >= config.MIN_DURATION_MIN) & (dur <= config.MAX_DURATION_MIN)
    )
    df = df[valid_dur]
    return df


def build_and_save() -> pd.DataFrame:
    """Будує таблицю подій і кешує її у data/processed/."""
    events = build_events()
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    events.to_parquet(config.PROCESSED_EVENTS, index=False)
    return events


def load_events(rebuild: bool = False) -> pd.DataFrame:
    """Повертає кешовану таблицю подій або будує її за потреби."""
    if not rebuild and config.PROCESSED_EVENTS.exists():
        return pd.read_parquet(config.PROCESSED_EVENTS)
    return build_and_save()


if __name__ == "__main__":
    ev = build_and_save()
    print(ev.head())
    print(f"\nВсього подій: {len(ev)}, регіонів: {ev[config.COL_REGION].nunique()}")
