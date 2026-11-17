# FinSight — Live Demo Checklist

Print this page or keep it on a second screen during the presentation (slides:
`docs/COM3115_Final_Presentation.pptx`, slide 12 is the demo script, slide 11 introduces the Copilot).

## T-1 day: preparation

- [ ] `cd backend && pip install -r requirements.txt` (clean venv check)
- [ ] `python warmup.py` — cache warms from Yahoo Finance; all 9 smoke checks must print `[OK]`
- [ ] `pytest -q` from `backend/` — expect **76 passed**
- [ ] `cd ../frontend && npm install && npm run build` — expect a clean build
- [ ] Confirm `backend/app/data/prices_snapshot.csv` exists (offline fallback)
- [ ] **Pre-warm the demo path once** (results are then cached and instant):
      start backend + frontend, walk the full flow: questionnaire → portfolio →
      Frontier tab → Backtest tab (click all three strategies) → EDA → Market Data
- [ ] Optional rehearsal: present the whole flow once with the slides

## Demo day: 5-minute script

| # | Screen | Action | Expected |
|---|--------|--------|----------|
| 1 | Questionnaire | Age 28, horizon 20, loss tolerance 5, liquidity 1, experience 4, amount 500000 → Generate | Score **87.5** → **Aggressive**, band 16–28% |
| 2 | Portfolio | "View my portfolio" | QQQ ≈ 68% / GLD ≈ 32% of HKD 500,000; vol ≈ 16.3%; suitability note visible |
| 3 | Efficient Frontier | Click tab | 50-point frontier; three profile dots; aggressive marker on the curve |
| 4 | Backtest | Click tab; show Max Sharpe first, then ML views | Max Sharpe: CAGR 7.3%, Sharpe 0.74, MDD −21.3%; ML lower (honest result) |
| 5 | Data Explorer (EDA) | Click tab; scroll to correlation matrix | 2,797 days; 2800.HK vs SPY correlation ≈ 0.12; bonds negative |
| 6 | Portfolio (AI) | Back on Portfolio tab, click "✨ Explain this portfolio (AI)" | Gemini commentary grounded on the real weights/metrics; badge shows "Gemini" |
| 7 | Copilot (agent) | Click the ✦ floating button (bottom-right), pick "What if gold were 30%…?" | Answer with real CAGR/vol/Sharpe/MDD numbers + a `backtest_fixed_weights` tool chip |

Fallbacks:

- **Gemini unreachable / no key** → `/api/explain` degrades to the rule-based
  explanation and the badge shows "offline fallback" — say: "the AI layer degrades
  gracefully, exactly like the rest of the system."
- **Network dies** → backend already serves from the SQLite cache; if the cache is
  missing, `DataService` falls back to `prices_snapshot.csv`. Say: "the demo is
  deliberately offline-capable."
- **Someone breaks the sliders** → "Restart questionnaire" resets state.
- **First ML-backtest click is slow** (~1–2 min on cold cache) → pre-warmed at T-1 day;
  if asked, explain the walk-forward RF refit per month and the result cache.

## Likely Q&A

- **Why did the ML strategy underperform?** Leak-free walk-forward hit rate 64.9% but RMSE ~0.4%
  below baseline; the optimizer consumes magnitude, not direction; α=0.30 propagates
  estimation error into the weakest input of MPT. Report Ch. 5.3.
- **Why GLD so large in the balanced portfolio?** Recent-window mean-variance favours
  gold's 2016–2026 Sharpe (0.79) and its near-zero correlation with equities.
- **Is this legal as a product?** Advising on securities = SFC Type 4; the prototype is
  educational: no funds, no orders, no fees, disclaimers everywhere. Report Ch. 7.
- **Where is the data from?** Yahoo Finance adjusted closes, cached in SQLite, snapshot
  committed for offline demos.
- **How do you know the ML isn't overfitting?** Walk-forward-only validation (refit
  monthly, train strictly on the past); fixed seeds; deterministic tests.
- **Can the AI hallucinate numbers?** The prompt carries only the optimizer's computed
  metrics and instructs the model not to invent figures; any parse failure falls back to
  the rule-based text. The badge always shows which source produced the commentary.
- **Is the Copilot just ChatGPT plugged in?** No — it is tool-grounded: it may only get
  numbers by calling FinSight's own endpoints (asset stats, correlations, fixed-weight
  backtests), the tool-call trace is displayed under every answer, and questions are
  audit-logged. Show the chip under an answer when asked.
- **What happens to the Copilot without an API key?** It shows "offline" and everything
  else (questionnaire, optimizer, backtest, EDA) keeps working — deliberate degradation.
