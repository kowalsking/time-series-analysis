"""Завантаження історії тривог з API alerts.in.ua у канонічну таблицю подій.

Один ``sync`` тягне історію по всіх областях (27 запитів < ліміту 30/10хв),
нормалізує у ту саму схему, що й історичний CSV, і кешує у parquet. Далі
дашборд читає кеш, не звертаючись до API щоразу.

CLI:  python -m src.ingest            # sync за період з config.API_PERIOD
      python -m src.ingest week_ago   # явний період
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from . import config
from .api_client import AlertsClient
from .preprocess import build_events


def normalize_api_alerts(alerts: list[dict[str, Any]]) -> pd.DataFrame:
    """Перетворює список тривог з API у сирий DataFrame [region, start, end].

    Фільтрує за типом тривоги (повітряна) і зводить регіон до рівня області
    (``location_oblast``), щоб бути сумісним з історичним датасетом.
    """
    rows = []
    for a in alerts:
        if a.get("alert_type") != config.API_ALERT_TYPE:
            continue
        region = a.get("location_oblast") or a.get("location_title")
        if not region:
            continue
        rows.append(
            {
                "region": region,
                "start": a.get("started_at"),
                "end": a.get("finished_at"),
            }
        )
    return pd.DataFrame(rows, columns=["region", "start", "end"])


def clip_to_period(events: pd.DataFrame, period: str) -> pd.DataFrame:
    """Лишає лише події в межах вікна періоду.

    Відсікає «вічні» тривоги окупованих територій (почалися у 2022 і не
    завершені), що інакше розтягнули б часовий ряд на роки.
    """
    days = config.API_PERIOD_DAYS.get(period)
    if not days:
        return events
    cutoff = pd.Timestamp.now(tz=config.TIMEZONE) - pd.Timedelta(days=days)
    return events[events[config.COL_START] >= cutoff].reset_index(drop=True)


def sync(
    period: str | None = None,
    uids: dict[int, str] | None = None,
    client: AlertsClient | None = None,
) -> pd.DataFrame:
    """Тягне історію по всіх областях, будує таблицю подій, кешує у parquet."""
    period = period or config.API_PERIOD
    uids = uids or config.OBLAST_UIDS
    client = client or AlertsClient()

    all_alerts: list[dict[str, Any]] = []
    for i, uid in enumerate(uids, 1):
        alerts = client.fetch_region_history(uid, period)
        all_alerts.extend(alerts)
        print(f"[{i}/{len(uids)}] uid={uid} {uids[uid]}: {len(alerts)} тривог")

    raw = normalize_api_alerts(all_alerts)
    events = build_events(raw)
    events = clip_to_period(events, period)

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    events.to_parquet(config.PROCESSED_EVENTS_API, index=False)
    _write_meta(period, events)
    print(
        f"\nЗбережено {len(events)} подій ({events[config.COL_REGION].nunique()} "
        f"областей) → {config.PROCESSED_EVENTS_API}"
    )
    return events


def _write_meta(period: str, events: pd.DataFrame) -> None:
    meta = {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "period": period,
        "n_events": int(len(events)),
        "n_regions": int(events[config.COL_REGION].nunique()),
        "alert_type": config.API_ALERT_TYPE,
    }
    config.API_SYNC_META.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def sync_meta() -> dict[str, Any] | None:
    if config.API_SYNC_META.exists():
        return json.loads(config.API_SYNC_META.read_text(encoding="utf-8"))
    return None


def load_api_events() -> pd.DataFrame:
    """Читає кешовану таблицю подій з API. Кидає помилку, якщо синку не було."""
    if not config.PROCESSED_EVENTS_API.exists():
        raise FileNotFoundError(
            "Немає даних з API. Спершу виконайте синхронізацію: "
            "`python -m src.ingest`."
        )
    return pd.read_parquet(config.PROCESSED_EVENTS_API)


if __name__ == "__main__":
    period_arg = sys.argv[1] if len(sys.argv) > 1 else None
    sync(period_arg)
