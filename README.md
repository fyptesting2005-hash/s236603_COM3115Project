# FinSight — AI-Powered Personal Portfolio Advisor

**COM3115 Financial Technology — Final Group Project (Track 2: AI & Machine Learning in FinTech)**

FinSight is an automated investment advisory prototype that profiles a user's risk tolerance,
then builds a personalized, optimized portfolio using real-time market data. It combines
Modern Portfolio Theory (Markowitz Efficient Frontier) with machine learning return/volatility
prediction, wrapped in a compliance-aware onboarding flow (SFC suitability & KYC-style checks).

> ⚠️ Educational prototype only. Not a licensed investment advisory service. Not regulated by the SFC.

## Features

| # | Feature | Course Mapping |
|---|---------|----------------|
| 1 | Risk-profiling questionnaire (age / horizon / loss tolerance / liquidity) → Conservative / Balanced / Aggressive | KYC-style onboarding, suitability |
| 2 | Real-time market data (HK + US ETFs) via Yahoo Finance with SQLite caching | Data engineering |
| 3 | Markowitz optimization: Min-Volatility, Max-Sharpe, Efficient Frontier | MPT (MILO a) |
| 4 | ML expected-return & volatility features (Random Forest, walk-forward validation) | ML regression (MILO d) |
| 5 | Vectorized backtesting vs. HSI / SPY benchmarks (CAGR, Sharpe, Max Drawdown) | Analytics (MILO d) |
| 6 | React dashboard: frontier, allocation, equity curve, EDA tab | Full-stack integration (MILO b) |
| 7 | Compliance module: risk-suitability matching, disclaimers, audit log | Regulatory (MILO c) |
| 8 | Gemini-powered plain-language portfolio commentary (grounded on computed metrics, offline fallback) | GenAI integration (MILO b/d) |
| 9 | **FinSight Copilot** — a tool-grounded AI agent: it answers what-if questions by calling the system's own analytics (asset stats, correlations, fixed-weight backtests); every answer ships with the tool-call trace | Agentic AI (MILO b) |

## Architecture

```
Browser → React SPA (Vite + Recharts)
              │ REST (JSON)
              ▼
        FastAPI (Python 3.13)
        ├─ DataService       yfinance + SQLite cache
        ├─ OptimizerService  PyPortfolioOpt (Markowitz)
        ├─ MLService         scikit-learn RF + walk-forward CV
        └─ BacktestService   vectorized backtest engine
```

See `docs/architecture.png` and `docs/COM3115_Project_Proposal.docx` for details.

## Repository Layout

```
finsight/
├── backend/            FastAPI application
│   ├── app/            application code (services, schemas, main)
│   ├── tests/          pytest suite
│   └── notebooks/      EDA & model development notebooks
├── frontend/           React (Vite) dashboard
├── docs/               proposal, report, slides, diagrams
└── README.md
```

## Quick Start

### Backend (Python 3.10+)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

**AI commentary (optional):** copy `backend/.env.example` to `backend/.env` and paste a
Gemini API key to enable the "Explain this portfolio" button (`POST /api/explain`). The
key is read from the `GEMINI_API_KEY` env var or that file and is git-ignored. Without a
key — or offline — the endpoint deterministically degrades to a rule-based explanation,
so demos never break. Calls go to the `v1` REST endpoint with a model fallback chain
(`gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` → `gemma-4-31b-it`).

**FinSight Copilot (optional, agentic):** set `GEMINI_API_KEY_AGENT` in the same `.env`
to enable the floating Copilot on the dashboard (`POST /api/agent/chat`). The Copilot is
a tool-grounded agent: it can call `get_universe`, `get_asset_stats`, `get_correlation`
and `backtest_fixed_weights` (a fast constant-mix backtest added for what-if questions).
Answers must be grounded in tool output — the full tool-call trace is returned and shown
in the UI. Max 4 tool rounds per question; every question is written to the audit log.

### Frontend (Node 18+)

```bash
cd frontend
npm install
npm run dev
# Dashboard: http://localhost:5173
```

### Tests

```bash
cd backend
pytest -v
```

## Milestones (course schedule)

| Milestone | Deliverable | Status |
|-----------|-------------|--------|
| M1 (W4)  | Proposal & architecture diagram | ✅ `docs/` |
| M2 (W8)  | MVP: data pipeline + EDA + models + unit tests | ✅ `backend/` |
| M3 (W12) | System integration & frontend | ✅ `frontend/` |
| M4 (W13) | Final presentation, report, GitHub submission | ✅ `docs/` |

## Team

Solo project, developed with AI pair-programming assistance.
