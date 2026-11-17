"""backtest_fixed_weights tests: validation, correctness, determinism, speed."""
import pytest

from app.services.backtest_service import BacktestError, BacktestService


@pytest.fixture(scope="module")
def backtester():
    return BacktestService(seed=42)


def test_rejects_empty_weights(backtester, synthetic_prices):
    with pytest.raises(BacktestError):
        backtester.backtest_fixed_weights(synthetic_prices, {})


def test_rejects_unknown_ticker(backtester, synthetic_prices):
    with pytest.raises(BacktestError):
        backtester.backtest_fixed_weights(synthetic_prices, {"NOPE": 1.0})


def test_rejects_negative_weights(backtester, synthetic_prices):
    with pytest.raises(BacktestError):
        backtester.backtest_fixed_weights(synthetic_prices, {"SPY": 1.2, "AGG": -0.2})


def test_rejects_weights_not_summing_to_one(backtester, synthetic_prices):
    with pytest.raises(BacktestError):
        backtester.backtest_fixed_weights(synthetic_prices, {"SPY": 0.5, "AGG": 0.4})


def test_runs_and_matches_grid(backtester, synthetic_prices):
    out = backtester.backtest_fixed_weights(synthetic_prices, {"SPY": 0.6, "AGG": 0.4})
    assert len(out["dates"]) == len(out["nav"]) >= 24
    assert out["nav"][0] == 1.0
    assert out["weights"] == {"SPY": 0.6, "AGG": 0.4}
    names = [m["name"] for m in out["metrics"]]
    assert "benchmark_SPY" in names


def test_all_in_single_asset_close_to_buy_hold(backtester, synthetic_prices):
    """100% SPY fixed-weight NAV should track buy-and-hold SPY closely (small cost drag)."""
    out = backtester.backtest_fixed_weights(synthetic_prices, {"SPY": 1.0})
    spy = next(m for m in out["metrics"] if m["name"] == "benchmark_SPY")
    fw = out["metrics"][0]
    # monthly rebalancing of a single asset is buy-and-hold + one initial 10bp cost
    assert abs(fw["cagr"] - spy["cagr"]) < 0.01


def test_deterministic(backtester, synthetic_prices):
    r1 = backtester.backtest_fixed_weights(synthetic_prices, {"GLD": 0.3, "SPY": 0.7})
    r2 = backtester.backtest_fixed_weights(synthetic_prices, {"GLD": 0.3, "SPY": 0.7})
    assert r1["nav"] == r2["nav"]
    assert r1["metrics"] == r2["metrics"]


def test_more_gold_lower_volatility_directionally(backtester, synthetic_prices):
    """Synthetic AGG/GLD are low-vol: a bond+gold mix should be calmer than all-QQQ."""
    aggressive = backtester.backtest_fixed_weights(
        synthetic_prices, {"QQQ": 0.9, "GLD": 0.1})
    defensive = backtester.backtest_fixed_weights(
        synthetic_prices, {"QQQ": 0.1, "AGG": 0.45, "IEF": 0.45})
    vol_aggressive = aggressive["metrics"][0]["volatility"]
    vol_defensive = defensive["metrics"][0]["volatility"]
    assert vol_defensive < vol_aggressive


def test_50_50_blend_sits_between_components(backtester, synthetic_prices):
    """50/50 monthly-rebalanced CAGR should land between the single-asset CAGRs."""
    a = backtester.backtest_fixed_weights(synthetic_prices, {"SPY": 1.0})["metrics"][0]["cagr"]
    b = backtester.backtest_fixed_weights(synthetic_prices, {"AGG": 1.0})["metrics"][0]["cagr"]
    blend = backtester.backtest_fixed_weights(
        synthetic_prices, {"SPY": 0.5, "AGG": 0.5})["metrics"][0]["cagr"]
    lo, hi = sorted([a, b])
    assert lo - 0.005 <= blend <= hi + 0.005


def test_api_agent_endpoint_contract(client, monkeypatch):
    def canned(question, history=None):
        return {"answer": "With 30% gold ... (grounded)",
                "tool_trace": [{"tool": "backtest_fixed_weights", "args": {},
                                "result": {"final_growth_multiple": 2.1}}],
                }
    monkeypatch.setattr(client.app.state.agent, "chat", canned)
    r = client.post("/api/agent/chat", json={"question": "What if gold were 30%?"})
    assert r.status_code == 200
    body = r.json()
    assert body["tools_used"] == ["backtest_fixed_weights"]
    assert body["tool_trace"][0]["tool"] == "backtest_fixed_weights"


def test_api_agent_offline_is_503(client, monkeypatch):
    # `available` is a read-only property; empty the key pool instead
    monkeypatch.setattr(client.app.state.agent, "keys", [])
    r = client.post("/api/agent/chat", json={"question": "hi"})
    assert r.status_code == 503
    assert "unavailable" in r.json()["detail"]


def test_api_agent_questions_endpoint(client, monkeypatch):
    canned = [{"id": 1, "ts": "2026-11-18T00:00:00", "question": "q?",
               "answer": "a", "tools": ["get_correlation"]}]
    monkeypatch.setattr(client.app.state.audit, "list_agent", lambda limit=50: canned)
    r = client.get("/api/agent/questions")
    assert r.status_code == 200
    assert r.json()[0]["tools"] == ["get_correlation"]
