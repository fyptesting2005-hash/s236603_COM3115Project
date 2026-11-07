"""BacktestService: monthly-rebalanced vectorized backtest with cost model.

Strategies re-estimate mu/cov on a trailing window at each month-end, build the
target portfolio, and hold it for the next month. Turnover is charged at
REBALANCE_COST_BPS. Benchmarks are buy-and-hold 2800.HK and SPY.

All randomness is fixed; results are deterministic from the price history.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import REBALANCE_COST_BPS, TRADING_DAYS
from .ml_service import MLService
from .optimizer_service import OptimizerService


class BacktestError(RuntimeError):
    pass


def _metrics(curve: pd.Series, periods_per_year: int = 12) -> dict[str, float]:
    """CAGR, annualized vol, Sharpe (rf=0), max drawdown from a NAV curve.

    The backtest NAV is sampled at month-ends, so returns are monthly and are
    annualized with periods_per_year=12 (benchmarks are reindexed to the same
    monthly grid before calling this function).
    """
    rets = curve.pct_change().dropna()
    years = max((len(curve) - 1) / periods_per_year, 1e-9)
    cagr = float((curve.iloc[-1] / curve.iloc[0]) ** (1 / years) - 1)
    vol = float(rets.std() * np.sqrt(periods_per_year))
    sharpe = float(rets.mean() / rets.std() * np.sqrt(periods_per_year)) if rets.std() > 0 else 0.0
    running_max = curve.cummax()
    mdd = float((curve / running_max - 1).min())
    return {"cagr": cagr, "volatility": vol, "sharpe": sharpe, "max_drawdown": mdd}


class BacktestService:
    def __init__(self, optimizer: OptimizerService | None = None,
                 ml: MLService | None = None, seed: int = 42) -> None:
        self.optimizer = optimizer or OptimizerService()
        self.ml = ml or MLService(seed=seed)
        self.seed = seed
        self._cache: dict[tuple, dict] = {}

    def run(self, prices: pd.DataFrame, strategy: str = "max_sharpe",
            use_ml: bool = True, window_days: int = TRADING_DAYS) -> dict:
        """Run the backtest; returns {dates, strategy_nav, benchmark_navs, metrics}.

        Results are cached per (strategy, use_ml, last price date) so repeated
        dashboard views (e.g. during a live demo) are served instantly; the cache
        invalidates automatically when the price panel moves forward.
        """
        cache_key = (strategy, bool(use_ml), str(prices.index.max().date()))
        if cache_key in self._cache:
            return self._cache[cache_key]
        if strategy not in ("max_sharpe", "max_sharpe_ml", "min_vol"):
            raise BacktestError(f"unknown strategy: {strategy}")
        returns = prices.pct_change().dropna(how="any")

        month_ends = prices.groupby(prices.index.to_period("M")).tail(1).index
        month_ends = [d for d in month_ends if prices.index.get_loc(d) > window_days]
        if len(month_ends) < 13:
            raise BacktestError("not enough history for backtest")

        nav = [1.0]
        nav_dates = [month_ends[0]]
        prev_weights = {t: 0.0 for t in prices.columns}

        for rebal_date in month_ends[:-1]:
            loc = prices.index.get_loc(rebal_date)
            window = prices.iloc[loc - window_days: loc + 1]
            mu, cov = self.optimizer.estimates(window)
            if use_ml and strategy == "max_sharpe_ml":
                views = self.ml.current_views(window)
                mu = self.ml.blend_mu(mu, views)
            # Rebalance; fall back to min-vol, then previous, then equal weights.
            # Max-Sharpe is infeasible when every trailing-window expected return
            # is non-positive (e.g. the 2022 bear market), so degrade gracefully
            # the way a production robo-advisor would.
            try:
                if strategy == "min_vol":
                    weights = self.optimizer.min_volatility(mu, cov)
                else:
                    weights = self.optimizer.max_sharpe(mu, cov)
            except Exception:  # noqa: BLE001
                try:
                    weights = self.optimizer.min_volatility(mu, cov)
                except Exception:  # noqa: BLE001
                    if any(w > 0 for w in prev_weights.values()):
                        weights = dict(prev_weights)
                    else:
                        weights = {t: 1.0 / len(prices.columns) for t in prices.columns}

            # hold until the next month-end
            next_locs = [prices.index.get_loc(d) for d in month_ends if d > rebal_date]
            hold_end = prices.index[min(next_locs[0], len(prices) - 1)] if next_locs else prices.index[-1]
            # bought at rebal_date close: earn returns strictly after that day
            step_rets = returns.loc[rebal_date: hold_end].iloc[1:]
            period_rets = (
                (1.0 + step_rets).prod(axis=0) - 1.0 if not step_rets.empty
                else pd.Series(0.0, index=returns.columns)
            )

            turnover = sum(abs(weights.get(t, 0.0) - prev_weights.get(t, 0.0))
                           for t in prices.columns)
            cost = turnover * REBALANCE_COST_BPS / 10_000

            w = np.array([weights.get(t, 0.0) for t in prices.columns])
            port_ret = float(np.dot(w, period_rets.values)) - cost
            nav.append(nav[-1] * (1 + port_ret))
            nav_dates.append(hold_end)
            prev_weights = weights

        strategy_curve = pd.Series(nav, index=pd.to_datetime(nav_dates), name="strategy")

        # benchmarks: buy-and-hold from the first rebalance date, resampled to the
        # same month-end grid as the strategy so all curves share one axis
        bench = {}
        base_date = pd.to_datetime(nav_dates[0])
        for ticker in ("2800.HK", "SPY"):
            if ticker not in prices.columns:
                continue
            series = prices.loc[prices.index >= base_date, ticker]
            series = series / series.iloc[0]
            bench[ticker] = series.reindex(strategy_curve.index).ffill()

        all_metrics = [_metrics(strategy_curve)]
        names = [strategy]
        for ticker, curve in bench.items():
            all_metrics.append(_metrics(curve))
            names.append(f"benchmark_{ticker}")

        result = {
            "dates": [d.strftime("%Y-%m-%d") for d in strategy_curve.index],
            "strategy_nav": [float(v) for v in strategy_curve.values],
            "benchmarks": {
                t: {"dates": [d.strftime("%Y-%m-%d") for d in c.index],
                    "values": [float(v) for v in c.values]}
                for t, c in bench.items()
            },
            "metrics": [
                {"name": n, **m} for n, m in zip(names, all_metrics)
            ],
        }
        self._cache[cache_key] = result
        return result
