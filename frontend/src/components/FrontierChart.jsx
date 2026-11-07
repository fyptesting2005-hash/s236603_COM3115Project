import React, { useEffect, useState } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceDot, Legend,
} from "recharts";
import { api, pct } from "../api.js";

const PROFILE_COLORS = { conservative: "#0fa3a3", balanced: "#d4875a", aggressive: "#b3402a" };

export default function FrontierChart({ profile }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.frontier()
      .then(setData)
      .catch((e) => setError(String(e.message || e)));
  }, []);

  if (error) return <div className="card"><div className="error">{error}</div></div>;
  if (!data) return <div className="card loading">Loading efficient frontier…</div>;

  const points = data.points.map((p) => ({ vol: p.volatility, ret: p.ret, sharpe: p.sharpe }));
  const positions = Object.entries(data.profile_positions).map(([name, p]) => ({
    name, vol: p.volatility, ret: p.ret,
  }));
  const current = data.profile_positions[profile.profile];

  return (
    <div className="card" data-testid="frontier">
      <h2>Markowitz efficient frontier</h2>
      <p className="sub">
        Long-only portfolios across the 8-asset ETF universe. Orange star = your
        recommended portfolio's risk-return position.
      </p>
      <div style={{ width: "100%", height: 420 }}>
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 10, right: 30, bottom: 30, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dfe6ee" />
            <XAxis type="number" dataKey="vol" name="volatility"
              tickFormatter={(v) => pct(v, 0)}
              label={{ value: "Annualized volatility", position: "insideBottom", offset: -18 }} />
            <YAxis type="number" dataKey="ret" name="return" tickFormatter={(v) => pct(v, 0)}
              label={{ value: "Annualized return", angle: -90, position: "insideLeft", offset: 10 }} />
            <ZAxis range={[60, 60]} />
            <Tooltip formatter={(v) => pct(v)} />
            <Scatter name="Efficient frontier" data={points} fill="#0f2a43" fillOpacity={0.55} />
            {positions.map((pos) => (
              <ReferenceDot key={pos.name} x={pos.vol} y={pos.ret} r={7}
                fill={PROFILE_COLORS[pos.name] || "#888"} stroke="#fff" strokeWidth={1.5}
                legendType="circle" name={pos.name} />
            ))}
            {current && (
              <ReferenceDot x={current.vol} y={current.ret} r={11}
                fill="#d4875a" stroke="#0f2a43" strokeWidth={2} isFront />
            )}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="legend-list">
        {positions.map((pos) => (
          <span key={pos.name}>
            <span className="legend-dot" style={{ background: PROFILE_COLORS[pos.name] }} />
            {pos.name} ({pct(pos.vol)} vol / {pct(pos.ret)} ret)
          </span>
        ))}
      </div>
    </div>
  );
}
