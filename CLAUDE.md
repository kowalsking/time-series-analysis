# CLAUDE.md — контекст проєкту

Навчальний MVP: аналіз часових рядів повітряних тривог в Україні зі Streamlit-дашбордом
(патерни + короткостроковий прогноз). Працює як на історичних даних, так і на live-API.

## Запуск

```bash
source .venv/bin/activate          # Python 3.14, venv у .venv/
python -m src.synth                # згенерувати синтетичні дані (dev-фолбек)
python -m src.ingest               # sync реальних даних з alerts.in.ua API
streamlit run app/dashboard.py     # дашборд
pytest                             # тести (10 шт.)
```

## Потік даних

```
Джерело → канонічна таблиця подій → часові ряди → аналітика/прогноз → дашборд
```

Канонічна таблиця подій (єдиний контракт між усіма модулями):
`[region, start_dt, end_dt, duration_min]`, де `start_dt`/`end_dt` — tz-aware (Europe/Kyiv).

Два джерела зводяться до однієї схеми, тому вся аналітика працює однаково:
1. **Історичні**: CSV у `data/raw/` (Kaggle `dimakyn/air-alarm-ukraine`, ~24.02–09.04.2022)
   або синтетика з `src/synth.py`. Завантаження: `data_loader` → `preprocess.build_events`.
2. **Live API**: `src/ingest.py` тягне історію по 27 областях → `build_events` →
   `data/processed/events_api.parquet`.

## Модулі (`src/`)

| Файл | Призначення |
|---|---|
| `config.py` | Шляхи, tz, `COLUMN_ALIASES` (маппінг колонок CSV), параметри API, `OBLAST_UIDS` (27 областей), `get_alerts_token()` |
| `data_loader.py` | Читання CSV + `canonicalize_columns()` (толерантний до назв) |
| `preprocess.py` | `build_events()` → канонічна таблиця; нормалізація регіонів, tz, відсів сміття |
| `features.py` | Погодинні ряди: `hourly_alert_starts` (цільовий для прогнозу), `hourly_active_regions`, `per_region_starts` |
| `analysis.py` | KPI, розподіли (година/день), `region_hour_heatmap`, `top_regions`, `region_correlation` |
| `forecast.py` | `seasonal_naive` (baseline) + `holt_winters` (statsmodels), метрики MAE/RMSE, `evaluate()` |
| `viz.py` | Plotly-білдери графіків (перевикористовуються дашбордом) |
| `synth.py` | Генератор синтетичних даних (dev-фолбек, НЕ реальні дані) |
| `api_client.py` | Клієнт alerts.in.ua: rate-limit, дисковий кеш, обробка 429 |
| `ingest.py` | `sync()` історії з API, `normalize_api_alerts()`, `clip_to_period()`, `load_api_events()` |

`app/dashboard.py` — Streamlit; додає корінь у `sys.path`. Перемикач джерела (live API за
замовчуванням), спільна функція `render_filters()` (регіони + пресети періоду), 3 вкладки:
Огляд / Патерни / Прогноз.

## Ключові рішення та підводні камені

- **alerts.in.ua API ліміт: 30 запитів / 10 хв.** Один sync = ~27 запитів (вкладається).
  Відповіді кешуються на диск (`data/processed/api_cache/`, TTL 30 хв). Токен — у `.env`
  під `ALERTS_TOKEN` (gitignored). На 429 клієнт чекає `Retry-After` (макс. `API_MAX_RETRY_WAIT_S`).
- **API віддає лише ~місяць історії** (`month_ago`); глибшої історії заднім числом немає.
  Тому пресет «усіх даних» для API названо «Усі дані (до місяця)».
- **«Вічні» тривоги окупованих територій** (Луганськ/Крим, почались 2022, не завершені)
  розтягували ряд на роки → `clip_to_period()` обрізає до `API_PERIOD_DAYS` (32 дні).
- **API-дані зводяться до рівня області** (`location_oblast`), фільтр `alert_type == air_raid`.
- **Часовий пояс**: усе в Europe/Kyiv; API віддає UTC (`...Z`) → конвертується у `preprocess`.
- **Прогноз**: цільовий ряд — погодинна к-сть початків тривог; добова сезонність (24h);
  тест — останні `TEST_DAYS` (7) днів. Holt-Winters порівнюється з наївним baseline.
- **plotly imshow проріджує підписи осей** при багатьох категоріях → у `viz.heatmap`
  підписи регіонів задаються явно (`tickmode="array"`), висота масштабується під рядки.
- **Якщо реальна схема CSV відрізняється** — оновити `COLUMN_ALIASES` у `config.py`
  (інспекція: `python -m src.data_loader`).

## Залежності

pandas, numpy, statsmodels, plotly, streamlit, requests, python-dotenv, pyarrow, pytest.
Стан на момент написання: усе встановлено в `.venv` (Python 3.14), 10/10 тестів проходять.
