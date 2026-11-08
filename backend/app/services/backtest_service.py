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

    def backtest_fixed_weights(self, prices: pd.DataFrame,
                               weights: dict[str, float],
                               window_days: int | None = None) -> dict:
        """Backtest a constant-mix portfolio of fixed target weights.

        Monthly rebalanced to the target weights (drift-induced turnover only),
        same 10 bps cost model and benchmarks as run(). No optimizer is involved,
        so what-if questions answer in milliseconds. Deterministic.
        """
        if not weights:
            raise BacktestError("weights must not be empty")
        unknown = [t for t in weights if t not in prices.columns]
        if unknown:
            raise BacktestError(f"unknown tickers: {unknown}")
        if any(w < -1e-9 for w in weights.values()):
            raise BacktestError("weights must be non-negative")
        total = sum(weights.values())
        if abs(total - 1.0) > 1e-6:
            raise BacktestError(f"weights must sum to 1 (got {total:.4f})")

        target = {t: float(w) for t, w in weights.items()}
        returns = prices.pct_change().dropna(how="any")

        month_ends = prices.groupby(prices.index.to_period("M")).tail(1).index
        nav = [1.0]
        nav_dates = [month_ends[0]]
        drifted = dict(target)  # weights after last month's drift

        for start in month_ends[:-1]:
            next_locs = [prices.index.get_loc(d) for d in month_ends if d > start]
            hold_end = prices.index[next_locs[0]] if next_locs else prices.index[-1]
            step_rets = returns.loc[start: hold_end].iloc[1:]
            period_rets = (
                (1.0 + step_rets).prod(axis=0) - 1.0 if not step_rets.empty
                else pd.Series(0.0, index=returns.columns)
            )
            # rebalance to target: cost on the turnover needed at this month start
            turnover = sum(abs(target.get(t, 0.0) - drifted.get(t, 0.0))
                           for t in prices.columns)
            cost = turnover * REBALANCE_COST_BPS / 10_000
            w = np.array([target.get(t, 0.0) for t in prices.columns])
            port_ret = float(np.dot(w, period_rets.values)) - cost
            nav.append(nav[-1] * (1 + port_ret))
            nav_dates.append(hold_end)
            # drift the weights through the month's asset returns (normalized to 1)
            gross = (1.0 + period_rets)
            pgross = float(np.dot(w, gross.values))
            if pgross > 0:
                for t in prices.columns:
                    drifted[t] = target.get(t, 0.0) * float(gross.get(t, 1.0)) / pgross

        strategy_curve = pd.Series(nav, index=pd.to_datetime(nav_dates), name="fixed_weights")
        base_date = pd.to_datetime(nav_dates[0])
        bench = {}
        for ticker in ("2800.HK", "SPY"):
            if ticker not in prices.columns:
                continue
            series = prices.loc[prices.index >= base_date, ticker]
            bench[ticker] = (series / series.iloc[0]).reindex(strategy_curve.index).ffill()

        metrics = [_metrics(strategy_curve)]
        names = ["fixed_weights"]
        for ticker, curve in bench.items():
            metrics.append(_metrics(curve))
            names.append(f"benchmark_{ticker}")

        return {
            "weights": target,
            "dates": [d.strftime("%Y-%m-%d") for d in strategy_curve.index],
            "nav": [float(v) for v in strategy_curve.values],
            "metrics": [{"name": n, **m} for n, m in zip(names, metrics)],
        }
