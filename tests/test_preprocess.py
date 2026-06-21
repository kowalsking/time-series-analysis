"""Тести препроцесингу: парсинг дат, нормалізація регіонів, відсів сміття."""

from __future__ import annotations

import pandas as pd
import pytest

from src import config
from src.preprocess import build_events, normalize_region


def test_normalize_region_strips_suffixes():
    assert normalize_region("Харківська область") == "Харківська"
    assert normalize_region("  Київська обл. ") == "Київська"
    assert normalize_region("Львівська") == "Львівська"


def _raw(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_build_events_canonical_schema():
    raw = _raw(
        [
            {"region": "Харківська область", "start": "2022-03-01 10:00:00",
             "end": "2022-03-01 10:45:00"},
        ]
    )
    ev = build_events(raw)
    assert list(ev.columns) == [
        config.COL_REGION, config.COL_START, config.COL_END, config.COL_DURATION,
    ]
    assert ev.loc[0, config.COL_REGION] == "Харківська"
    assert ev.loc[0, config.COL_DURATION] == pytest.approx(45.0)


def test_timezone_is_kyiv():
    raw = _raw([{"region": "Київська", "start": "2022-03-01 10:00:00",
                 "end": "2022-03-01 11:00:00"}])
    ev = build_events(raw)
    assert str(ev[config.COL_START].dt.tz) == config.TIMEZONE


def test_drops_negative_and_excessive_durations():
    raw = _raw(
        [
            # негативна тривалість (кінець раніше початку)
            {"region": "А", "start": "2022-03-01 10:00:00", "end": "2022-03-01 09:00:00"},
            # надмірна (> доба)
            {"region": "Б", "start": "2022-03-01 10:00:00", "end": "2022-03-05 10:00:00"},
            # валідна
            {"region": "В", "start": "2022-03-01 10:00:00", "end": "2022-03-01 10:30:00"},
        ]
    )
    ev = build_events(raw)
    assert len(ev) == 1
    assert ev.loc[0, config.COL_REGION] == "В"


def test_missing_required_column_raises():
    raw = _raw([{"foo": "bar"}])
    with pytest.raises(ValueError, match="бракує"):
        build_events(raw)


def test_missing_end_column_yields_nan_duration():
    raw = _raw([{"region": "Київська", "start": "2022-03-01 10:00:00"}])
    ev = build_events(raw)
    assert ev[config.COL_DURATION].isna().all()
    assert len(ev) == 1
