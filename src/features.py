"""Побудова часових рядів із таблиці подій.

Усі ряди мають безперервний погодинний індекс (Europe/Kyiv) без пропусків
(відсутні години заповнюються нулями) — це потрібно для коректного прогнозу.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def _hourly_index(events: pd.DataFrame) -> pd.DatetimeIndex:
    """Безперервний погодинний індекс від першої до останньої події."""
    start = events[config.COL_START].min().floor("h")
    end_col = events[config.COL_END].dropna()
    last = end_col.max() if not end_col.empty else events[config.COL_START].max()
    end = last.ceil("h")
    return pd.date_range(start, end, freq="h", tz=config.TIMEZONE)


def hourly_alert_starts(events: pd.DataFrame) -> pd.Series:
    """К-сть початків тривог за кожну годину (цільовий ряд для прогнозу)."""
    idx = _hourly_index(events)
    starts = events[config.COL_START].dt.floor("h")
    counts = starts.value_counts().reindex(idx, fill_value=0).sort_index()
    counts.name = "alert_starts"
    counts.index.name = "hour"
    return counts


def hourly_active_regions(events: pd.DataFrame) -> pd.Series:
    """К-сть регіонів під тривогою в кожну годину (рівень навантаження).

    Подія активна в годину h, якщо вона почалася до кінця h і завершилась
    після початку h. Події без часу завершення вважаємо тривалістю 1 година.
    """
    idx = _hourly_index(events)
    active = pd.Series(0, index=idx, dtype=int)

    ends = events[config.COL_END].fillna(
        events[config.COL_START] + pd.Timedelta(hours=1)
    )
    starts = events[config.COL_START].dt.floor("h")
    ends = ends.dt.floor("h")

    for s, e in zip(starts, ends):
        active.loc[s:e] += 1

    active.name = "active_regions"
    active.index.name = "hour"
    return active


def per_region_starts(events: pd.DataFrame) -> pd.DataFrame:
    """Матриця погодинних початків тривог: рядки — години, колонки — регіони."""
    idx = _hourly_index(events)
    tmp = events.copy()
    tmp["hour"] = tmp[config.COL_START].dt.floor("h")
    pivot = (
        tmp.pivot_table(
            index="hour",
            columns=config.COL_REGION,
            values=config.COL_START,
            aggfunc="count",
            fill_value=0,
        )
        .reindex(idx, fill_value=0)
        .sort_index()
    )
    pivot.index.name = "hour"
    return pivot


def durations(events: pd.DataFrame) -> pd.Series:
    """Тривалості тривог (хв), лише валідні (не NaN)."""
    return events[config.COL_DURATION].dropna()


def add_calendar(series: pd.Series) -> pd.DataFrame:
    """Додає календарні ознаки (година доби, день тижня, дата) до ряду."""
    df = series.to_frame()
    df["hour_of_day"] = df.index.hour
    df["day_of_week"] = df.index.dayofweek  # 0 = понеділок
    df["date"] = df.index.date
    return df
