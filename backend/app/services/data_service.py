"""DataService: market data acquisition, SQLite caching, and cleaning.

Cache-first design:
1. Read from the SQLite cache.
2. If the cache is stale (or empty) and the network is allowed, refresh from
   Yahoo Finance via yfinance and upsert into the cache.
3. If the network fails, fall back to the last cached snapshot (or the bundled
   offline CSV snapshot) so demos never depend on connectivity.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import DB_PATH, SNAPSHOT_CSV, START_DATE, TRADING_DAYS


class DataUnavailableError(RuntimeError):
    """Raised when neither the cache nor the network can provide prices."""


class DataService:
    def __init__(self, db_path: Path = DB_PATH, snapshot_csv: Path = SNAPSHOT_CSV,
                 allow_network: bool = True) -> None:
        self.db_path = Path(db_path)
        self.snapshot_csv = Path(snapshot_csv)
        self.allow_network = allow_network
        self._download_lock = threading.Lock()
        self._ensure_table()

    # ---------- cache plumbing ----------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _ensure_table(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS prices ("
                " ticker TEXT NOT NULL, date TEXT NOT NULL, close REAL NOT NULL,"
                " PRIMARY KEY (ticker, date))"
            )

    def _read_cache(self, tickers: list[str], start: str) -> pd.DataFrame:
        query = "SELECT ticker, date, close FROM prices WHERE date >= ? AND ticker IN (%s)"
        placeholders = ",".join("?" for _ in tickers)
        with closing(self._connect()) as conn:
            df = pd.read_sql_query(query % placeholders, conn, params=(start, *tickers))
        if df.empty:
            return pd.DataFrame()
        pivot = df.pivot(index="date", columns="ticker", values="close")
        pivot.index = pd.to_datetime(pivot.index)
        return pivot.sort_index()

    def _write_cache(self, prices: pd.DataFrame) -> None:
        rows = [
            (ticker, date.strftime("%Y-%m-%d"), float(close))
            for date, row in prices.iterrows()
            for ticker, close in row.items()
            if pd.notna(close)
        ]
        with closing(self._connect()) as conn, conn:
            conn.executemany(
                "INSERT OR REPLACE INTO prices (ticker, date, close) VALUES (?, ?, ?)", rows
            )

    def _cache_is_stale(self, cached: pd.DataFrame, tickers: list[str]) -> bool:
        if cached.empty:
            return True
        # stale when the newest cached close is older than 5 calendar days,
        # or when any requested ticker is missing from the cache entirely
        if any(t not in cached.columns for t in tickers):
            return True
        newest = cached.index.max()
        return newest < pd.Timestamp.today().normalize() - timedelta(days=5)

    # ---------- network ----------
    def _download(self, tickers: list[str], start: str) -> pd.DataFrame:
        import yfinance as yf

        raw = yf.download(tickers, start=start, auto_adjust=True, progress=False)
        if raw is None or raw.empty:
            raise DataUnavailableError("Yahoo Finance returned no data")
        close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        if isinstance(close, pd.Series):
            close = close.to_frame()
        close = close[tickers] if set(tickers).issubset(close.columns) else close
        close.index = pd.to_datetime(close.index).tz_localize(None)
        return close.dropna(how="all")

    # ---------- cleaning ----------
    @staticmethod
    def clean(prices: pd.DataFrame, max_ffill_days: int = 5) -> pd.DataFrame:
        """Align calendars, forward-fill short gaps, drop leading all-NaN rows."""
        if prices.empty:
            return prices
        cleaned = prices.sort_index().ffill(limit=max_ffill_days)
        cleaned = cleaned.dropna(how="all")
        # keep only rows from the first day on which at least half the assets trade
        first_valid = cleaned.apply(lambda s: s.first_valid_index()).dropna()
        if not first_valid.empty:
            cleaned = cleaned[cleaned.index >= first_valid.max()]
        return cleaned.dropna(how="any")

    # ---------- public API ----------
    def get_history(self, tickers: list[str], start: str = START_DATE,
                    allow_network: bool | None = None) -> pd.DataFrame:
        """Return cleaned adjusted-close prices, cache-first with offline fallback.

        Fallback order: fresh download -> cached columns -> offline snapshot for
        whatever tickers the cache is missing. Raises DataUnavailableError (-> 503)
        with a clear message if any requested ticker cannot be served.
        """
        allow_network = self.allow_network if allow_network is None else allow_network
        cached = self._read_cache(tickers, start)
        if self._cache_is_stale(cached, tickers) and allow_network:
            # one download at a time: N concurrent requests on a stale cache must
            # not trigger N full-history Yahoo Finance downloads
            with self._download_lock:
                try:
                    fresh = self._download(tickers, start)
                    self._write_cache(fresh)
                    cached = self._read_cache(tickers, start)
                except Exception:  # noqa: BLE001 - offline fallback is intentional
                    pass

        have = [t for t in tickers if not cached.empty and t in cached.columns]
        missing = [t for t in tickers if t not in have]
        if missing:
            snap = self._load_snapshot(missing, start)
            if not snap.empty:
                if cached.empty:
                    cached = snap
                else:
                    cached = cached.join(snap, how="outer")

        still_missing = [t for t in tickers if cached.empty or t not in cached.columns]
        if still_missing:
            raise DataUnavailableError(
                f"No price data available for: {still_missing} "
                "(cache empty/incomplete, network unavailable, no snapshot)"
            )
        cleaned = self.clean(cached[tickers])
        if cleaned.empty:
            raise DataUnavailableError(
                "No price data available: cache empty, network disabled, no snapshot"
            )
        return cleaned

    def _load_snapshot(self, tickers: list[str], start: str) -> pd.DataFrame:
        if not self.snapshot_csv.exists():
            return pd.DataFrame()
        snap = pd.read_csv(self.snapshot_csv, index_col=0, parse_dates=True)
        cols = [t for t in tickers if t in snap.columns]
        return snap.loc[snap.index >= pd.Timestamp(start), cols]

    def write_snapshot(self, prices: pd.DataFrame) -> None:
        """Persist the current cache content as an offline CSV fallback."""
        prices.to_csv(self.snapshot_csv)

    # ---------- derived ----------
    @staticmethod
    def log_returns(prices: pd.DataFrame) -> pd.DataFrame:
        return np.log(prices / prices.shift(1)).dropna(how="any")

    @staticmethod
    def max_drawdown(cumulative: pd.Series) -> float:
        running_max = cumulative.cummax()
        dd = cumulative / running_max - 1.0
        return float(dd.min())
