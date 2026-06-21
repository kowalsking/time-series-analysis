"""Генератор синтетичних даних про тривоги — DEV-ФОЛБЕК.

Потрібен, щоб запускати конвеєр і дашборд без ручного завантаження Kaggle-датасету.
Відтворює реалістичні патерни (добовий цикл, різна активність регіонів, масовані
сплески), але це НЕ реальні дані. Для справжнього аналізу покладіть CSV з Kaggle
у data/raw/ (див. README).

Запуск:  python -m src.synth
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

# Період, що збігається з реальним датасетом dimakyn (24.02.2022–09.04.2022).
START_DATE = "2022-02-24"
END_DATE = "2022-04-09"

# Умовна «інтенсивність» тривог по регіонах (прифронтові/прикордонні — вищі).
REGION_INTENSITY: dict[str, float] = {
    "Харківська": 3.0,
    "Донецька": 2.8,
    "Луганська": 2.5,
    "Запорізька": 2.2,
    "Миколаївська": 2.0,
    "Сумська": 1.9,
    "Чернігівська": 1.8,
    "Київська": 1.7,
    "Дніпропетровська": 1.6,
    "Одеська": 1.4,
    "Херсонська": 1.4,
    "Полтавська": 1.0,
    "Житомирська": 0.9,
    "Вінницька": 0.8,
    "Черкаська": 0.8,
    "Кіровоградська": 0.7,
    "Хмельницька": 0.7,
    "Рівненська": 0.6,
    "Волинська": 0.6,
    "Львівська": 0.6,
    "Тернопільська": 0.5,
    "Івано-Франківська": 0.5,
    "Чернівецька": 0.4,
    "Закарпатська": 0.3,
}

# Відносна ймовірність початку тривоги за годиною доби (нічні/ранкові — вищі).
HOUR_WEIGHTS = np.array(
    [
        1.1, 1.0, 1.0, 1.2, 1.5, 1.8, 1.6, 1.3,  # 00-07
        1.0, 0.8, 0.7, 0.7, 0.7, 0.8, 0.9, 1.0,  # 08-15
        1.1, 1.2, 1.3, 1.4, 1.4, 1.3, 1.2, 1.1,  # 16-23
    ]
)


def generate(seed: int = 42) -> pd.DataFrame:
    """Генерує таблицю подій тривог із колонками region/start/end."""
    rng = np.random.default_rng(seed)
    hour_p = HOUR_WEIGHTS / HOUR_WEIGHTS.sum()

    days = pd.date_range(START_DATE, END_DATE, freq="D")
    rows: list[dict] = []

    for region, intensity in REGION_INTENSITY.items():
        for day in days:
            # Кількість тривог за день ~ Пуассон, масштабована інтенсивністю регіону.
            n_alerts = rng.poisson(lam=1.2 * intensity)
            # Зрідка — масований день (сплеск активності всюди).
            if rng.random() < 0.05:
                n_alerts += rng.poisson(lam=3)

            for _ in range(n_alerts):
                hour = rng.choice(24, p=hour_p)
                minute = rng.integers(0, 60)
                start = day + pd.Timedelta(hours=int(hour), minutes=int(minute))
                # Тривалість: лог-нормальна, медіана ~40 хв, хвіст до кількох годин.
                duration = float(np.clip(rng.lognormal(mean=3.7, sigma=0.6), 5, 600))
                end = start + pd.Timedelta(minutes=duration)
                rows.append(
                    {
                        "region": region,
                        "start": start.strftime("%Y-%m-%d %H:%M:%S"),
                        "end": end.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

    df = pd.DataFrame(rows).sort_values("start").reset_index(drop=True)
    return df


def main() -> None:
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = config.RAW_DIR / config.RAW_CSV_NAME
    df = generate()
    df.to_csv(out, index=False)
    print(f"Згенеровано {len(df)} синтетичних подій → {out}")
    print("⚠️  Це СИНТЕТИЧНІ дані для розробки, не реальні тривоги.")


if __name__ == "__main__":
    main()
