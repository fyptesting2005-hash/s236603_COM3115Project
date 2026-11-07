import React, { useEffect, useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { api, pct, num } from "../api.js";

const STRATEGIES = [
  ["max_sharpe", "Max Sharpe (historical μ)"],
  ["max_sharpe_ml", "Max Sharpe + ML views"],
  ["min_vol", "Minimum volatility"],
];
const LINE_COLORS = ["#d4875a", "#0f2a43", "#0fa3a3"];

export default function BacktestView() {
  const [strategy, setStrategy] = useState("max_sharpe");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    api.backtest({ strategy, use_ml: strategy === "max_sharpe_ml" })
      .then((r) => alive && setResult(r))
      .catch((e) => alive && setError(String(e.message || e)))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [strategy]);

  // Recharts treats "." in a dataKey as a nested-path separator, so curves are
  // mapped to safe keys (k0, k1, …) with display names kept separate.
  const { chartData, series } = useMemo(() => {
    if (!result) return { chartData: null, series: [] };
    const byDate = {};
    const safeSeries = result.curves.map((c, i) => ({
      key: `k${i}`, name: c.name, color: LINE_COLORS[i % LINE_COLORS.length],
    }));
    result.curves.forEach((c, i) => {
      c.dates.forEach((d, j) => {
        byDate[d] = byDate[d] || { date: d };
        byDate[d][`k${i}`] = c.values[j];
      });
    });
    return {
      chartData: Object.keys(byDate).sort().map((d) => byDate[d]),
      series: safeSeries,
    };
  }, [result]);

  return (
    <div className="card" data-testid="backtest">
      <h2>Backtest — monthly rebalancing, 10 bps cost</h2>
      <p className="sub">
        Rolling 1-year estimation window; the ML strategy blends Random Forest views into
        expected returns. Benchmarks are buy-and-hold 2800.HK and SPY.
      </p>
      <div className="tabs">
        {STRATEGIES.map(([id, label]) => (
          <button key={id} className={strategy === id ? "active" : ""} onClick={() => setStrategy(id)}>
            {label}
          </button>
        ))}
      </div>
      {error && <div className="error">{error}</div>}
      {loading && <div className="loading">Running backtest…</div>}
      {result && chartData && (
        <>
          <div style={{ width: "100%", height: 360 }}>
            <ResponsiveContainer>
              <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 0, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#dfe6ee" />
                <XAxis dataKey="date" minTickGap={70} />
                <YAxis tickFormatter={(v) => `${v.toFixed(1)}x`} />
                <Tooltip formatter={(v) => `${Number(v).toFixed(3)}x`} />
                <Legend />
                {series.map((s) => (
                  <Line key={s.key} type="monotone" dataKey={s.key} name={s.name}
                    stroke={s.color} dot={false} strokeWidth={2} connectNulls
                    isAnimationActive={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <table className="data" style={{ marginTop: 14 }}>
            <thead>
              <tr><th>Series</th><th className="num">CAGR</th><th className="num">Volatility</th>
                <th className="num">Sharpe</th><th className="num">Max drawdown</th></tr>
            </thead>
            <tbody>
              {result.metrics.map((m) => (
                <tr key={m.name}>
                  <td>{m.name}</td>
                  <td className="num">{pct(m.cagr)}</td>
                  <td className="num">{pct(m.volatility)}</td>
                  <td className="num">{num(m.sharpe)}</td>
                  <td className="num">{pct(m.max_drawdown)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="note">
            Past performance does not predict future returns. Educational prototype only.
          </div>
        </>
      )}
    </div>
  );
}
