import React, { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { api, num } from "../api.js";

export default function MarketView() {
  const [tickers, setTickers] = useState([]);
  const [ticker, setTicker] = useState("SPY");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.universe()
      .then((u) => {
        setTickers(u.tickers);
        if (u.tickers.length && !u.tickers.some((t) => t.ticker === ticker)) {
          setTicker(u.tickers[0].ticker);
        }
      })
      .catch((e) => setError(String(e.message || e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let alive = true;
    setData(null);
    api.market(ticker)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(String(e.message || e)));
    return () => { alive = false; };
  }, [ticker]);

  const chartData = data?.points.map((p) => ({ date: p.date, close: p.close }));

  return (
    <div className="card" data-testid="market">
      <h2>Market data viewer</h2>
      <p className="sub">
        Adjusted closes served from the SQLite cache (Yahoo Finance source).
      </p>
      <label className="field" style={{ maxWidth: 320 }}>
        Ticker
        <select value={ticker} onChange={(e) => setTicker(e.target.value)} aria-label="Ticker selector">
          {tickers.map((t) => (
            <option key={t.ticker} value={t.ticker}>{t.ticker} — {t.name}</option>
          ))}
        </select>
      </label>
      {error && <div className="error">{error}</div>}
      {data && chartData && (
        <>
          <div className="stat-row">
            <div className="stat"><div className="k">Last close</div>
              <div className="v">{num(data.last_close)}</div></div>
            <div className="stat"><div className="k">Points</div>
              <div className="v">{chartData.length}</div></div>
          </div>
          <div style={{ width: "100%", height: 360 }}>
            <ResponsiveContainer>
              <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 0, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#dfe6ee" />
                <XAxis dataKey="date" minTickGap={70} />
                <YAxis domain={["auto", "auto"]} />
                <Tooltip />
                <Line type="monotone" dataKey="close" name={`${data.ticker} close`}
                  stroke="#0f2a43" dot={false} strokeWidth={1.8}
                  isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}
