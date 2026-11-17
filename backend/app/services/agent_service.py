"""AgentService: a tool-grounded Copilot for the FinSight dashboard.

The agent answers dashboard questions by CALLING the system's own analytics
tools (universe, per-asset stats, correlations, fixed-weight backtest) through
Gemini function calling. Answers must be grounded in tool output — the system
prompt forbids inventing figures, and every tool invocation is returned in a
trace so the UI (and an examiner) can verify where each number came from.

Constraints:
- max AGENT_MAX_TOOL_ROUNDS tool rounds per question, then one tool-free call
  forces a final text answer;
- key pool with failover: GEMINI_API_KEY_AGENT first, then GEMINI_API_KEY
  (429/503/5xx try the next combination);
- no key -> the endpoint reports the agent as unavailable (UI shows offline).
"""
from __future__ import annotations

import json
import time

import httpx

from .ai_service import _load_env_vars

ENDPOINT = "https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"
AGENT_MAX_TOOL_ROUNDS = 4
TIMEOUT_S = 45.0
MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
RETRY_BACKOFF_S = 2.0
DEADLINE_S = 120.0

AGENT_SYSTEM_PROMPT = (
    "You are FinSight Copilot, the assistant inside an educational Markowitz "
    "robo-advisor for a Hong Kong FinTech course. Answer the user's question about "
    "the dashboard, the asset universe, or portfolio what-if scenarios. You have "
    "tools that return REAL computed numbers from the system's own data pipeline; "
    "call them instead of guessing. Rules: (1) every number in your final answer "
    "must come from a tool result in this conversation; (2) keep answers under 150 "
    "words, plain language; (3) the system is an educational prototype, not "
    "SFC-licensed advice — add a one-line reminder when giving performance figures; "
    "(4) if the question is outside your tools' scope, say so briefly."
)

TOOLS_DECLARATION = [
    {
        "name": "get_universe",
        "description": "List the investable ETF universe (tickers and full names).",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "get_asset_stats",
        "description": (
            "Full-sample annualized return, volatility, Sharpe and max drawdown for "
            "every ticker, computed from real daily data (2016 to present)."
        ),
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "get_correlation",
        "description": "Daily-return correlation matrix across the whole universe.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "backtest_fixed_weights",
        "description": (
            "Backtest a portfolio of FIXED weights, monthly rebalanced with 10 bps "
            "costs, over the full history. Weights must be ticker->weight and sum to "
            "1. Use for what-if questions like 'what if gold were 30%'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "weights": {
                    "type": "OBJECT",
                    "description": "Map of ticker to weight between 0 and 1; the weights must sum to 1.",
                },
            },
            "required": ["weights"],
        },
    },
]

RETRYABLE = {429, 500, 503}


class AgentError(RuntimeError):
    """Raised when the agent cannot produce an answer (no key, all backends down)."""


class AgentService:
    def __init__(self, keys: list[str] | None = None,
                 models: list[str] | None = None,
                 tools: dict[str, callable] | None = None) -> None:
        env = _load_env_vars()
        agent_key = env.get("GEMINI_API_KEY_AGENT", "")
        main_key = env.get("GEMINI_API_KEY", "")
        self.keys = keys if keys is not None else [k for k in (agent_key, main_key) if k]
        self.models = models or MODELS
        self.tools = tools or {}

    # ---------- public ----------
    @property
    def available(self) -> bool:
        return bool(self.keys) and bool(self.tools)

    def chat(self, question: str, history: list[dict] | None = None) -> dict:
        """Answer one question; returns {answer, tool_trace}.

        history: optional [{"role": "user"|"assistant", "text": str}] recent turns.
        """
        if not self.available:
            raise AgentError("agent unavailable: no API key or no tools configured")

        contents: list[dict] = []
        for turn in (history or [])[-3:]:
            role = "user" if turn["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": turn["text"]}]})
        contents.append({"role": "user", "parts": [{"text": question}]})

        tool_trace: list[dict] = []
        deadline = time.monotonic() + DEADLINE_S
        for _ in range(AGENT_MAX_TOOL_ROUNDS):
            data = self._request(contents, tools=True, deadline=deadline)
            parts = data["candidates"][0]["content"].get("parts", [])
            contents.append({"role": "model", "parts": parts})

            calls = [p["functionCall"] for p in parts if "functionCall" in p]
            if not calls:
                text = "".join(p.get("text", "") for p in parts).strip()
                return {"answer": text or "(empty reply)", "tool_trace": tool_trace}

            response_parts = []
            for call in calls:
                result = self._execute_tool(call["name"], call.get("args", {}))
                tool_trace.append({"tool": call["name"], "args": call.get("args", {}),
                                   "result": result})
                response_parts.append({
                    "functionResponse": {
                        "name": call["name"],
                        "response": {"result": json.dumps(result)[:4000]},
                    }
                })
            contents.append({"role": "user", "parts": response_parts})

        # round budget exhausted -> one tool-free call forces a text answer
        data = self._request(contents, tools=False, deadline=deadline)
        parts = data["candidates"][0]["content"].get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        return {"answer": text or "(empty reply)", "tool_trace": tool_trace}

    # ---------- internals ----------
    def _execute_tool(self, name: str, args: dict) -> dict:
        fn = self.tools.get(name)
        if fn is None:
            return {"error": f"unknown tool: {name}"}
        try:
            return fn(**args)
        except Exception as exc:  # noqa: BLE001 - surfaced to the model as an error
            return {"error": f"{type(exc).__name__}: {exc}"}

    def _request(self, contents: list[dict], tools: bool,
                 deadline: float | None = None) -> dict:
        payload: dict = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": AGENT_SYSTEM_PROMPT}]},
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
        }
        if tools:
            payload["tools"] = [{"functionDeclarations": TOOLS_DECLARATION}]

        last_err = ""
        for key in self.keys:
            for model in self.models:
                if deadline is not None and time.monotonic() > deadline:
                    raise AgentError("Copilot deadline exceeded before a reply arrived")
                try:
                    resp = httpx.post(
                        ENDPOINT.format(model=model), params={"key": key},
                        json=payload, timeout=TIMEOUT_S,
                    )
                    if resp.status_code in RETRYABLE:
                        last_err = f"{model}: HTTP {resp.status_code}"
                        if deadline is not None and time.monotonic() > deadline:
                            raise AgentError(f"Copilot deadline exceeded (last: {last_err})")
                        time.sleep(RETRY_BACKOFF_S)
                        continue
                    resp.raise_for_status()
                    return resp.json()
                except httpx.HTTPStatusError as exc:
                    last_err = f"{model}: HTTP {exc.response.status_code}"
                except httpx.HTTPError as exc:
                    last_err = f"{model}: {type(exc).__name__}"
        raise AgentError(f"all Gemini backends failed (last: {last_err})")
