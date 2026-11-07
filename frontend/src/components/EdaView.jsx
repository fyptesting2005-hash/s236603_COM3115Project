import React, { useEffect, useState } from "react";
import { api, pct, num } from "../api.js";

function corrColor(v) {
  if (v >= 0) return `rgba(212, 135, 90, ${0.15 + 0.75 * v})`;
  return `rgba(15, 163, 163, ${0.15 + 0.75 * Math.abs(v)})`;
}

export default function EdaView() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.eda().then(setData).catch((e) => setError(String(e.message || e)));
  }, []);

  if (error) return <div className="card"><div className="error">{error}</div></div>;
  if (!data) return <div className="card loading">Loading EDA summary…</div>;

  const tickers = data.tickers;

  return (
    <div>
      <div className="card" data-testid="eda">
        <h2>Dataset summary (EDA)</h2>
        <p className="sub">
          {data.rows} trading days, {data.start} → {data.end}, cleaned panel shared by the
          optimizer and ML pipeline. Full analysis: <code>backend/notebooks/01_eda.ipynb</code>.
        </p>
        <table className="data">
          <thead>
            <tr><th>Asset</th><th>Name</th><th className="num">Ann. return</th>
              <th className="num">Ann. vol</th><th className="num">Sharpe</th>
              <th className="num">Max DD</th><th className="num">Missing</th></tr>
          </thead>
          <tbody>
            {data.assets.map((a) => (
              <tr key={a.ticker}>
                <td><b>{a.ticker}</b></td>
                <td>{a.name}</td>
                <td className="num">{pct(a.ann_return)}</td>
                <td className="num">{pct(a.ann_vol)}</td>
                <td className="num">{num(a.sharpe)}</td>
                <td className="num">{pct(a.max_drawdown)}</td>
                <td className="num">{a.missing_days}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Return correlation matrix</h3>
        <div style={{ overflowX: "auto" }}>
          <table className="data" style={{ minWidth: 560 }}>
            <thead>
              <tr><th></th>{tickers.map((t) => <th key={t} className="num">{t}</th>)}</tr>
            </thead>
            <tbody>
              {tickers.map((a) => (
                <tr key={a}>
                  <td><b>{a}</b></td>
                  {tickers.map((b) => {
                    const v = data.correlation[a][b];
                    return (
                      <td key={b} className="correlation-cell num"
                        style={{ background: corrColor(v), color: Math.abs(v) > 0.6 ? "#fff" : "#1c2a3a" }}>
                        {v.toFixed(2)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="note">
          Equity ETFs co-move strongly; bonds (AGG/IEF) and gold (GLD) provide the
          diversification sleeves the optimizer uses to shift the frontier left.
        </div>
      </div>
    </div>
  );
}
