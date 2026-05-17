"""Test config loading."""
from __future__ import annotations

from src.config import load_config


def test_load_config_returns_populated_dataclass() -> None:
    cfg = load_config()
    assert cfg.user_profile.horizon_years > 0
    assert cfg.thresholds.ma_short_window == 50
    assert cfg.thresholds.ma_long_window == 200
    assert cfg.benchmarks.default == "SPY"
    assert sorted(cfg.honesty_layer.forward_horizons_months) == [1, 3, 6, 12]


def test_load_config_raw_contains_all_sections() -> None:
    cfg = load_config()
    for section in ("user_profile", "thresholds", "benchmarks", "honesty_layer"):
        assert section in cfg.raw


def test_honesty_layer_tier_thresholds_sane() -> None:
    cfg = load_config()
    assert cfg.honesty_layer.tier_low < cfg.honesty_layer.tier_moderate
    assert cfg.honesty_layer.tier_moderate < cfg.honesty_layer.tier_good
