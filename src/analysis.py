"""Аналітика патернів тривог: KPI, розподіли за часом, регіони, кореляції."""

from __future__ import annotations

import pandas as pd

from . import config, features

UA_WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]


def kpis(events: pd.DataFrame) -> dict[str, float]:
    """Зведені показники для KPI-карток дашборда."""
    dur = features.durations(events)
    span = events[config.COL_START].max() - events[config.COL_START].min()
    return {
        "total_alerts": int(len(events)),
        "regions": int(events[config.COL_REGION].nunique()),
        "total_alert_hours": float(dur.sum() / 60.0),
        "avg_duration_min": float(dur.mean()) if not dur.empty else 0.0,
        "median_duration_min": float(dur.median()) if not dur.empty else 0.0,
        "days_covered": int(span.days) + 1,
    }


def by_hour_of_day(events: pd.DataFrame) -> pd.Series:
    """Розподіл к-сті тривог за годиною доби (0–23)."""
    s = events[config.COL_START].dt.hour.value_counts().reindex(range(24), fill_value=0)
    s.index.name = "hour_of_day"
    s.name = "alerts"
    return s.sort_index()


def by_day_of_week(events: pd.DataFrame) -> pd.Series:
    """Розподіл к-сті тривог за днем тижня (Пн–Нд)."""
    s = (
        events[config.COL_START]
        .dt.dayofweek.value_counts()
        .reindex(range(7), fill_value=0)
        .sort_index()
    )
    s.index = UA_WEEKDAYS
    s.index.name = "day_of_week"
    s.name = "alerts"
    return s


def daily_trend(events: pd.DataFrame) -> pd.Series:
    """К-сть тривог по днях (тренд за весь період)."""
    s = events.set_index(config.COL_START).resample("D").size()
    s.name = "alerts"
    s.index.name = "date"
    return s


def top_regions(events: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    """Топ регіонів за к-стю тривог та сумарними годинами під тривогою."""
    g = events.groupby(config.COL_REGION)
    out = pd.DataFrame(
        {
            "alerts": g.size(),
            "total_hours": g[config.COL_DURATION].sum() / 60.0,
            "avg_duration_min": g[config.COL_DURATION].mean(),
        }
    )
    return out.sort_values("alerts", ascending=False).head(n)


def region_hour_heatmap(events: pd.DataFrame) -> pd.DataFrame:
    """Матриця регіон × година доби (к-сть тривог) для теплової карти."""
    tmp = events.copy()
    tmp["hour_of_day"] = tmp[config.COL_START].dt.hour
    pivot = tmp.pivot_table(
        index=config.COL_REGION,
        columns="hour_of_day",
        values=config.COL_START,
        aggfunc="count",
        fill_value=0,
    ).reindex(columns=range(24), fill_value=0)
    # Сортуємо регіони за загальною активністю (найактивніші зверху).
    return pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]


def region_correlation(events: pd.DataFrame, top_n: int = 12) -> pd.DataFrame:
    """Кореляція погодинної активності між регіонами.

    Висока кореляція = тривоги в регіонах часто збігаються в часі (індикатор
    масованих, синхронних атак).
    """
    pivot = features.per_region_starts(events)
    # Беремо найактивніші регіони, щоб матриця була читабельною.
    top = pivot.sum().sort_values(ascending=False).head(top_n).index
    return pivot[top].corr()
