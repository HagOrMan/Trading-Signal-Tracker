"""Load config.toml once into a typed namespace accessible from anywhere."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"


@dataclass(frozen=True)
class UserProfile:
    age_range: str
    horizon_years: int
    risk_tolerance: str
    location: str


@dataclass(frozen=True)
class Thresholds:
    drawdown_pct: float
    vol_lookback_years: int
    vol_window_days: int
    ma_short_window: int
    ma_long_window: int
    crossover_lookback_days: int
    new_high_low_lookback_days: int
    correlation_window_days: int
    correlation_drop_threshold: float


@dataclass(frozen=True)
class Benchmarks:
    default: str
    canadian: str


@dataclass(frozen=True)
class HonestyLayer:
    forward_horizons_months: list[int]
    tier_low: int
    tier_moderate: int
    tier_good: int


@dataclass(frozen=True)
class Config:
    user_profile: UserProfile
    thresholds: Thresholds
    benchmarks: Benchmarks
    honesty_layer: HonestyLayer
    raw: dict[str, Any] = field(repr=False)


def load_config(path: Path | None = None) -> Config:
    """Read and parse config.toml. Raises FileNotFoundError if missing."""
    path = path or CONFIG_PATH
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    return Config(
        user_profile=UserProfile(**raw["user_profile"]),
        thresholds=Thresholds(**raw["thresholds"]),
        benchmarks=Benchmarks(**raw["benchmarks"]),
        honesty_layer=HonestyLayer(**raw["honesty_layer"]),
        raw=raw,
    )
