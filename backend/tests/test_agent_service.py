"""AgentService tests (hermetic: Gemini function-calling HTTP is mocked)."""
import pytest

from app.services.agent_service import AGENT_MAX_TOOL_ROUNDS, AgentError, AgentService

FAKE_TOOLS = {
    "get_universe": lambda: {"tickers": ["SPY", "GLD"]},
    "backtest_fixed_weights": lambda weights: (
        (_ for _ in ()).throw(ValueError("weights must sum to 1"))
        if abs(sum(weights.values()) - 1.0) > 1e-6
        else {"weights": weights, "final_growth_multiple": 2.5,
              "metrics": [{"name": "fixed_weights", "cagr": 0.08, "sharpe": 0.7}]}
    ),
}


def _svc(keys=None, tools=None):
    return AgentService(keys=keys if keys is not None else ["k1"],
                        models=["test-model"], tools=tools if tools is not None else FAKE_TOOLS)


def _httpx_spy(responses):
    """Fake httpx.post popping scripted replies; snapshots contents[-1] per call
    (the service keeps appending to the same contents list, so a live reference
    would be mutated by later turns)."""
    import copy
    calls = []

    def fake_post(url, params=None, json=None, timeout=None):
        calls.append({
            "url": url, "key": params["key"], "payload": json,
            "last_content": copy.deepcopy(json["contents"][-1]),
            "contents_len": len(json["contents"]),
            "first_content": copy.deepcopy(json["contents"][0]),
        })
        scripted = responses.pop(0)

        class Resp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return scripted
        return Resp()

    return fake_post, calls


def _reply_text(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def _reply_call(name, args):
    return {"candidates": [{"content": {"parts": [{"functionCall": {"name": name, "args": args}}]}}]}


def test_unavailable_without_keys():
    svc = _svc(keys=[])
    assert svc.available is False
    with pytest.raises(AgentError):
        svc.chat("hello")


def test_unavailable_without_tools():
    svc = _svc(tools={})
    assert svc.available is False


def test_direct_answer_without_tools(monkeypatch):
    fake_post, calls = _httpx_spy([_reply_text("42")])
    import app.services.agent_service as mod
    monkeypatch.setattr(mod.httpx, "post", fake_post)
    out = _svc().chat("What is the universe?")
    assert out["answer"] == "42"
    assert out["tool_trace"] == []
    assert len(calls) == 1


def test_tool_loop_executes_and_traces(monkeypatch):
    scripted = [
        _reply_call("backtest_fixed_weights", {"weights": {"GLD": 0.3, "SPY": 0.7}}),
        _reply_text("With 30% gold the portfolio grows 2.5x, Sharpe 0.7."),
    ]
    fake_post, calls = _httpx_spy(scripted)
    import app.services.agent_service as mod
    monkeypatch.setattr(mod.httpx, "post", fake_post)

    out = _svc().chat("What if gold were 30%?")

    assert "2.5x" in out["answer"]
    assert len(out["tool_trace"]) == 1
    assert out["tool_trace"][0]["tool"] == "backtest_fixed_weights"
    assert out["tool_trace"][0]["result"]["final_growth_multiple"] == 2.5
    # two model calls: tool round + final answer
    assert len(calls) == 2
    # the second call carries the functionResponse continuation
    second_parts = calls[1]["last_content"]["parts"]
    assert "functionResponse" in second_parts[0]


def test_tool_error_is_surfaced_to_model(monkeypatch):
    scripted = [
        _reply_call("backtest_fixed_weights", {"weights": {"GLD": 0.5, "SPY": 0.2}}),  # sums to 0.7
        _reply_text("The weights must sum to 1."),
    ]
    fake_post, calls = _httpx_spy(scripted)
    import app.services.agent_service as mod
    monkeypatch.setattr(mod.httpx, "post", fake_post)

    out = _svc().chat("what if 50/20?")
    trace = out["tool_trace"][0]
    assert "error" in trace["result"]  # tool exception captured, loop continued
    assert "sum to 1" in trace["result"]["error"]
    assert len(calls) == 2


def test_unknown_tool_is_reported(monkeypatch):
    scripted = [
        _reply_call("buy_everything", {}),
        _reply_text("I cannot do that."),
    ]
    fake_post, _ = _httpx_spy(scripted)
    import app.services.agent_service as mod
    monkeypatch.setattr(mod.httpx, "post", fake_post)
    out = _svc().chat("buy")
    assert out["tool_trace"][0]["result"].get("error", "").startswith("unknown tool")


def test_round_budget_forces_final_answer(monkeypatch):
    # every reply is another tool call -> after AGENT_MAX_TOOL_ROUNDS a tool-free
    # final call must produce text
    endless_call = _reply_call("get_universe", {})
    scripted = [endless_call] * AGENT_MAX_TOOL_ROUNDS + [_reply_text("final answer")]
    fake_post, calls = _httpx_spy(scripted)
    import app.services.agent_service as mod
    monkeypatch.setattr(mod.httpx, "post", fake_post)

    out = _svc().chat("loop")
    assert out["answer"] == "final answer"
    assert len(calls) == AGENT_MAX_TOOL_ROUNDS + 1
    # the forcing call has no tools attached
    assert "tools" not in calls[-1]["payload"]


def test_key_failover_on_retryable_status(monkeypatch):
    keys_seen = []

    def fake_post(url, params=None, json=None, timeout=None):
        keys_seen.append(params["key"])
        if len(keys_seen) == 1:
            class BadResp:
                status_code = 503
                def raise_for_status(self):
                    import httpx
                    raise httpx.HTTPStatusError("503", request=None, response=None)
            return BadResp()
        return type("R", (), {"status_code": 200, "raise_for_status": lambda s: None,
                              "json": lambda s: _reply_text("ok")})()

    import app.services.agent_service as mod
    monkeypatch.setattr(mod.httpx, "post", fake_post)
    svc = AgentService(keys=["keyA", "keyB"], models=["m1"], tools=FAKE_TOOLS)
    out = svc.chat("hi")
    assert keys_seen == ["keyA", "keyB"]
    assert out["answer"] == "ok"


def test_history_is_included_and_trimmed(monkeypatch):
    fake_post, calls = _httpx_spy([_reply_text("ok")])
    import app.services.agent_service as mod
    monkeypatch.setattr(mod.httpx, "post", fake_post)
    history = [{"role": "user", "text": f"q{i}"} for i in range(6)]  # > 3, should trim
    _svc().chat("now", history=history)
    # at request time: 3 kept history turns + 1 question
    assert calls[0]["contents_len"] == 4
    assert calls[0]["first_content"]["parts"][0]["text"] == "q3"
