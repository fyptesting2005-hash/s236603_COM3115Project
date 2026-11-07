"""BacktestService tests: determinism, metrics sanity, both strategies."""
import pytest

from app.services.backtest_service import BacktestError, BacktestService


@pytest.fixture(scope="module")
def backtester():
    return BacktestService(seed=42)


def test_backtest_max_sharpe_runs(backtester, synthetic_prices):
    result = backtester.run(synthetic_prices, strategy="max_sharpe", use_ml=False)
    assert len(result["dates"]) == len(result["strategy_nav"])
    assert len(result["dates"]) >= 24  # ~6y minus warmup
    assert result["strategy_nav"][0] == 1.0


def test_backtest_metrics_sane(backtester, synthetic_prices):
    result = backtester.run(synthetic_prices, strategy="max_sharpe", use_ml=False)
    for m in result["metrics"]:
        assert 0.05 < m["volatility"] < 0.60
        assert -1.0 < m["max_drawdown"] <= 0.0
        assert m["sharpe"] > -3.0


def test_backtest_includes_benchmarks(backtester, synthetic_prices):
    result = backtester.run(synthetic_prices, strategy="max_sharpe", use_ml=False)
    names = [m["name"] for m in result["metrics"]]
    assert "benchmark_2800.HK" in names
    assert "benchmark_SPY" in names


def test_backtest_is_deterministic(backtester, synthetic_prices):
    r1 = backtester.run(synthetic_prices, strategy="max_sharpe", use_ml=False)
    r2 = backtester.run(synthetic_prices, strategy="max_sharpe", use_ml=False)
    assert r1["strategy_nav"] == r2["strategy_nav"]
    assert r1["metrics"] == r2["metrics"]


def test_backtest_min_vol_runs(backtester, synthetic_prices):
    result = backtester.run(synthetic_prices, strategy="min_vol", use_ml=False)
    assert len(result["strategy_nav"]) >= 24


def test_backtest_ml_strategy_smoke(backtester, synthetic_prices):
    """ML-blended strategy runs end-to-end on a shorter history (speed)."""
    short = synthetic_prices.tail(1000)
    result = backtester.run(short, strategy="max_sharpe_ml", use_ml=True)
    assert len(result["strategy_nav"]) >= 12


def test_unknown_strategy_raises(backtester, synthetic_prices):
    with pytest.raises(BacktestError):
        backtester.run(synthetic_prices, strategy="nope")
