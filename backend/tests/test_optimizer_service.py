"""OptimizerService tests: weight constraints, frontier shape, band selection."""
import numpy as np
import pytest

from app.services.optimizer_service import OptimizerService


@pytest.fixture(scope="module")
def estimates(synthetic_prices_module):
    opt = OptimizerService()
    mu, cov = opt.estimates(synthetic_prices_module)
    return opt, mu, cov


@pytest.fixture(scope="module")
def synthetic_prices_module(synthetic_prices):
    return synthetic_prices


def test_estimates_are_annualized(estimates):
    _, mu, cov = estimates
    assert (mu > -1).all() and (mu < 2).all()
    diag = np.sqrt(np.diag(cov.values))
    # annualized vols should sit in a sane band for the synthetic universe
    assert (diag > 0.02).all() and (diag < 0.60).all()


def _assert_valid_weights(weights, tickers):
    assert set(weights) <= set(tickers)
    assert abs(sum(weights.values()) - 1.0) < 1e-4
    assert all(w >= 0 for w in weights.values())


def test_min_volatility_weights_valid(estimates, tickers):
    opt, mu, cov = estimates
    weights = opt.min_volatility(mu, cov)
    _assert_valid_weights(weights, tickers)


def test_max_sharpe_weights_valid(estimates, tickers):
    opt, mu, cov = estimates
    weights = opt.max_sharpe(mu, cov)
    _assert_valid_weights(weights, tickers)


def test_portfolio_stats_single_asset(estimates):
    opt, mu, cov = estimates
    ticker = mu.index[0]
    ret, vol, sharpe = opt.portfolio_stats({ticker: 1.0}, mu, cov)
    assert np.isclose(ret, mu[ticker], atol=1e-8)
    assert np.isclose(vol, np.sqrt(cov.loc[ticker, ticker]), atol=1e-6)
    assert np.isclose(sharpe, mu[ticker] / vol, atol=1e-6)


def test_frontier_volatility_is_monotone(estimates):
    opt, mu, cov = estimates
    frontier = opt.efficient_frontier(mu, cov, points=15)
    vols = [p["volatility"] for p in frontier]
    assert len(vols) >= 10
    # non-decreasing along the frontier from min-vol upward
    diffs = np.diff(vols)
    assert (diffs > -1e-6).all()


def test_frontier_weights_all_valid(estimates, tickers):
    opt, mu, cov = estimates
    frontier = opt.efficient_frontier(mu, cov, points=8)
    for point in frontier:
        _assert_valid_weights(point["weights"], tickers)


def test_band_selection_returns_portfolio(estimates):
    opt, mu, cov = estimates
    weights, method = opt.for_volatility_band(mu, cov, (0.05, 0.12))
    _assert_valid_weights(weights, mu.index)
    assert method in ("band_max_sharpe", "band_closest")


def test_band_selection_prefers_inside_band(estimates):
    opt, mu, cov = estimates
    frontier = opt.efficient_frontier(mu, cov, points=20)
    vols = [p["volatility"] for p in frontier]
    lo, hi = float(np.percentile(vols, 30)), float(np.percentile(vols, 60))
    weights, method = opt.for_volatility_band(mu, cov, (lo, hi))
    _, vol, _ = opt.portfolio_stats(weights, mu, cov)
    if method == "band_max_sharpe":
        assert lo - 1e-6 <= vol <= hi + 1e-6
