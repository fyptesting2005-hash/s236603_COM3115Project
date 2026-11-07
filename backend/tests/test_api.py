"""API contract tests via FastAPI TestClient (hermetic, synthetic data)."""
import pytest


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "SFC" in body["disclaimer"]


def test_universe(client):
    r = client.get("/api/universe")
    assert r.status_code == 200
    tickers = [t["ticker"] for t in r.json()["tickers"]]
    assert "2800.HK" in tickers and "SPY" in tickers


def test_profile_mapping_extremes(client):
    aggressive = client.post("/api/profile", json={
        "age": 25, "horizon_years": 25, "loss_tolerance": 5,
        "liquidity_needs": 1, "experience": 5,
    }).json()
    assert aggressive["profile"] == "aggressive"

    conservative = client.post("/api/profile", json={
        "age": 70, "horizon_years": 2, "loss_tolerance": 1,
        "liquidity_needs": 5, "experience": 1,
    }).json()
    assert conservative["profile"] == "conservative"


def test_profile_rejects_invalid(client):
    r = client.post("/api/profile", json={
        "age": 10, "horizon_years": 5, "loss_tolerance": 3,
        "liquidity_needs": 3, "experience": 3,
    })
    assert r.status_code == 422


def test_optimize_returns_valid_portfolio(client, tickers):
    r = client.post("/api/optimize", json={"profile": "balanced", "use_ml": False})
    assert r.status_code == 200
    body = r.json()
    assert abs(sum(body["weights"].values()) - 1.0) < 1e-3
    assert all(w >= 0 for w in body["weights"].values())
    assert body["target_vol_band"] == [0.09, 0.16]
    assert "disclaimer" in body["suitability_note"].lower() or "prototype" in body["suitability_note"].lower()


def test_optimize_with_amount_allocations(client):
    r = client.post("/api/optimize", json={
        "profile": "conservative", "use_ml": False, "amount": 100000,
    })
    assert r.status_code == 200
    allocations = r.json()["amount_allocations"]
    assert abs(sum(allocations.values()) - 100000) < 1.0


def test_optimize_appends_audit(client):
    before = len(client.get("/api/audit").json())
    client.post("/api/optimize", json={"profile": "aggressive", "use_ml": False})
    after = client.get("/api/audit").json()
    assert len(after) == before + 1
    assert after[0]["profile"] == "aggressive"


def test_frontier_shape(client):
    r = client.get("/api/frontier")
    assert r.status_code == 200
    body = r.json()
    assert len(body["points"]) >= 10
    p0 = body["points"][0]
    assert {"volatility", "ret", "sharpe", "weights"} <= set(p0)
    assert "conservative" in body["profile_positions"]


def test_backtest_endpoint(client):
    r = client.post("/api/backtest", json={"strategy": "max_sharpe", "use_ml": False})
    assert r.status_code == 200
    body = r.json()
    assert body["strategy"] == "max_sharpe"
    names = [m["name"] for m in body["metrics"]]
    assert "benchmark_SPY" in names
    assert len(body["curves"]) >= 2


def test_eda_endpoint(client, tickers):
    r = client.get("/api/eda")
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] > 1000
    assert set(body["tickers"]) == set(tickers)
    assets = {a["ticker"]: a for a in body["assets"]}
    assert assets["SPY"]["ann_vol"] > 0
    assert -1 < assets["SPY"]["max_drawdown"] <= 0
    corr_spy = body["correlation"]["SPY"]
    assert abs(corr_spy["SPY"] - 1.0) < 1e-6


def test_market_endpoint_and_404(client):
    r = client.get("/api/market/SPY")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "SPY"
    assert len(body["points"]) > 200
    assert client.get("/api/market/NOPE").status_code == 404


def test_walkforward_endpoint(client):
    r = client.get("/api/ml/walkforward")
    assert r.status_code == 200
    body = r.json()
    assert body["months_evaluated"] > 0
    assert 0 <= body["hit_rate"] <= 1
