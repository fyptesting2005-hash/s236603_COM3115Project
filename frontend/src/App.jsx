import React, { useState } from "react";
import Questionnaire from "./components/Questionnaire.jsx";
import Dashboard from "./components/Dashboard.jsx";

export default function App() {
  const [profile, setProfile] = useState(null); // {score, profile, label, ...}

  return (
    <div>
      <header className="app-header">
        <h1>FinSight</h1>
        <span className="tag">AI-Powered Portfolio Advisor · COM3115 Educational Prototype</span>
      </header>
      <div className="compliance-banner">
        Educational prototype — not licensed by the SFC, does not provide regulated
        investment advice, and does not accept client funds.
      </div>
      <main className="main">
        {!profile ? (
          <Questionnaire onProfiled={setProfile} />
        ) : (
          <Dashboard profile={profile} onRestart={() => setProfile(null)} />
        )}
        <p className="footer-note">
          FinSight · COM3115 Financial Technology Final Project · Track 2 (AI &amp; ML in
          FinTech) · Markowitz Efficient Frontier + Random Forest expected-return views
        </p>
      </main>
    </div>
  );
}
