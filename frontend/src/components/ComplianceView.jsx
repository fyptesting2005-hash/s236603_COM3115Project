import React, { useEffect, useState } from "react";
import { api, pct, num } from "../api.js";

export default function ComplianceView() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    Promise.all([api.audit(50), api.agentQuestions(50)])
      .then(([recs, qs]) => alive && setData({ recs, qs }))
      .catch((e) => alive && setError(String(e.message || e)));
    return () => { alive = false; };
  }, []);

  if (error) return <div className="card"><div className="error">{error}</div></div>;
  if (!data) return <div className="card loading">Loading compliance log…</div>;

  return (
    <div>
      <div className="card" data-testid="compliance">
        <h2>Recommendation audit log</h2>
        <p className="sub">
          Append-only record of every portfolio recommendation (SFC record-keeping
          expectation). {data.recs.length} entries shown (latest first).
        </p>
        {data.recs.length === 0 ? (
          <p className="sub">No recommendations yet — generate a portfolio first.</p>
        ) : (
          <table className="data">
            <thead>
              <tr><th>Time (UTC)</th><th>Profile</th><th>Weights</th>
                <th className="num">Exp. return</th><th className="num">Volatility</th><th>ML</th></tr>
            </thead>
            <tbody>
              {data.recs.map((r) => (
                <tr key={r.id}>
                  <td>{r.ts.slice(0, 19).replace("T", " ")}</td>
                  <td><span className={`badge ${r.profile}`}>{r.profile}</span></td>
                  <td style={{ maxWidth: 260 }}>
                    {Object.entries(r.weights).sort((a, b) => b[1] - a[1])
                      .map(([t, w]) => `${t} ${pct(w, 0)}`).join(", ")}
                  </td>
                  <td className="num">{pct(r.expected_return)}</td>
                  <td className="num">{pct(r.volatility)}</td>
                  <td>{r.use_ml ? "on" : "off"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>Copilot question log</h2>
        <p className="sub">Every Copilot question and its answer, with the tools it used.</p>
        {data.qs.length === 0 ? (
          <p className="sub">No Copilot questions yet.</p>
        ) : (
          <table className="data">
            <thead>
              <tr><th>Time (UTC)</th><th>Question</th><th>Answer (excerpt)</th><th>Tools</th></tr>
            </thead>
            <tbody>
              {data.qs.map((q) => (
                <tr key={q.id}>
                  <td>{q.ts.slice(0, 19).replace("T", " ")}</td>
                  <td style={{ maxWidth: 220 }}>{q.question}</td>
                  <td style={{ maxWidth: 300 }}>{q.answer.slice(0, 120)}{q.answer.length > 120 ? "…" : ""}</td>
                  <td>{q.tools.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="note">
          Record keeping is one of the four SFC expectations mapped in the report
          (chapter 7): profiling, suitability, disclosure, oversight and records.
        </div>
      </div>
    </div>
  );
}
