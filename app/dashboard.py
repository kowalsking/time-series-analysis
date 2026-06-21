"""Streamlit-дашборд: аналіз часових рядів повітряних тривог.

Запуск з кореня проєкту:  streamlit run app/dashboard.py
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

# Додаємо корінь проєкту в sys.path, щоб працював `from src import ...`.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from src import analysis, config, features, viz
from src.forecast import evaluate, forecast_future, train_test_split, holt_winters
from src.preprocess import load_events
from src import ingest

st.set_page_config(page_title="Повітряні тривоги — аналіз ЧР", layout="wide")

SOURCE_HISTORICAL = "Історичні (CSV / синтетика)"
SOURCE_API = "Live API (alerts.in.ua)"

# Пресети періоду (спільні для обох джерел даних).
# Назва «усіх даних» залежить від джерела: API віддає лише ~місяць історії.
PERIOD_ALL_API = "Усі дані (до місяця)"
PERIOD_ALL_HIST = "Усі дані"
PERIOD_WEEK = "Останній тиждень"
PERIOD_MONTH = "Останній місяць"
PERIOD_CUSTOM = "Власний діапазон"


@st.cache_data
def get_events(source: str) -> pd.DataFrame:
    if source == SOURCE_API:
        return ingest.load_api_events()
    return load_events()


@st.cache_data
def get_forecast_eval(_series_key: str, series: pd.Series) -> pd.DataFrame:
    return evaluate(series)


def filter_events(events: pd.DataFrame, regions: list[str], date_range) -> pd.DataFrame:
    df = events
    if regions:
        df = df[df[config.COL_REGION].isin(regions)]
    if date_range and len(date_range) == 2:
        start, end = date_range
        d = df[config.COL_START].dt.date
        df = df[(d >= start) & (d <= end)]
    return df


def render_filters(events: pd.DataFrame, source: str):
    """Малює спільні фільтри сайдбару (регіони + період з пресетами).

    Пресети рахуються відносно останньої дати в даних (а не «сьогодні»), бо
    дані можуть не доходити до поточного дня. Назва «усіх даних» залежить від
    джерела (API має лише ~місяць історії). Повертає (regions, date_range,
    min_d, max_d). Використовується однаково для обох джерел даних.
    """
    st.sidebar.header("Фільтри")
    all_regions = sorted(events[config.COL_REGION].unique())
    sel_regions = st.sidebar.multiselect("Регіони", all_regions, default=[])

    min_d = events[config.COL_START].dt.date.min()
    max_d = events[config.COL_START].dt.date.max()

    all_label = PERIOD_ALL_API if source == SOURCE_API else PERIOD_ALL_HIST
    presets = [all_label, PERIOD_WEEK, PERIOD_MONTH, PERIOD_CUSTOM]

    period = st.sidebar.selectbox("Період", presets, index=0)
    if period == PERIOD_WEEK:
        date_range = (max(min_d, max_d - timedelta(days=7)), max_d)
    elif period == PERIOD_MONTH:
        date_range = (max(min_d, max_d - timedelta(days=30)), max_d)
    elif period == PERIOD_CUSTOM:
        date_range = st.sidebar.date_input(
            "Діапазон", value=(min_d, max_d), min_value=min_d, max_value=max_d
        )
    else:  # усі дані
        date_range = (min_d, max_d)

    if period != PERIOD_CUSTOM and len(date_range) == 2:
        st.sidebar.caption(f"📅 {date_range[0]} – {date_range[1]}")

    return sel_regions, date_range, min_d, max_d


# --- Сайдбар: джерело даних -----------------------------------------------
st.sidebar.header("Джерело даних")
source = st.sidebar.radio("Дані", [SOURCE_API, SOURCE_HISTORICAL], label_visibility="collapsed")

if source == SOURCE_API:
    meta = ingest.sync_meta()
    if meta:
        st.sidebar.caption(
            f"Останній sync: {meta['synced_at'][:16].replace('T', ' ')} · "
            f"період: {meta['period']} · подій: {meta['n_events']}"
        )
    if st.sidebar.button("🔄 Синхронізувати з API"):
        with st.spinner("Завантаження з alerts.in.ua…"):
            try:
                ingest.sync()
                get_events.clear()
                st.sidebar.success("Готово")
            except Exception as e:  # noqa: BLE001 — показуємо будь-яку помилку API
                st.sidebar.error(f"Помилка синхронізації: {e}")

# --- Завантаження даних ---------------------------------------------------
try:
    events = get_events(source)
except FileNotFoundError as e:
    st.error(str(e))
    if source == SOURCE_API:
        st.info("Натисніть «🔄 Синхронізувати з API» у бічній панелі або виконайте `python -m src.ingest`.")
    else:
        st.info(
            "Згенеруйте синтетичні дані командою `python -m src.synth` "
            "або покладіть CSV з Kaggle у `data/raw/` (див. README)."
        )
    st.stop()

# --- Сайдбар: фільтри (спільні для обох джерел) ---------------------------
sel_regions, sel_dates, min_d, max_d = render_filters(events, source)

if source == SOURCE_API:
    st.sidebar.caption("✅ Реальні дані alerts.in.ua (повітряні тривоги).")
else:
    st.sidebar.caption(
        "⚠️ Якщо завантажено синтетичні дані — це згенеровані значення для "
        "демонстрації, не реальні тривоги."
    )

fe = filter_events(events, sel_regions, sel_dates)
if fe.empty:
    st.warning("За обраними фільтрами немає даних.")
    st.stop()

# --- Заголовок ------------------------------------------------------------
st.title("🚨 Аналіз часових рядів повітряних тривог")
KAGGLE_URL = "https://www.kaggle.com/datasets/dimakyn/air-alarm-ukrain-2022022420220409"
if source == SOURCE_API:
    src_label = "alerts.in.ua API"
else:
    src_label = f"[Kaggle dimakyn/air-alarm-ukraine]({KAGGLE_URL}) / синтетичні дані"
st.caption(f"Період даних: {min_d} – {max_d} · джерело: {src_label}")

tab_overview, tab_patterns, tab_forecast = st.tabs(
    ["📊 Огляд", "🔁 Патерни", "📈 Прогноз"]
)

# === Вкладка: Огляд =======================================================
with tab_overview:
    k = analysis.kpis(fe)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Всього тривог", f"{k['total_alerts']:,}".replace(",", " "))
    c2.metric("Регіонів", k["regions"])
    c3.metric("Сумарно годин тривог", f"{k['total_alert_hours']:.0f}")
    c4.metric("Медіанна тривалість, хв", f"{k['median_duration_min']:.0f}")

    active = features.hourly_active_regions(fe)
    st.plotly_chart(
        viz.line_series(active, "Регіонів під тривогою (погодинно)", "Регіонів"),
        use_container_width=True,
    )
    st.plotly_chart(
        viz.line_series(analysis.daily_trend(fe), "Тривог за день", "Тривог"),
        use_container_width=True,
    )

# === Вкладка: Патерни =====================================================
with tab_patterns:
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            viz.bar_distribution(
                analysis.by_hour_of_day(fe), "Розподіл за годиною доби", "Година"
            ),
            use_container_width=True,
        )
    with col2:
        st.plotly_chart(
            viz.bar_distribution(
                analysis.by_day_of_week(fe), "Розподіл за днем тижня", "День"
            ),
            use_container_width=True,
        )

    st.plotly_chart(
        viz.heatmap(
            analysis.region_hour_heatmap(fe),
            "Теплова карта: регіон × година доби",
            "Година доби",
            "Регіон",
        ),
        use_container_width=True,
    )

    col3, col4 = st.columns(2)
    with col3:
        st.plotly_chart(
            viz.top_regions_bar(analysis.top_regions(fe), "Топ регіонів за к-стю тривог"),
            use_container_width=True,
        )
    with col4:
        if fe[config.COL_REGION].nunique() >= 2:
            st.plotly_chart(
                viz.correlation_heatmap(
                    analysis.region_correlation(fe),
                    "Кореляція активності між регіонами",
                ),
                use_container_width=True,
            )
        else:
            st.info("Кореляція доступна, коли обрано ≥2 регіони.")

# === Вкладка: Прогноз =====================================================
with tab_forecast:
    st.markdown(
        "Цільовий ряд — **погодинна к-сть початків тривог**. Прогноз будується на "
        "добовій сезонності (24 год). Через короткий період даних фокус — на "
        "**короткостроковому** горизонті."
    )
    series = features.hourly_alert_starts(fe)

    try:
        metrics = evaluate(series)
        st.subheader("Якість моделей на тесті (останні дні)")
        st.dataframe(metrics.style.format("{:.3f}"), use_container_width=False)

        best = metrics["MAE"].idxmin()
        st.caption(f"Найкраща за MAE: **{best}**")

        # Прогноз на тестовому хвості для наочного порівняння.
        train, test = train_test_split(series)
        fc_test = holt_winters(train, len(test))
        st.plotly_chart(
            viz.forecast_plot(
                train.iloc[-7 * 24:],
                fc_test,
                "Прогноз vs факт на відкладеному тесті (Holt-Winters)",
                actual=test,
            ),
            use_container_width=True,
        )

        # Прогноз у майбутнє.
        horizon = st.slider("Горизонт прогнозу, год", 12, 72, config.FORECAST_HORIZON_H, 12)
        future = forecast_future(series, horizon=horizon, model="holt_winters")
        st.plotly_chart(
            viz.forecast_plot(
                series.iloc[-7 * 24:], future, f"Прогноз на {horizon} год уперед"
            ),
            use_container_width=True,
        )
    except ValueError as e:
        st.warning(f"Недостатньо даних для прогнозу за обраними фільтрами: {e}")
