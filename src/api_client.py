"""Клієнт alerts.in.ua API.

Особливості:
  • токен читається з .env (ALERTS_TOKEN);
  • контроль ліміту (30 запитів / 10 хв) — пауза між запитами + обробка 429;
  • дисковий кеш сирих JSON-відповідей (TTL), щоб не палити ліміт на повторах.

Документація API підтверджена живими запитами: ендпоінти повертають
{"alerts": [...], "meta": {...}, "disclaimer": "..."}.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from . import config


class RateLimitError(RuntimeError):
    """Перевищено ліміт API і очікування довше за API_MAX_RETRY_WAIT_S."""


class AlertsClient:
    def __init__(self, token: str | None = None, use_cache: bool = True):
        self.token = token or config.get_alerts_token()
        self.use_cache = use_cache
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self._last_call_ts = 0.0
        config.API_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # --- кеш --------------------------------------------------------------
    def _cache_path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace(".json", "")
        return config.API_CACHE_DIR / f"{safe}.json"

    def _read_cache(self, key: str) -> dict[str, Any] | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > config.API_CACHE_TTL_S:
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_cache(self, key: str, data: dict[str, Any]) -> None:
        self._cache_path(key).write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    # --- низькорівневий запит --------------------------------------------
    def _throttle(self) -> None:
        elapsed = time.time() - self._last_call_ts
        if elapsed < config.API_MIN_INTERVAL_S:
            time.sleep(config.API_MIN_INTERVAL_S - elapsed)

    def _get(self, endpoint: str) -> dict[str, Any]:
        """GET з кешем, throttle та обробкою 429."""
        if self.use_cache:
            cached = self._read_cache(endpoint)
            if cached is not None:
                return cached

        url = f"{config.ALERTS_API_BASE}/{endpoint}"
        self._throttle()
        resp = self.session.get(url, timeout=20)
        self._last_call_ts = time.time()

        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", "60"))
            if wait > config.API_MAX_RETRY_WAIT_S:
                raise RateLimitError(
                    f"Перевищено ліміт API. Повторіть через ~{wait} с "
                    f"(ліміт: {config.API_RATE_LIMIT} запитів / "
                    f"{config.API_RATE_WINDOW_S // 60} хв)."
                )
            time.sleep(wait + 1)
            resp = self.session.get(url, timeout=20)

        resp.raise_for_status()
        data = resp.json()
        if self.use_cache:
            self._write_cache(endpoint, data)
        return data

    # --- публічні методи --------------------------------------------------
    def fetch_active(self) -> list[dict[str, Any]]:
        """Усі активні тривоги (поточний знімок)."""
        return self._get("alerts/active.json").get("alerts", [])

    def fetch_region_history(
        self, uid: int, period: str | None = None
    ) -> list[dict[str, Any]]:
        """Історія тривог для області ``uid`` за період (week_ago/month_ago)."""
        period = period or config.API_PERIOD
        return self._get(f"regions/{uid}/alerts/{period}.json").get("alerts", [])
