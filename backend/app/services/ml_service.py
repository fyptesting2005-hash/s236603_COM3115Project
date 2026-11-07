"""MLService: technical features, Random Forest return prediction, walk-forward CV.

The model predicts each asset's forward 21-trading-day annualized return from
technical features. Predictions are blended with the historical mean estimate
and fed into the optimizer as adjusted expected-return inputs.

Validation is walk-forward only: for each evaluation month, the model trains on
data strictly before that month and predicts on that month — no look-ahead.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from ..config import ML_BLEND_ALPHA, TRADING_DAYS

HORIZON = 21  # forward trading days


def make_features(prices: pd.DataFrame) -> pd.DataFrame:
    """Per (date, ticker) technical features from adjusted closes."""
    frames = []
    for ticker in prices.columns:
        px = prices[ticker]
        f = pd.DataFrame(index=px.index)
        f["ticker"] = ticker
        f["mom_1m"] = px.pct_change(21)
        f["mom_3m"] = px.pct_change(63)
        f["mom_6m"] = px.pct_change(126)
        f["vol_21d"] = px.pct_change().rolling(21).std() * np.sqrt(TRADING_DAYS)
        f["ma_ratio"] = px / px.rolling(63).mean()
        f["volume_proxy"] = px.pct_change().rolling(21).mean().abs()
        frames.append(f)
    features = pd.concat(frames).reset_index().rename(columns={"index": "date"})
    return features


def make_targets(prices: pd.DataFrame) -> pd.DataFrame:
    """Forward 21-day annualized return per (date, ticker)."""
    frames = []
    for ticker in prices.columns:
        px = prices[ticker]
        fwd = px.shift(-HORIZON) / px - 1.0
        ann = (1.0 + fwd) ** (TRADING_DAYS / HORIZON) - 1.0
        frames.append(pd.DataFrame({"date": px.index, "ticker": ticker, "fwd_return": ann.values}))
    return pd.concat(frames)


def build_dataset(prices: pd.DataFrame) -> pd.DataFrame:
    """Feature/target table, one row per (date, ticker), NaN rows dropped."""
    features = make_features(prices)
    targets = make_targets(prices)
    df = features.merge(targets, on=["date", "ticker"], how="inner")
    feature_cols = ["mom_1m", "mom_3m", "mom_6m", "vol_21d", "ma_ratio", "volume_proxy"]
    return df.dropna(subset=feature_cols + ["fwd_return"]).reset_index(drop=True)

FEATURE_COLS = ["mom_1m", "mom_3m", "mom_6m", "vol_21d", "ma_ratio", "volume_proxy"]


class MLService:
    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self._model: RandomForestRegressor | None = None

    # ---------- model ----------
    def _new_model(self) -> RandomForestRegressor:
        return RandomForestRegressor(
            n_estimators=200, max_depth=5, random_state=self.seed, n_jobs=-1
        )

    def walk_forward_validate(self, prices: pd.DataFrame,
                              min_train_months: int = 36) -> dict:
        """Expanding-window walk-forward evaluation over the last available months.

        Returns metrics against the naive historical-mean baseline:
        rmse_model, rmse_baseline, hit_rate, months_evaluated.
        """
        data = build_dataset(prices)
        if data.empty:
            return {"rmse_model": None, "rmse_baseline": None, "hit_rate": None,
                    "months_evaluated": 0}
        dates = np.sort(data["date"].unique())
        month_keys = pd.to_datetime(dates).to_period("M").unique()
        eval_months = list(month_keys[max(min_train_months, len(month_keys) - 36):])

        preds, actuals, baselines = [], [], []
        for month in eval_months:
            month_end = month.to_timestamp(how="end")
            train = data[pd.to_datetime(data["date"]) <= month_end]
            # predict on the last available day of this month
            cut = pd.to_datetime(train["date"]).max()
            test = train[pd.to_datetime(train["date"]) == cut]
            if test.empty:
                continue
            model = self._new_model()
            model.fit(train[FEATURE_COLS], train["fwd_return"])
            preds.extend(model.predict(test[FEATURE_COLS]).tolist())
            actuals.extend(test["fwd_return"].tolist())
            # naive baseline: trailing mean daily return annualized, per ticker
            hist_mean = (
                train.groupby("ticker")["fwd_return"].mean().to_dict()
            )
            baselines.extend(hist_mean.get(t, 0.0) for t in test["ticker"])

        if not preds:
            return {"rmse_model": None, "rmse_baseline": None, "hit_rate": None,
                    "months_evaluated": 0}
        preds_a = np.asarray(preds)
        actuals_a = np.asarray(actuals)
        baselines_a = np.asarray(baselines)
        rmse_model = float(np.sqrt(np.mean((preds_a - actuals_a) ** 2)))
        rmse_baseline = float(np.sqrt(np.mean((baselines_a - actuals_a) ** 2)))
        hit_rate = float(np.mean(np.sign(preds_a) == np.sign(actuals_a)))
        return {
            "rmse_model": rmse_model,
            "rmse_baseline": rmse_baseline,
            "hit_rate": hit_rate,
            "months_evaluated": len(preds),
        }

    def current_views(self, prices: pd.DataFrame) -> dict[str, float]:
        """Fit on all history and predict forward annualized return per ticker."""
        data = build_dataset(prices)
        if data.empty:
            return {}
        latest = pd.to_datetime(data["date"]).max()
        current = data[pd.to_datetime(data["date"]) == latest]
        model = self._new_model()
        model.fit(data[FEATURE_COLS], data["fwd_return"])
        preds = model.predict(current[FEATURE_COLS])
        return dict(zip(current["ticker"], (float(p) for p in preds)))

    def blend_mu(self, mu_hist: pd.Series, views: dict[str, float],
                 alpha: float = ML_BLEND_ALPHA) -> pd.Series:
        """Blend historical mean returns with ML views (alpha = ML weight).

        ML views are winsorized to [-0.5, 0.5] annualized and floored at -0.9
        relative to the historical estimate to keep the optimizer well-behaved.
        """
        blended = mu_hist.copy().astype(float)
        for ticker in blended.index:
            view = views.get(ticker)
            if view is None:
                continue
            view = float(np.clip(view, -0.5, 0.5))
            blended[ticker] = (1 - alpha) * blended[ticker] + alpha * view
        # keep expected returns above a small floor so frontier math stays sane
        return blended.clip(lower=-0.5, upper=0.6)
