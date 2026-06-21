"""Тести нормалізації відповідей alerts.in.ua API (без мережі).

Зразки — реальні записи, отримані з живого API (структура підтверджена).
"""

from __future__ import annotations

from src import config
from src.ingest import normalize_api_alerts
from src.preprocess import build_events

# Реальні записи з /v1/regions/31/alerts/month_ago.json (м. Київ) + 1 артилерійський.
SAMPLE = [
    {
        "alert_type": "air_raid",
        "location_oblast": "м. Київ",
        "location_title": "м. Київ",
        "location_type": "oblast",
        "started_at": "2026-06-21T07:32:52.000Z",
        "finished_at": "2026-06-21T08:11:50.000Z",
    },
    {
        "alert_type": "air_raid",
        "location_oblast": "Харківська область",
        "location_title": "Харківський район",
        "location_type": "raion",
        "started_at": "2026-06-14T18:56:53.576Z",
        "finished_at": "2026-06-14T19:10:22.000Z",
    },
    {
        # не повітряна — має бути відфільтрована
        "alert_type": "artillery_shelling",
        "location_oblast": "Сумська область",
        "location_title": "Сумський район",
        "location_type": "raion",
        "started_at": "2026-06-10T10:00:00.000Z",
        "finished_at": "2026-06-10T11:00:00.000Z",
    },
]


def test_normalize_filters_non_air_raid():
    df = normalize_api_alerts(SAMPLE)
    assert len(df) == 2  # артилерійську відкинуто
    assert list(df.columns) == ["region", "start", "end"]


def test_normalize_rolls_up_to_oblast():
    df = normalize_api_alerts(SAMPLE)
    # район зводиться до області (location_oblast)
    assert "Харківська область" in df["region"].values
    assert "Харківський район" not in df["region"].values


def test_api_events_pipeline_tz_and_duration():
    events = build_events(normalize_api_alerts(SAMPLE))
    assert str(events[config.COL_START].dt.tz) == config.TIMEZONE
    # 07:32:52 → 08:11:50 ≈ 38.97 хв
    kyiv = events[events[config.COL_REGION] == "Київ"]
    assert len(kyiv) == 1
    assert 38 < kyiv.iloc[0][config.COL_DURATION] < 40


def test_empty_input():
    df = normalize_api_alerts([])
    assert df.empty
    assert list(df.columns) == ["region", "start", "end"]
