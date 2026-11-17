import React, { useMemo, useState } from "react";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { api, pct, num } from "../api.js";
import FrontierChart from "./FrontierChart.jsx";
import BacktestView from "./BacktestView.jsx";
import EdaView from "./EdaView.jsx";
import MarketView from "./MarketView.jsx";
import ComplianceView from "./ComplianceView.jsx";

const PIE_COLORS = ["#0f2a43", "#d4875a", "#0fa3a3", "#5b8db8", "#a05a20",
  "#7ba68a", "#b3402a", "#9687a8"];

function PortfolioTab({ profile }) {
  const optimization = profile.optimization;
  const weights = optimization.weights;
  const pieData = useMemo(
    () => Object.entries(weights).map(([name, value]) => ({ name, value })),
    [weights]
  );
  const isWarning = optimization.suitability_note.startsWith("Warning");
  const names = optimization.amount_allocations;
  const [aiState, setAiState] = useState({ loading: false, error: "", data: null });

  const explain = async () => {
    setAiState({ loading: true, error: "", data: null });
    try {
      const data = await api.explain({
        profile: optimization.profile,
        weights,
        expected_return: optimization.expected_return,
        volatility: optimization.volatility,
        sharpe: optimization.sharpe,
      });
      setAiState({ loading: false, error: "", data });
    } catch (e) {
      setAiState({ loading: false, error: String(e.message || e), data: null });
    }
  };

  return (
    <div>
      <div className="card" data-testid="portfolio">
        <h2>
          Recommended portfolio <span className={`badge ${optimization.profile}`}>{profile.label}</span>
        </h2>
        <p className="sub">
          Markowitz efficient portfolio matched to your volatility band, with
          Random Forest expected-return views blended in (alpha = 0.30).
        </p>
        <div className="grid-2">
          <div style={{ width: "100%", height: 300 }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name"
                  innerRadius={60} outerRadius={100} paddingAngle={2}
                  isAnimationActive={false}>
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => pct(v)} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div>
            <div className="stat-row">
              <div className="stat"><div className="k">Expected return (ann.)</div>
                <div className="v" data-testid="exp-return">{pct(optimization.expected_return)}</div></div>
              <div className="stat"><div className="k">Volatility (ann.)</div>
                <div className="v">{pct(optimization.volatility)}</div></div>
            </div>
            <div className="stat-row">
              <div className="stat"><div className="k">Sharpe ratio</div>
                <div className="v">{num(optimization.sharpe)}</div></div>
              <div className="stat"><div className="k">Target band</div>
                <div className="v">{pct(optimization.target_vol_band[0], 0)}–{pct(optimization.target_vol_band[1], 0)}</div></div>
            </div>
            <table className="data">
              <thead><tr><th>Asset</th><th className="num">Weight</th>
                {names && <th className="num">Amount (HKD)</th>}</tr></thead>
              <tbody>
                {Object.entries(weights).sort((a, b) => b[1] - a[1]).map(([t, w]) => (
                  <tr key={t}>
                    <td>{t}</td>
                    <td className="num">{pct(w)}</td>
                    {names && <td className="num">{names[t]?.toLocaleString?.() ?? names[t]}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className={`note ${isWarning ? "warning-note" : ""}`}>{optimization.suitability_note}</div>

        <div style={{ marginTop: 16 }}>
          <button className="primary" onClick={explain} disabled={aiState.loading} data-testid="explain-btn">
            {aiState.loading ? "Thinking…" : "✨ Explain this portfolio (AI)"}
          </button>
          {aiState.error && <div className="error" style={{ marginTop: 10 }}>{aiState.error}</div>}
          {aiState.data && (
            <div className="card" style={{ marginTop: 12, background: "#f8fafc" }} data-testid="ai-explanation">
              <h3 style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                AI commentary
                <span className="badge" style={{
                  background: aiState.data.source === "gemini" ? "#e3f2f0" : "#f0ede5",
                  color: aiState.data.source === "gemini" ? "#0b6b62" : "#7a6a4a",
                  fontSize: 11,
                }}>
                  {aiState.data.source === "gemini" ? "Gemini" : "offline fallback"}
                  {aiState.data.cached ? " · cached" : ""}
                </span>
              </h3>
              <p style={{ fontSize: 14, lineHeight: 1.55, color: "#1c2a3a", margin: "0 0 10px" }}>
                {aiState.data.summary}
              </p>
              <ul style={{ margin: "0 0 10px", paddingLeft: 20 }}>
                {aiState.data.highlights.map((h, i) => (
                  <li key={i} style={{ fontSize: 13.5, color: "#3a4a5a", marginBottom: 5 }}>{h}</li>
                ))}
              </ul>
              <p style={{ fontSize: 13, color: "#7a4a1e", margin: 0 }}>
                <b>Risk:</b> {aiState.data.risk_note}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Dashboard({ profile, onRestart }) {
  const [tab, setTab] = useState("portfolio");
  const tabs = [
    ["portfolio", "Portfolio"],
    ["frontier", "Efficient Frontier"],
    ["backtest", "Backtest"],
    ["eda", "Data Explorer (EDA)"],
    ["market", "Market Data"],
    ["compliance", "Compliance Log"],
  ];

  return (
    <div>
      <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ marginBottom: 2 }}>
            Dashboard — <span className={`badge ${profile.profile}`}>{profile.label}</span>
          </h2>
          <span className="sub" style={{ margin: 0 }}>
            Risk score {profile.score} · target volatility {pct(profile.target_vol_band[0], 0)}–{pct(profile.target_vol_band[1], 0)}
          </span>
        </div>
        <button className="primary" onClick={onRestart}>Restart questionnaire</button>
      </div>

      <div className="tabs" role="tablist">
        {tabs.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id}
            className={tab === id ? "active" : ""}
            onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </div>

      {tab === "portfolio" && <PortfolioTab profile={profile} />}
      {tab === "frontier" && <FrontierChart profile={profile} />}
      {tab === "backtest" && <BacktestView />}
      {tab === "eda" && <EdaView />}
      {tab === "market" && <MarketView />}
      {tab === "compliance" && <ComplianceView />}
    </div>
  );
}
