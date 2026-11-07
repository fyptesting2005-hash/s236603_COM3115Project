"""Generate and execute the EDA notebook (Milestone 2 data deliverable).

Run:  python make_eda_notebook.py
- Builds notebooks/01_eda.ipynb via nbformat
- Executes it against the warmed SQLite cache (real market data)
- Key figures are exported to ../../docs/figures/ for the final report
"""
import sys
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parent
FIG_DIR = ROOT.parent / "docs" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

nb = nbf.v4.new_notebook()
cells = []

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell

cells.append(md(
    "# FinSight — Exploratory Data Analysis (Milestone 2)\n"
    "\n"
    "This notebook documents the data pipeline for the COM3115 project: acquisition,\n"
    "cleaning, preprocessing, and exploratory analysis of the ETF universe that feeds\n"
    "the optimizer and the ML model. Data source: Yahoo Finance via `yfinance`, cached\n"
    "in SQLite by `DataService` (run `python warmup.py` once to populate).\n"
    "\n"
    "**Universe**: 2800.HK, SPY, QQQ, VTI, AGG, IEF, GLD, EEM — daily adjusted closes."
))
cells.append(code(
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "import numpy as np\n"
    "import pandas as pd\n"
    "import matplotlib.pyplot as plt\n"
    "\n"
    "ROOT = Path.cwd().parent\n"
    "sys.path.insert(0, str(ROOT))\n"
    "\n"
    "from app.config import ASSET_UNIVERSE, START_DATE\n"
    "from app.services.data_service import DataService\n"
    "\n"
    "plt.rcParams['figure.dpi'] = 110\n"
    "plt.rcParams['axes.grid'] = True\n"
    "plt.rcParams['grid.alpha'] = 0.3\n"
    "FIG_DIR = ROOT / 'docs' / 'figures'\n"
    "FIG_DIR.mkdir(exist_ok=True)\n"
    "\n"
    "ds = DataService(allow_network=False)  # notebook uses the warmed cache\n"
    "tickers = list(ASSET_UNIVERSE)\n"
    "prices = ds.get_history(tickers, START_DATE)\n"
    "print(f'rows={len(prices)}, span={prices.index.min().date()} -> {prices.index.max().date()}')\n"
    "prices.tail(3)"
))
cells.append(md("## 1. Data quality and cleaning"))
cells.append(code(
    "# raw cache content before cleaning: count missing values per ticker\n"
    "raw = ds._read_cache(tickers, START_DATE)\n"
    "missing = raw.isna().sum()\n"
    "aligned = raw.dropna(how='any')\n"
    "print('rows raw:', len(raw), '| rows after calendar alignment:', len(aligned))\n"
    "pd.DataFrame({'missing_raw': missing, 'first_valid': raw.apply(lambda s: s.first_valid_index())})"
))
cells.append(md(
    "Cleaning policy (`DataService.clean`): forward-fill gaps of up to 5 trading days,\n"
    "drop rows where every ticker is missing, and start the panel on the first date on\n"
    "which **all** tickers quote, so the covariance matrix is computed on a common calendar."
))
cells.append(md("## 2. Price levels (normalized)"))
cells.append(code(
    "norm = prices / prices.iloc[0] * 100\n"
    "fig, ax = plt.subplots(figsize=(11, 5.5))\n"
    "for t in tickers:\n"
    "    ax.plot(norm.index, norm[t], label=t, linewidth=1.1)\n"
    "ax.set_title('Normalized adjusted closes (first day = 100)')\n"
    "ax.set_ylabel('index')\n"
    "ax.legend(ncol=4, fontsize=9)\n"
    "fig.tight_layout()\n"
    "fig.savefig(FIG_DIR / 'eda_prices_normalized.png', bbox_inches='tight')\n"
    "plt.show()"
))
cells.append(md("## 3. Return distribution properties"))
cells.append(code(
    "rets = ds.log_returns(prices)\n"
    "ann = pd.DataFrame({\n"
    "    'ann_return': rets.mean() * 252,\n"
    "    'ann_vol': rets.std() * np.sqrt(252),\n"
    "    'skew': rets.skew(),\n"
    "    'kurtosis': rets.kurtosis(),\n"
    "})\n"
    "ann['sharpe'] = ann['ann_return'] / ann['ann_vol']\n"
    "cum = (1 + rets).cumprod()\n"
    "ann['max_drawdown'] = (cum / cum.cummax() - 1).min()\n"
    "ann.round(3)"
))
cells.append(code(
    "fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))\n"
    "x = np.arange(len(tickers))\n"
    "axes[0].bar(x - 0.2, ann['ann_return'], width=0.4, label='annualized return')\n"
    "axes[0].bar(x + 0.2, ann['ann_vol'], width=0.4, label='annualized vol')\n"
    "axes[0].set_xticks(x, tickers, rotation=45, ha='right')\n"
    "axes[0].set_title('Return / volatility by asset')\n"
    "axes[0].legend()\n"
    "sc = axes[1].scatter(ann['ann_vol'], ann['ann_return'], c=ann['sharpe'], cmap='viridis')\n"
    "for t in tickers:\n"
    "    axes[1].annotate(t, (ann.loc[t, 'ann_vol'], ann.loc[t, 'ann_return']), fontsize=8)\n"
    "axes[1].set_xlabel('annualized volatility')\n"
    "axes[1].set_ylabel('annualized return')\n"
    "axes[1].set_title('Risk-return map (color = Sharpe)')\n"
    "fig.colorbar(sc, ax=axes[1])\n"
    "fig.tight_layout()\n"
    "fig.savefig(FIG_DIR / 'eda_risk_return.png', bbox_inches='tight')\n"
    "plt.show()"
))
cells.append(md("## 4. Correlation structure"))
cells.append(code(
    "corr = rets.corr()\n"
    "fig, ax = plt.subplots(figsize=(7.2, 6))\n"
    "im = ax.imshow(corr.values, cmap='RdBu_r', vmin=-1, vmax=1)\n"
    "ax.set_xticks(range(len(tickers)), tickers, rotation=45, ha='right')\n"
    "ax.set_yticks(range(len(tickers)), tickers)\n"
    "for i in range(len(tickers)):\n"
    "    for j in range(len(tickers)):\n"
    "        ax.text(j, i, f'{corr.values[i, j]:.2f}', ha='center', va='center', fontsize=8)\n"
    "fig.colorbar(im, ax=ax)\n"
    "ax.set_title('Daily log-return correlation')\n"
    "fig.tight_layout()\n"
    "fig.savefig(FIG_DIR / 'eda_correlation.png', bbox_inches='tight')\n"
    "plt.show()"
))
cells.append(md(
    "Equity ETFs co-move strongly (diversification benefit is limited within the block),\n"
    "while bonds (AGG, IEF) and gold provide the low-correlation sleeves the optimizer\n"
    "uses to push the efficient frontier leftward."
))
cells.append(md("## 5. Rolling volatility and drawdowns"))
cells.append(code(
    "fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))\n"
    "roll_vol = rets.rolling(63).std() * np.sqrt(252)\n"
    "for t in tickers:\n"
    "    axes[0].plot(roll_vol.index, roll_vol[t], linewidth=1.0, label=t)\n"
    "axes[0].set_title('63-day rolling annualized volatility')\n"
    "dd = cum / cum.cummax() - 1\n"
    "for t in tickers:\n"
    "    axes[1].plot(dd.index, dd[t], linewidth=1.0, label=t)\n"
    "axes[1].set_title('Drawdown from running maximum')\n"
    "axes[1].legend(ncol=4, fontsize=8, loc='lower left')\n"
    "fig.tight_layout()\n"
    "fig.savefig(FIG_DIR / 'eda_vol_drawdown.png', bbox_inches='tight')\n"
    "plt.show()"
))
cells.append(md("## 6. Takeaways for modelling"))
cells.append(md(
    "1. **Calendar alignment matters**: US and HK markets have different holidays; the\n"
    "   panel starts on the first common trading day, which the optimizer and ML feature\n"
    "   builder both rely on.\n"
    "2. **Return distributions have fat tails** (positive excess kurtosis across the\n"
    "   universe): walk-forward validation and a modest ML blend weight (alpha=0.30)\n"
    "   are used rather than trusting full-sample fits.\n"
    "3. **Bonds and gold diversify**: the correlation block structure is what makes the\n"
    "   Markowitz frontier meaningful for conservative profiles.\n"
    "4. **2022 is a stress case**: equities and bonds fell together, and every trailing\n"
    "   1-year expected return turned non-negative-negative — the backtest degrades to\n"
    "   min-volatility in that regime (documented in `BacktestService`)."
))

nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out = ROOT / "notebooks" / "01_eda.ipynb"
nbf.write(nb, out)
print("notebook written:", out)

# execute it
from nbclient import NotebookClient  # noqa: E402

nb_exec = nbf.read(out, as_version=4)
client = NotebookClient(nb_exec, timeout=600, kernel_name="python3",
                        resources={"metadata": {"path": str(ROOT)}})
client.execute()
nbf.write(nb_exec, out)
print("notebook executed OK:", out)
