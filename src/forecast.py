"""Короткостроковий прогноз погодинної к-сті тривог.

Моделі:
  • seasonal_naive — наївний сезонний baseline («та сама година попереднього дня»);
  • holt_winters — експоненційне згладжування з добовою сезонністю (statsmodels).

Оцінка: MAE / RMSE на відкладеному хвості (останні TEST_DAYS днів).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from . import config, features
from .preprocess import load_events

# statsmodels імпортуємо ліниво (важка залежність), щоб модулі-споживачі
# (напр. аналітика) не тягли її без потреби.


def _future_index(last_ts: pd.Timestamp, steps: int) -> pd.DatetimeIndex:
    return pd.date_range(
        last_ts + pd.Timedelta(hours=1), periods=steps, freq="h", tz=config.TIMEZONE
    )


def train_test_split(
    series: pd.Series, test_days: int = config.TEST_DAYS
) -> tuple[pd.Series, pd.Series]:
    """Відкладає останні ``test_days`` днів у тест."""
    test_hours = test_days * 24
    if len(series) <= test_hours + config.SEASONAL_PERIOD_H:
        raise ValueError(
            f"Замало даних для оцінки: {len(series)} год при тесті {test_hours} год."
        )
    return series.iloc[:-test_hours], series.iloc[-test_hours:]


def seasonal_naive(
    train: pd.Series, steps: int, period: int = config.SEASONAL_PERIOD_H
) -> pd.Series:
    """Прогноз = значення ``period`` годин тому (повторення добового профілю)."""
    history = train.values
    preds = [history[-period + (i % period)] for i in range(steps)]
    idx = _future_index(train.index[-1], steps)
    return pd.Series(np.clip(preds, 0, None), index=idx, name="seasonal_naive")


def holt_winters(
    train: pd.Series, steps: int, period: int = config.SEASONAL_PERIOD_H
) -> pd.Series:
    """Holt-Winters (адитивна добова сезонність) через statsmodels."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ExponentialSmoothing(
            train.values,
            trend=None,
            seasonal="add",
            seasonal_periods=period,
            initialization_method="estimated",
        ).fit()
        preds = model.forecast(steps)

    idx = _future_index(train.index[-1], steps)
    return pd.Series(np.clip(preds, 0, None), index=idx, name="holt_winters")


def _metrics(actual: pd.Series, pred: pd.Series) -> dict[str, float]:
    a, p = actual.values, pred.values[: len(actual)]
    err = a - p
    return {
        "MAE": float(np.mean(np.abs(err))),
        "RMSE": float(np.sqrt(np.mean(err**2))),
    }


def evaluate(series: pd.Series | None = None) -> pd.DataFrame:
    """Порівнює моделі на тесті. Повертає таблицю метрик (рядки — моделі)."""
    if series is None:
        series = features.hourly_alert_starts(load_events())
    train, test = train_test_split(series)
    steps = len(test)

    results = {
        "seasonal_naive": _metrics(test, seasonal_naive(train, steps)),
        "holt_winters": _metrics(test, holt_winters(train, steps)),
    }
    return pd.DataFrame(results).T[["MAE", "RMSE"]]


def forecast_future(
    series: pd.Series,
    horizon: int = config.FORECAST_HORIZON_H,
    model: str = "holt_winters",
) -> pd.Series:
    """Прогноз на ``horizon`` годин уперед, навчений на всьому ряду."""
    fn = {"holt_winters": holt_winters, "seasonal_naive": seasonal_naive}[model]
    return fn(series, horizon)


if __name__ == "__main__":
    print(evaluate())
