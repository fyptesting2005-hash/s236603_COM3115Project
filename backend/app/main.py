"""FinSight FastAPI application.

Run:  uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import APP_DIR, ASSET_UNIVERSE, DB_PATH, RiskProfile, score_to_profile
from .schemas import (
    AuditEntry, BacktestRequest, BacktestResponse, EdaResponse, AssetStats,
    ExplainRequest, ExplainResponse, FrontierPoint, MarketPoint, MarketResponse,
    OptimizeRequest, OptimizeResponse, ProfileResponse, RiskAnswers,
)
from .services.ai_service import AIService
from .services.backtest_service import BacktestError, BacktestService
from .services.data_service import DataUnavailableError, DataService
from .services.ml_service import MLService
from .services.optimizer_service import OptimizationError, OptimizerService

DISCLAIMER = (
    "FinSight is an educational prototype. It is not licensed by the SFC and does "
    "not provide regulated investment advice. Past performance does not predict "
    "future returns."
)


class AuditLog:
    """Append-only SQLite audit trail of every recommendation (compliance)."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS recommendations ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " ts TEXT NOT NULL, profile TEXT NOT NULL, weights_json TEXT NOT NULL,"
                " expected_return REAL NOT NULL, volatility REAL NOT NULL, use_ml INTEGER NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def append(self, profile: str, weights: dict, exp_ret: float, vol: float,
               use_ml: bool) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO recommendations (ts, profile, weights_json, expected_return,"
                " volatility, use_ml) VALUES (?, ?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), profile, json.dumps(weights),
                 exp_ret, vol, int(use_ml)),
            )
            return int(cur.lastrowid)

    def list(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, ts, profile, weights_json, expected_return, volatility, use_ml"
                " FROM recommendations ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {"id": r[0], "ts": r[1], "profile": r[2], "weights": json.loads(r[3]),
             "expected_return": r[4], "volatility": r[5], "use_ml": bool(r[6])}
            for r in rows
        ]


def score_answers(answers: RiskAnswers) -> float:
    """Weighted 0-100 risk score from questionnaire answers."""
    age_component = max(0.0, min(1.0, (100 - answers.age) / 70))
    horizon_component = max(0.0, min(1.0, answers.horizon_years / 30))
    loss_component = (answers.loss_tolerance - 1) / 4
    liquidity_component = (5 - answers.liquidity_needs) / 4
    experience_component = (answers.experience - 1) / 4
    score = (
        0.20 * age_component
        + 0.30 * horizon_component
        + 0.25 * loss_component
        + 0.15 * liquidity_component
        + 0.10 * experience_component
    ) * 100
    return round(score, 1)


def create_app(data_service: DataService | None = None,
               audit_path: Path | None = None) -> FastAPI:
    app = FastAPI(title="FinSight API", version="1.0.0",
                  description="AI Robo-Advisor prototype - COM3115 (educational, not SFC-licensed)")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"], allow_headers=["*"],
    )

    ds = data_service or DataService(db_path=DB_PATH)
    optimizer = OptimizerService()
    ml = MLService()
    backtester = BacktestService(optimizer=optimizer, ml=ml)
    audit = AuditLog(audit_path or APP_DIR / "data" / "audit.db")
    ai = AIService()

    app.state.data_service = ds
    app.state.optimizer = optimizer
    app.state.ml = ml
    app.state.backtester = backtester
    app.state.audit = audit
    app.state.ai = ai

    def history_or_404():
        try:
            return ds.get_history(list(ASSET_UNIVERSE.keys()))
        except DataUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    # ---------- meta ----------
    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "service": "finsight", "disclaimer": DISCLAIMER}

    @app.get("/api/universe")
    def universe() -> dict:
        return {"tickers": [{"ticker": t, "name": n} for t, n in ASSET_UNIVERSE.items()]}

    # ---------- risk profiling ----------
    @app.post("/api/profile", response_model=ProfileResponse)
    def profile(answers: RiskAnswers) -> ProfileResponse:
        score = score_answers(answers)
        profile_name = score_to_profile(score)
        definition = RiskProfile.DEFINITIONS[profile_name]
        return ProfileResponse(
            score=score,
            profile=profile_name,
            label=definition["label"],
            description=definition["description"],
            target_vol_band=list(definition["vol_band"]),
            suitability_note=DISCLAIMER,
        )

    # ---------- optimization ----------
    @app.post("/api/optimize", response_model=OptimizeResponse)
    def optimize(req: OptimizeRequest) -> OptimizeResponse:
        prices = history_or_404()
        definition = RiskProfile.DEFINITIONS[req.profile]
        mu, cov = optimizer.estimates(prices)
        if req.use_ml:
            views = ml.current_views(prices)
            mu = ml.blend_mu(mu, views)
        try:
            weights, method = optimizer.for_volatility_band(mu, cov, tuple(definition["vol_band"]))
        except OptimizationError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        exp_ret, vol, sharpe = optimizer.portfolio_stats(weights, mu, cov)

        note = DISCLAIMER
        lo, hi = definition["vol_band"]
        if not (lo <= vol <= hi):
            note = (
                f"Warning: portfolio volatility {vol:.1%} falls outside the {definition['label']} "
                f"target band {lo:.0%}-{hi:.0%}. " + DISCLAIMER
            )
        allocations = None
        if req.amount:
            allocations = {t: round(req.amount * w, 2) for t, w in weights.items()}

        audit.append(req.profile, weights, exp_ret, vol, req.use_ml)
        return OptimizeResponse(
            profile=req.profile, weights=weights, expected_return=exp_ret,
            volatility=vol, sharpe=sharpe, target_vol_band=[lo, hi],
            method=method, amount_allocations=allocations, suitability_note=note,
        )

    # ---------- efficient frontier ----------
    @app.get("/api/frontier")
    def frontier() -> dict:
        prices = history_or_404()
        mu, cov = optimizer.estimates(prices)
        points = [FrontierPoint(**p) for p in optimizer.efficient_frontier(mu, cov)]
        positions = {}
        for name, definition in RiskProfile.DEFINITIONS.items():
            try:
                w, _ = optimizer.for_volatility_band(mu, cov, tuple(definition["vol_band"]))
                ret, vol, _ = optimizer.portfolio_stats(w, mu, cov)
                positions[name] = {"volatility": vol, "ret": ret}
            except OptimizationError:
                continue
        return {"points": [p.model_dump() for p in points], "profile_positions": positions}

    # ---------- backtest ----------
    @app.post("/api/backtest", response_model=BacktestResponse)
    def backtest(req: BacktestRequest) -> BacktestResponse:
        prices = history_or_404()
        try:
            result = backtester.run(prices, strategy=req.strategy, use_ml=req.use_ml)
        except BacktestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return BacktestResponse(
            strategy=req.strategy,
            metrics=result["metrics"],
            curves=[{"name": req.strategy, "dates": result["dates"],
                     "values": result["strategy_nav"]}]
            + [{"name": f"benchmark_{t}", "dates": c["dates"], "values": c["values"]}
               for t, c in result["benchmarks"].items()],
        )

    # ---------- EDA ----------
    @app.get("/api/eda", response_model=EdaResponse)
    def eda() -> EdaResponse:
        prices = history_or_404()
        rets = prices.pct_change().dropna(how="any")
        assets = []
        for ticker in prices.columns:
            cum = (1 + rets[ticker]).cumprod()
            running_max = cum.cummax()
            mdd = float((cum / running_max - 1).min())
            ann_ret = float(rets[ticker].mean() * 252)
            ann_vol = float(rets[ticker].std() * (252 ** 0.5))
            assets.append(AssetStats(
                ticker=ticker, name=ASSET_UNIVERSE.get(ticker, ticker),
                ann_return=ann_ret, ann_vol=ann_vol,
                sharpe=ann_ret / ann_vol if ann_vol > 0 else 0.0,
                max_drawdown=mdd,
                missing_days=int(prices[ticker].isna().sum()),
            ))
        corr = rets.corr().round(3)
        return EdaResponse(
            rows=int(len(prices)),
            start=str(prices.index.min().date()),
            end=str(prices.index.max().date()),
            tickers=list(prices.columns),
            assets=assets,
            correlation={a: {b: float(corr.loc[a, b]) for b in corr.columns} for a in corr.index},
        )

    # ---------- market data ----------
    @app.get("/api/market/{ticker}", response_model=MarketResponse)
    def market(ticker: str) -> MarketResponse:
        if ticker not in ASSET_UNIVERSE:
            raise HTTPException(status_code=404, detail=f"unknown ticker: {ticker}")
        prices = history_or_404()
        series = prices[ticker].tail(252)
        points = [MarketPoint(date=str(d.date()), close=float(v))
                  for d, v in series.items()]
        return MarketResponse(ticker=ticker, name=ASSET_UNIVERSE[ticker],
                              points=points, last_close=float(series.iloc[-1]))

    # ---------- ML transparency ----------
    @app.get("/api/ml/walkforward")
    def walkforward() -> dict:
        prices = history_or_404()
        return ml.walk_forward_validate(prices)

    # ---------- audit ----------
    @app.get("/api/audit", response_model=list[AuditEntry])
    def audit_list(limit: int = 50) -> list[AuditEntry]:
        return [AuditEntry(**e) for e in audit.list(limit)]

    # ---------- AI commentary ----------
    @app.post("/api/explain", response_model=ExplainResponse)
    def explain(req: ExplainRequest) -> ExplainResponse:
        """Plain-language explanation of an already-computed portfolio.

        Grounded on the numbers the optimizer actually produced; degrades to a
        deterministic rule-based text when the AI backend is unavailable.
        """
        definition = RiskProfile.DEFINITIONS[req.profile]
        result = ai.explain_portfolio(
            profile_label=definition["label"],
            weights=req.weights,
            expected_return=req.expected_return,
            volatility=req.volatility,
            sharpe=req.sharpe,
        )
        return ExplainResponse(**result)

    return app


app = create_app()
