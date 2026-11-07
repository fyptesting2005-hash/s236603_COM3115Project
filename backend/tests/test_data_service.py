"""DataService tests: cleaning, cache round-trip, offline snapshot fallback."""
import numpy as np
import pandas as pd
import pytest

from app.services.data_service import DataService


def test_clean_aligns_and_ffills_short_gaps():
    idx = pd.bdate_range("2024-01-01", periods=10)
    # interior gap in A: forward-filled within tolerance
    prices = pd.DataFrame(
        {"A": [100, np.nan, 102, 103, 104, 105, 106, 107, 108, 109],
         "B": [200, 201, 202, 203, 204, 205, 206, 207, 208, 209]},
        index=idx,
    )
    cleaned = DataService.clean(prices, max_ffill_days=5)
    assert cleaned.notna().all().all()
    assert cleaned["A"].iloc[1] == 100.0
    assert len(cleaned) == 10

    # leading missing rows (calendar alignment) are dropped entirely
    prices2 = pd.DataFrame(
        {"A": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
         "B": [np.nan] * 4 + [204, 205, 206, 207, 208, 209]},
        index=idx,
    )
    cleaned2 = DataService.clean(prices2, max_ffill_days=5)
    assert len(cleaned2) == 6
    assert cleaned2["B"].iloc[0] == 204.0


def test_log_returns_matches_manual_computation(synthetic_prices):
    rets = DataService.log_returns(synthetic_prices)
    expected = np.log(synthetic_prices.iloc[1] / synthetic_prices.iloc[0])
    assert np.isclose(rets.iloc[0]["SPY"], expected["SPY"])
    assert rets.shape[0] == len(synthetic_prices) - 1


def test_cache_round_trip(data_service, synthetic_prices):
    cached = data_service._read_cache(list(synthetic_prices.columns), "2021-01-01")
    cached.index.name = None  # SQLite round-trip names the pivot axes
    cached.columns.name = None
    assert not cached.empty
    assert set(cached.columns) == set(synthetic_prices.columns)
    pd.testing.assert_frame_equal(
        cached[synthetic_prices.columns].round(10),
        synthetic_prices.round(10),
        check_freq=False,
    )


def test_get_history_uses_cache_when_fresh(data_service, synthetic_prices):
    out = data_service.get_history(list(synthetic_prices.columns), "2021-01-01")
    assert out.shape[0] > 1000
    assert out.notna().all().all()


def test_snapshot_fallback_when_cache_empty(tmp_path, synthetic_prices):
    snap_path = tmp_path / "snapshot.csv"
    synthetic_prices.to_csv(snap_path)
    svc = DataService(db_path=tmp_path / "empty.db", snapshot_csv=snap_path,
                      allow_network=False)
    out = svc.get_history(list(synthetic_prices.columns)[:3], "2021-01-01")
    assert not out.empty


def test_raises_when_no_source_available(tmp_path):
    svc = DataService(db_path=tmp_path / "empty.db",
                      snapshot_csv=tmp_path / "missing.csv", allow_network=False)
    with pytest.raises(Exception):
        svc.get_history(["SPY"], "2021-01-01")
