"""AIService: Gemini-powered plain-language portfolio commentary.

Design constraints:
- Grounding only: the prompt carries the portfolio's REAL computed numbers; the
  model explains them, it never invents performance figures.
- Model fallback chain over the v1 REST endpoint (v1beta is region-blocked for
  some deployments); any failure degrades to a deterministic rule-based text so
  the live demo never depends on the network or the key.
- Responses are cached per portfolio signature to conserve quota.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import httpx

from ..config import APP_DIR

ENDPOINT = "https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"
MODEL_CHAIN = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemma-4-31b-it"]
TIMEOUT_S = 30.0

SYSTEM_PROMPT = (
    "You are the explanation layer of FinSight, an educational Markowitz robo-advisor "
    "prototype for a Hong Kong FinTech course. You receive the REAL computed metrics of a "
    "recommended ETF portfolio. Explain in plain language why this allocation follows from "
    "modern portfolio theory and the client's risk profile. You MUST NOT invent numbers that "
    "are not provided; you may restate and interpret the given ones. Keep a professional, "
    "neutral tone. Reply with ONLY a JSON object of shape: "
    '{"summary": "2-3 sentences", "highlights": ["short point", "short point", "short point"], '
    '"risk_note": "1-2 sentences on the main risk"}'
)


def _load_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    env_file = APP_DIR.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


class AIService:
    def __init__(self, api_key: str | None = None, models: list[str] | None = None) -> None:
        self.api_key = api_key if api_key is not None else _load_api_key()
        self.models = models or MODEL_CHAIN
        self._cache: dict[str, dict] = {}

    # ---------- public ----------
    def explain_portfolio(self, *, profile_label: str, weights: dict[str, float],
                          expected_return: float, volatility: float, sharpe: float,
                          benchmark_sharpe: float = 0.31) -> dict:
        """Return {summary, highlights, risk_note, source} for a computed portfolio."""
        signature = hashlib.sha256(
            json.dumps([profile_label, weights, expected_return, volatility, sharpe],
                       sort_keys=True).encode()
        ).hexdigest()[:16]
        if signature in self._cache:
            return {**self._cache[signature], "cached": True}

        prompt = (
            f"Client risk profile: {profile_label}. The optimizer recommends this portfolio: "
            f"{json.dumps(weights)}. Computed annualized metrics: expected return "
            f"{expected_return:.1%}, volatility {volatility:.1%}, Sharpe {sharpe:.2f} "
            f"(the client's home-market benchmark 2800.HK has a full-sample Sharpe of "
            f"about {benchmark_sharpe:.2f}). Explain the allocation logic and its main risk."
        )
        result = self._generate(prompt)
        if result is None:
            result = self._fallback(profile_label, weights, expected_return, volatility, sharpe)
            result["source"] = "rule-based fallback"
        else:
            result["source"] = "gemini"
        result.setdefault("summary", "")
        result.setdefault("highlights", [])
        result.setdefault("risk_note", "")
        if len(self._cache) > 32:
            self._cache.clear()
        self._cache[signature] = result
        return {**result, "cached": False}

    # ---------- internals ----------
    def _generate(self, prompt: str) -> dict | None:
        if not self.api_key:
            return None
        for model in self.models:
            try:
                text = self._call_model(model, prompt)
                parsed = _parse_json_object(text)
                if parsed and isinstance(parsed.get("summary"), str):
                    return parsed
            except Exception:  # noqa: BLE001 - try the next model, then fall back
                continue
        return None

    def _call_model(self, model: str, prompt: str) -> str:
        url = ENDPOINT.format(model=model)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1024},
        }
        resp = httpx.post(url, params={"key": self.api_key}, json=payload, timeout=TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    @staticmethod
    def _fallback(profile_label: str, weights: dict[str, float],
                  expected_return: float, volatility: float, sharpe: float) -> dict:
        top = sorted(weights.items(), key=lambda kv: -kv[1])[:3]
        names = ", ".join(f"{t} ({w:.0%})" for t, w in top)
        return {
            "summary": (
                f"This {profile_label.lower()} portfolio concentrates {names}. The optimizer "
                f"selected the efficient portfolio whose volatility best matches the profile's "
                f"target band while maximizing expected risk-adjusted return."
            ),
            "highlights": [
                f"Expected return {expected_return:.1%} at {volatility:.1%} annualized volatility (Sharpe {sharpe:.2f}).",
                "Long-only weights chosen on the Markowitz efficient frontier from real 2016-2026 data.",
                "Low-correlation sleeves (bonds/gold vs equities) are what keep the volatility inside the target band.",
            ],
            "risk_note": (
                "Mean-variance estimates are sensitive to the estimation window; in regime "
                "shifts (e.g. 2022) realized volatility can exceed the target band."
            ),
        }


def _parse_json_object(text: str) -> dict | None:
    """Extract the first JSON object from a model reply (tolerates code fences)."""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text).strip().strip("`")
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None
