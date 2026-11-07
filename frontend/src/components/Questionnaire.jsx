import React, { useState } from "react";
import { api, pct } from "../api.js";

const QUESTIONS = [
  { key: "age", label: "Age", min: 18, max: 75, step: 1, format: (v) => `${v} years` },
  { key: "horizon_years", label: "Investment horizon", min: 0, max: 30, step: 1, format: (v) => `${v} years` },
  { key: "loss_tolerance", label: "Loss tolerance", min: 1, max: 5, step: 1,
    format: (v) => ["Cannot accept losses", "Very low", "Moderate", "High", "Comfortable with large swings"][v - 1] },
  { key: "liquidity_needs", label: "Liquidity needs", min: 1, max: 5, step: 1,
    format: (v) => ["Locked-up capital is fine", "Low", "Some", "Regular", "May need cash any time"][v - 1] },
  { key: "experience", label: "Investment experience", min: 1, max: 5, step: 1,
    format: (v) => ["None", "Beginner", "Some", "Advanced", "Professional"][v - 1] },
];

export default function Questionnaire({ onProfiled }) {
  const [answers, setAnswers] = useState({
    age: 35, horizon_years: 15, loss_tolerance: 3, liquidity_needs: 2, experience: 3,
  });
  const [amount, setAmount] = useState(100000);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const submit = async () => {
    setLoading(true);
    setError("");
    try {
      const profile = await api.profile(answers);
      const optimization = await api.optimize({
        profile: profile.profile,
        use_ml: true,
        amount: Number(amount) || undefined,
      });
      setResult({ profile, optimization });
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  };

  if (result) {
    const { profile, optimization } = result;
    return (
      <div>
        <div className="card profile-card" data-testid="profile-result">
          <h2>Your risk profile</h2>
          <div className="score">{profile.score}</div>
          <span className={`badge ${profile.profile}`}>{profile.label}</span>
          <p className="desc">{profile.description}</p>
          <p className="desc" style={{ marginTop: 4 }}>
            Target volatility band: <b>{pct(profile.target_vol_band[0], 0)} – {pct(profile.target_vol_band[1], 0)}</b>
          </p>
        </div>
        <div style={{ textAlign: "center" }}>
          <button className="primary" onClick={() => onProfiled({ ...profile, optimization })}>
            View my portfolio →
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="card" data-testid="questionnaire">
        <h2>KYC-style risk profiling</h2>
        <p className="sub">
          Five questions mirror the client-profiling step a licensed advisor must
          complete before recommending a portfolio.
        </p>
        {QUESTIONS.map((q) => (
          <label className="field" key={q.key}>
            {q.label}
            <span className="val">{q.format(answers[q.key])}</span>
            <input
              type="range" min={q.min} max={q.max} step={q.step}
              value={answers[q.key]}
              aria-label={q.label}
              onChange={(e) =>
                setAnswers({ ...answers, [q.key]: Number(e.target.value) })
              }
            />
          </label>
        ))}
        <label className="field">
          Indicative investment amount (HKD)
          <input
            type="number" min={0} step={1000} value={amount}
            aria-label="Investment amount"
            onChange={(e) => setAmount(e.target.value)}
          />
        </label>
        {error && <div className="error">{error}</div>}
        <button className="primary" onClick={submit} disabled={loading} data-testid="submit-answers">
          {loading ? "Analysing…" : "Generate my profile"}
        </button>
      </div>
    </div>
  );
}
