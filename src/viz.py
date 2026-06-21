"""Білдери інтерактивних графіків (Plotly). Перевикористовуються дашбордом."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

ACCENT = "#d6336c"
GRID = "#e9ecef"


def _layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(
        title=title,
        template="plotly_white",
        margin=dict(l=40, r=20, t=50, b=40),
        hovermode="x unified",
    )
    return fig


def line_series(series: pd.Series, title: str, y_label: str) -> go.Figure:
    fig = px.line(series, labels={"value": y_label, "index": ""})
    fig.update_traces(line_color=ACCENT)
    fig.update_layout(showlegend=False)
    return _layout(fig, title)


def bar_distribution(series: pd.Series, title: str, x_label: str) -> go.Figure:
    fig = px.bar(series, labels={"value": "Тривог", "index": x_label})
    fig.update_traces(marker_color=ACCENT)
    fig.update_layout(showlegend=False)
    return _layout(fig, title)


def top_regions_bar(df: pd.DataFrame, title: str) -> go.Figure:
    data = df.sort_values("alerts")
    fig = px.bar(
        data,
        x="alerts",
        y=data.index,
        orientation="h",
        labels={"alerts": "Кількість тривог", "y": ""},
    )
    fig.update_traces(marker_color=ACCENT)
    return _layout(fig, title)


def heatmap(matrix: pd.DataFrame, title: str, x_label: str, y_label: str) -> go.Figure:
    fig = px.imshow(
        matrix,
        aspect="auto",
        color_continuous_scale="Reds",
        labels={"x": x_label, "y": y_label, "color": "Тривог"},
    )
    # Примусово показуємо ВСІ підписи осей (px.imshow інакше проріджує їх при
    # великій к-сті категорій — тоді частина регіонів лишається без підпису).
    fig.update_xaxes(tickmode="linear", dtick=1)
    fig.update_yaxes(tickmode="array", tickvals=list(range(len(matrix.index))),
                     ticktext=list(matrix.index))
    # Висота під кількість рядків, щоб підписи не злипались.
    fig.update_layout(height=max(400, 22 * len(matrix.index) + 120))
    return _layout(fig, title)


def correlation_heatmap(corr: pd.DataFrame, title: str) -> go.Figure:
    fig = px.imshow(
        corr,
        aspect="auto",
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
        labels={"color": "Кореляція"},
    )
    return _layout(fig, title)


def forecast_plot(
    history: pd.Series,
    forecast: pd.Series,
    title: str,
    actual: pd.Series | None = None,
) -> go.Figure:
    """Графік: історія + прогноз (+ опційно фактичні значення тесту)."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=history.index, y=history.values, name="Факт (історія)",
            line=dict(color="#495057"),
        )
    )
    if actual is not None:
        fig.add_trace(
            go.Scatter(
                x=actual.index, y=actual.values, name="Факт (тест)",
                line=dict(color="#1c7ed6"),
            )
        )
    fig.add_trace(
        go.Scatter(
            x=forecast.index, y=forecast.values, name="Прогноз",
            line=dict(color=ACCENT, dash="dash"),
        )
    )
    return _layout(fig, title)
