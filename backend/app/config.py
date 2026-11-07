"""FinSight configuration: asset universe, risk profiles, and paths."""
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "prices.db"
SNAPSHOT_CSV = DATA_DIR / "prices_snapshot.csv"

# History window used for estimation and backtesting
START_DATE = "2016-01-01"

# Liquid ETF universe spanning HK equity, US equity, bonds and gold.
ASSET_UNIVERSE = {
    "2800.HK": "Tracker Fund of Hong Kong",
    "SPY": "SPDR S&P 500 ETF",
    "QQQ": "Invesco Nasdaq-100 ETF",
    "VTI": "Vanguard Total Stock Market ETF",
    "AGG": "iShares Core US Aggregate Bond ETF",
    "IEF": "iShares 7-10 Year Treasury Bond ETF",
    "GLD": "SPDR Gold Shares",
    "EEM": "iShares MSCI Emerging Markets ETF",
}

TRADING_DAYS = 252
REBALANCE_COST_BPS = 10          # one-way transaction cost assumption
ML_BLEND_ALPHA = 0.30            # weight of ML view in blended expected returns
FRONTIER_POINTS = 50


class RiskProfile:
    """Static risk-profile definitions keyed by profile name."""

    DEFINITIONS = {
        "conservative": {
            "label": "Conservative",
            "vol_band": (0.03, 0.09),
            "description": "Capital preservation first; bond-heavy allocation with modest equity exposure.",
        },
        "balanced": {
            "label": "Balanced",
            "vol_band": (0.09, 0.16),
            "description": "Growth and stability in equal measure; diversified across equities and bonds.",
        },
        "aggressive": {
            "label": "Aggressive",
            "vol_band": (0.16, 0.28),
            "description": "Long-horizon growth; equity-heavy allocation that tolerates drawdowns.",
        },
    }


def score_to_profile(score: float) -> str:
    """Map a 0-100 risk score to a profile name."""
    if score < 34:
        return "conservative"
    if score < 67:
        return "balanced"
    return "aggressive"
