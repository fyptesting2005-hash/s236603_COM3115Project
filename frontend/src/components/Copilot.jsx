import React, { useRef, useState } from "react";
import { api } from "../api.js";

const SUGGESTIONS = [
  "What if gold (GLD) were 30% of my portfolio with the rest in SPY?",
  "Which two assets are the least correlated?",
  "How has 2800.HK performed compared with SPY?",
];

export default function Copilot() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]); // {role, text, tools?}
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [offline, setOffline] = useState(false);
  const listRef = useRef(null);

  const scrollDown = () => {
    requestAnimationFrame(() => {
      const el = listRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    });
  };

  const send = async (text) => {
    const question = (text ?? input).trim();
    if (!question || loading) return;
    setInput("");
    const history = messages.slice(-3).map((m) => ({ role: m.role, text: m.text }));
    setMessages((m) => [...m, { role: "user", text: question }]);
    setLoading(true);
    scrollDown();
    try {
      const resp = await api.agentChat({ question, history });
      setMessages((m) => [...m, { role: "assistant", text: resp.answer, tools: resp.tools_used }]);
      setOffline(false);
    } catch (e) {
      const msg = String(e.message || e);
      setMessages((m) => [...m, {
        role: "assistant",
        text: msg.includes("unavailable") || msg.includes("503")
          ? "Copilot is offline (no Gemini key configured). Every other FinSight feature still works."
          : `Sorry, the Copilot failed: ${msg}`,
      }]);
      if (msg.includes("unavailable") || msg.includes("503")) setOffline(true);
    } finally {
      setLoading(false);
      scrollDown();
    }
  };

  return (
    <div className="copilot-root" data-testid="copilot">
      {open && (
        <div className="copilot-drawer">
          <div className="copilot-header">
            <span>FinSight Copilot</span>
            <span className="copilot-sub">tool-grounded · answers cite real pipeline data</span>
            <button className="copilot-close" onClick={() => setOpen(false)} aria-label="Close Copilot">×</button>
          </div>

          <div className="copilot-list" ref={listRef}>
            {messages.length === 0 && (
              <div className="copilot-welcome">
                <p>Ask about the data behind your dashboard. I answer by calling FinSight's own analytics tools — every number is real.</p>
                <div className="copilot-suggest">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} onClick={() => send(s)}>{s}</button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`copilot-msg ${m.role}`}>
                <div className="copilot-bubble">{m.text}</div>
                {m.tools && m.tools.length > 0 && (
                  <div className="copilot-tools">
                    {m.tools.map((t) => <span className="chip" key={t}>{t}</span>)}
                  </div>
                )}
              </div>
            ))}
            {loading && <div className="copilot-msg assistant"><div className="copilot-bubble typing">Calling tools…</div></div>}
          </div>

          <div className="copilot-input">
            <input
              value={input}
              placeholder={offline ? "Copilot offline — no Gemini key" : "Ask about assets, correlations, what-if backtests…"}
              disabled={loading || offline}
              aria-label="Copilot question"
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") send(); }}
            />
            <button className="copilot-send" onClick={() => send()} disabled={loading || offline || !input.trim()}>Send</button>
          </div>
        </div>
      )}
      <button
        className={`copilot-fab ${offline ? "offline" : ""}`}
        onClick={() => setOpen((v) => !v)}
        aria-label="Toggle FinSight Copilot"
        title="FinSight Copilot"
      >
        {open ? "×" : "✦"}
      </button>
    </div>
  );
}
