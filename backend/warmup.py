"""Warm up the price cache with real Yahoo Finance data and smoke-test the API.

Run:  python warmup.py
- Downloads the full universe from 2016-01-01 into the SQLite cache
- Writes the offline CSV snapshot (demo fallback)
- Exercises every endpoint against real data
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient

from app.config import ASSET_UNIVERSE, START_DATE
from app.main import create_app
from app.services.data_service import DataService


def main() -> None:
    ds = DataService(allow_network=True)
    tickers = list(ASSET_UNIVERSE.keys())
    print("downloading real prices ...")
    prices = ds.get_history(tickers, START_DATE, allow_network=True)
    ds.write_snapshot(prices)
    print(f"cache warmed: {prices.shape[0]} rows x {prices.shape[1]} tickers, "
          f"{prices.index.min().date()} -> {prices.index.max().date()}")

    app = create_app(data_service=ds)
    client = TestClient(app)

    checks = [
        ("health", "GET", "/api/health", None),
        ("universe", "GET", "/api/universe", None),
        ("frontier", "GET", "/api/frontier", None),
        ("eda", "GET", "/api/eda", None),
        ("market SPY", "GET", "/api/market/SPY", None),
        ("walkforward", "GET", "/api/ml/walkforward", None),
        ("profile", "POST", "/api/profile", {
            "age": 30, "horizon_years": 20, "loss_tolerance": 4,
            "liquidity_needs": 2, "experience": 3}),
        ("optimize balanced+ML", "POST", "/api/optimize",
         {"profile": "balanced", "use_ml": True, "amount": 100000}),
        ("backtest", "POST", "/api/backtest", {"strategy": "max_sharpe", "use_ml": False}),
    ]
    for name, method, url, payload in checks:
        resp = client.request(method, url, json=payload)
        status = "OK " if resp.status_code == 200 else "ERR"
        print(f"  [{status}] {name}: {resp.status_code}")
        if resp.status_code != 200:
            print(resp.text[:500])
            sys.exit(1)

    opt = client.post("/api/optimize", json={"profile": "balanced", "use_ml": True}).json()
    weights = ", ".join(f"{t}:{w:.0%}" for t, w in sorted(opt["weights"].items(), key=lambda kv: -kv[1]))
    print(f"balanced+ML weights: {weights}")
    print(f"exp_ret={opt['expected_return']:.2%} vol={opt['volatility']:.2%} "
          f"sharpe={opt['sharpe']:.2f} method={opt['method']}")
    print("ALL SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
