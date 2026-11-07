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
