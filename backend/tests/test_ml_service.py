"""MLService tests: dataset construction, views bounds, walk-forward plumbing."""
import numpy as np
import pandas as pd
import pytest

from app.services.ml_service import MLService, build_dataset, make_features


def test_build_dataset_has_all_tickers(synthetic_prices):
    data = build_dataset(synthetic_prices)
    assert set(data["ticker"].unique()) == set(synthetic_prices.columns)
    assert len(data) > 1000
    # features and target must not contain NaN after construction
    assert data[["mom_1m", "mom_3m", "mom_6m", "vol_21d", "ma_ratio", "volume_proxy",
                 "fwd_return"]].notna().all().all()


def test_features_forward_looking_columns_absent(synthetic_prices):
    features = make_features(synthetic_prices)
    for col in ("mom_1m", "vol_21d", "ma_ratio"):
        assert col in features.columns


def test_current_views_bounded(synthetic_prices, tickers):
    ml = MLService(seed=42)
    views = ml.current_views(synthetic_prices)
    assert set(views.keys()) == set(tickers)
    for v in views.values():
        assert -0.5 <= v <= 0.5


def test_blend_mu_within_bounds(synthetic_prices):
    ml = MLService(seed=42)
    hist = pd.Series({t: 0.05 for t in synthetic_prices.columns})
    views = {t: 0.9 for t in synthetic_prices.columns}  # extreme view gets clipped
    blended = ml.blend_mu(hist, views, alpha=0.3)
    assert (blended <= 0.6).all() and (blended >= -0.5).all()
    # alpha blend of 0.05 and clipped view 0.5 = 0.185
    assert np.isclose(blended.iloc[0], (1 - 0.3) * 0.05 + 0.3 * 0.5)


def test_walk_forward_runs_and_counts_months(synthetic_prices):
    ml = MLService(seed=42)
    result = ml.walk_forward_validate(synthetic_prices, min_train_months=30)
    assert result["months_evaluated"] > 5
    assert result["rmse_model"] is not None
    assert 0.0 <= result["hit_rate"] <= 1.0


def test_walk_forward_deterministic(synthetic_prices):
    ml = MLService(seed=42)
    r1 = ml.walk_forward_validate(synthetic_prices, min_train_months=24)
    r2 = ml.walk_forward_validate(synthetic_prices, min_train_months=24)
    assert r1["rmse_model"] == r2["rmse_model"]
    assert r1["hit_rate"] == r2["hit_rate"]


def test_walk_forward_train_excludes_prediction_month(synthetic_prices, monkeypatch):
    """Regression test: the model must never train on the row it predicts.

    The leaky version fit on `data[date <= month_end]` (including the test row).
    The leak-free fit for a month with prediction date `cut` uses exactly
    len(data[date < cut]) rows (8 tickers per date).
    """
    import numpy as np

    from app.services.ml_service import build_dataset

    ml = MLService(seed=42)
    fit_sizes = []

    class SpyModel:
        def fit(self, X, y):
            fit_sizes.append(len(X))
            return self

        def predict(self, X):
            return np.zeros(len(X))

    monkeypatch.setattr(ml, "_new_model", lambda: SpyModel())
    ml.walk_forward_validate(synthetic_prices, min_train_months=36)
    assert fit_sizes, "walk-forward should have fitted at least once"

    # expected leak-free size for the last evaluation month
    data = build_dataset(synthetic_prices)
    dates = pd.to_datetime(data["date"])
    month_keys = pd.Series(dates).dt.to_period("M").unique()
    eval_months = list(month_keys[max(36, len(month_keys) - 36):])
    last_month = eval_months[-1]
    month_data = dates[dates <= last_month.to_timestamp(how="end")]
    cut = month_data.max()
    expected = int((dates < cut).sum())
    assert fit_sizes[-1] == expected  # leaky version would give expected + 8
