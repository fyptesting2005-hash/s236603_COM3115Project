/* Thin fetch wrappers around the FinSight API. */

async function request(path, options = {}) {
  const resp = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail || detail;
    } catch {
      /* keep statusText */
    }
    throw new Error(detail);
  }
  return resp.json();
}

export const api = {
  health: () => request("/api/health"),
  universe: () => request("/api/universe"),
  profile: (answers) => request("/api/profile", { method: "POST", body: JSON.stringify(answers) }),
  optimize: (req) => request("/api/optimize", { method: "POST", body: JSON.stringify(req) }),
  frontier: () => request("/api/frontier"),
  backtest: (req) => request("/api/backtest", { method: "POST", body: JSON.stringify(req) }),
  eda: () => request("/api/eda"),
  market: (ticker) => request(`/api/market/${encodeURIComponent(ticker)}`),
  walkforward: () => request("/api/ml/walkforward"),
  audit: () => request("/api/audit"),
  explain: (req) => request("/api/explain", { method: "POST", body: JSON.stringify(req) }),
  agentChat: (req) => request("/api/agent/chat", { method: "POST", body: JSON.stringify(req) }),
};

export const pct = (x, digits = 1) =>
  x === null || x === undefined ? "—" : `${(x * 100).toFixed(digits)}%`;
export const num = (x, digits = 2) =>
  x === null || x === undefined ? "—" : Number(x).toFixed(digits);
