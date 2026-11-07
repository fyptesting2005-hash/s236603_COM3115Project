"""Shared fixtures: synthetic price data and a hermetic API client.

No test hits the network; every service is exercised against a synthetic
geometric-random-walk price history with a fixed seed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import ASSET_UNIVERSE, START_DATE  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.data_service import DataService  # noqa: E402

N_DAYS = 1500  # ~6 years of business days


@pytest.fixture(scope="session")
def synthetic_prices() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2021-01-04", periods=N_DAYS)
    specs = {  # (annual drift, annual vol) - diverse but well-behaved
        "2800.HK": (0.05, 0.18), "SPY": (0.08, 0.15), "QQQ": (0.11, 0.22),
        "VTI": (0.07, 0.16), "AGG": (0.02, 0.06), "IEF": (0.015, 0.07),
        "GLD": (0.04, 0.14), "EEM": (0.03, 0.20),
    }
    data = {}
    for ticker, (drift, vol) in specs.items():
        daily_mu = drift / 252
        daily_sigma = vol / np.sqrt(252)
        shocks = rng.normal(daily_mu, daily_sigma, N_DAYS)
        data[ticker] = 100.0 * np.exp(np.cumsum(shocks))
    return pd.DataFrame(data, index=dates)


@pytest.fixture()
def data_service(synthetic_prices, tmp_path) -> DataService:
    svc = DataService(db_path=tmp_path / "prices.db",
                      snapshot_csv=tmp_path / "snapshot.csv",
                      allow_network=False)
    svc._write_cache(synthetic_prices)
    return svc


@pytest.fixture()
def client(data_service, tmp_path) -> TestClient:
    app = create_app(data_service=data_service, audit_path=tmp_path / "audit.db")
    return TestClient(app)


@pytest.fixture()
def tickers():
    return list(ASSET_UNIVERSE.keys())
