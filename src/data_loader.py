"""Завантаження сирих даних про тривоги з CSV.

Толерантний до точної назви файлу та назв колонок: спирається на
``config.COLUMN_ALIASES`` для приведення до канонічної схеми.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config


def find_raw_csv() -> Path:
    """Повертає шлях до сирого CSV.

    Спочатку шукає файл із точним іменем ``config.RAW_CSV_NAME``, інакше —
    перший ``*.csv`` у ``data/raw/``.
    """
    exact = config.RAW_DIR / config.RAW_CSV_NAME
    if exact.exists():
        return exact
    candidates = sorted(config.RAW_DIR.glob("*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"Не знайдено жодного CSV у {config.RAW_DIR}. "
            "Завантажте датасет (див. README) або згенеруйте синтетичні дані: "
            "`python -m src.synth`."
        )
    return candidates[0]


def canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Приводить назви колонок до канонічних через config.COLUMN_ALIASES.

    Невідомі колонки зберігаються без змін (можуть знадобитися при інспекції).
    """
    rename_map = {
        col: config.COLUMN_ALIASES[col.strip().lower()]
        for col in df.columns
        if col.strip().lower() in config.COLUMN_ALIASES
    }
    return df.rename(columns=rename_map)


def load_raw(path: Path | None = None) -> pd.DataFrame:
    """Читає сирий CSV і приводить назви колонок до канонічних."""
    path = path or find_raw_csv()
    return canonicalize_columns(pd.read_csv(path))


def inspect(path: Path | None = None) -> None:
    """Друкує схему сирого файлу — для кроку «інспекція реальних колонок»."""
    path = path or find_raw_csv()
    df = pd.read_csv(path, nrows=200)
    print(f"Файл: {path}")
    print(f"Колонки: {list(df.columns)}")
    print(f"Типи:\n{df.dtypes}")
    print(f"Перші рядки:\n{df.head(5).to_string()}")


if __name__ == "__main__":
    inspect()
