"""OptimizerService: Markowitz mean-variance optimization via PyPortfolioOpt."""
from __future__ import annotations

import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier, expected_returns, risk_models

from ..config import FRONTIER_POINTS, TRADING_DAYS


class OptimizationError(RuntimeError):
    """Raised when the optimization problem cannot be solved."""


class OptimizerService:
    """Wraps PyPortfolioOpt behind a small, testable interface."""

    def estimates(self, prices: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
        """Annualized mean return vector and covariance matrix from prices."""
        mu = expected_returns.mean_historical_return(prices, frequency=TRADING_DAYS)
        cov = risk_models.sample_cov(prices, frequency=TRADING_DAYS)
        return mu, cov

    def _solve(self, mu: pd.Series, cov: pd.DataFrame, objective: str,
               target_return: float | None = None) -> dict[str, float]:
        ef = EfficientFrontier(mu, cov, weight_bounds=(0.0, 1.0))
        if objective == "min_vol":
            ef.min_volatility()
        elif objective == "max_sharpe":
            ef.max_sharpe(risk_free_rate=0.0)
        elif objective == "efficient_return":
            if target_return is None:
                raise OptimizationError("target_return required")
            ef.efficient_return(target_return=target_return)
        else:
            raise OptimizationError(f"unknown objective: {objective}")
        weights = ef.clean_weights(cutoff=1e-4)
        total = sum(weights.values())
        weights = {k: round(v / total, 6) for k, v in weights.items() if v / total > 1e-6}
        return weights

    @staticmethod
    def portfolio_stats(weights: dict[str, float], mu: pd.Series,
                        cov: pd.DataFrame) -> tuple[float, float, float]:
        """Return (expected_return, volatility, sharpe) for given weights."""
        w = np.array([weights.get(t, 0.0) for t in mu.index])
        ret = float(w @ mu.values)
        vol = float(np.sqrt(max(w @ cov.values @ w, 1e-18)))
        sharpe = ret / vol if vol > 0 else 0.0
        return ret, vol, sharpe

    def min_volatility(self, mu: pd.Series, cov: pd.DataFrame) -> dict[str, float]:
        return self._solve(mu, cov, "min_vol")

    def max_sharpe(self, mu: pd.Series, cov: pd.DataFrame) -> dict[str, float]:
        return self._solve(mu, cov, "max_sharpe")

    def for_volatility_band(self, mu: pd.Series, cov: pd.DataFrame,
                            band: tuple[float, float]) -> tuple[dict[str, float], str]:
        """Pick the efficient portfolio whose volatility best matches the band.

        Strategy: among the frontier portfolios whose volatility lies inside the
        band, return the one with the highest Sharpe ratio; if none fits, return
        the portfolio closest to the band's midpoint volatility.
        """
        frontier = self.efficient_frontier(mu, cov)
        lo, hi = band
        inside = [p for p in frontier if lo <= p["volatility"] <= hi]
        if inside:
            best = max(inside, key=lambda p: p["sharpe"])
            return best["weights"], "band_max_sharpe"
        midpoint = (lo + hi) / 2
        closest = min(frontier, key=lambda p: abs(p["volatility"] - midpoint))
        return closest["weights"], "band_closest"

    def efficient_frontier(self, mu: pd.Series, cov: pd.DataFrame,
                           points: int = FRONTIER_POINTS) -> list[dict]:
        """Frontier from the min-vol return up to the max single-asset return."""
        ef = EfficientFrontier(mu, cov, weight_bounds=(0.0, 1.0))
        try:
            ef_min = ef.min_volatility()
        except Exception as exc:  # noqa: BLE001
            raise OptimizationError(f"frontier floor failed: {exc}") from exc
        ret_floor, vol_floor, _ = self.portfolio_stats(ef_min, mu, cov)
        ret_cap = float(mu.max())
        if ret_cap <= ret_floor:
            ret_cap = ret_floor * 1.5 + 0.01
        targets = np.linspace(ret_floor, ret_cap, points)
        frontier: list[dict] = []
        for target in targets:
            try:
                weights = self._solve(mu, cov, "efficient_return", float(target))
                ret, vol, sharpe = self.portfolio_stats(weights, mu, cov)
                frontier.append({"volatility": vol, "ret": ret, "sharpe": sharpe, "weights": weights})
            except Exception:  # noqa: BLE001 - skip infeasible target
                continue
        return frontier
