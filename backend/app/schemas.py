"""Pydantic request/response models for the FinSight API."""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class RiskAnswers(BaseModel):
    """KYC-style risk profiling questionnaire."""

    age: int = Field(ge=18, le=100, description="Investor age in years")
    horizon_years: int = Field(ge=0, le=60, description="Investment horizon in years")
    loss_tolerance: int = Field(ge=1, le=5, description="1 = cannot accept any loss, 5 = comfortable with large swings")
    liquidity_needs: int = Field(ge=1, le=5, description="1 = long locked-up capital is fine, 5 = may need cash any time")
    experience: int = Field(ge=1, le=5, description="1 = no experience, 5 = experienced investor")
    amount: Optional[float] = Field(default=None, ge=0, description="Indicative investment amount (HKD)")


class OptimizeRequest(BaseModel):
    profile: str = Field(pattern="^(conservative|balanced|aggressive)$")
    use_ml: bool = Field(default=True, description="Blend ML expected-return views into the optimization")
    amount: Optional[float] = Field(default=None, ge=0, description="Indicative investment amount (HKD)")


class BacktestRequest(BaseModel):
    strategy: str = Field(pattern="^(max_sharpe|max_sharpe_ml|min_vol)$")
    use_ml: bool = Field(default=True)


class FrontierPoint(BaseModel):
    volatility: float
    ret: float
    sharpe: float
    weights: Dict[str, float]


class OptimizeResponse(BaseModel):
    profile: str
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe: float
    target_vol_band: List[float]
    method: str
    amount_allocations: Optional[Dict[str, float]] = None
    suitability_note: str = ""


class EquityCurve(BaseModel):
    name: str
    dates: List[str]
    values: List[float]


class BacktestMetrics(BaseModel):
    name: str
    cagr: float
    volatility: float
    sharpe: float
    max_drawdown: float


class BacktestResponse(BaseModel):
    strategy: str
    metrics: List[BacktestMetrics]
    curves: List[EquityCurve]


class AssetStats(BaseModel):
    ticker: str
    name: str
    ann_return: float
    ann_vol: float
    sharpe: float
    max_drawdown: float
    missing_days: int


class EdaResponse(BaseModel):
    rows: int
    start: str
    end: str
    tickers: List[str]
    assets: List[AssetStats]
    correlation: Dict[str, Dict[str, float]]


class MarketPoint(BaseModel):
    date: str
    close: float


class MarketResponse(BaseModel):
    ticker: str
    name: str
    points: List[MarketPoint]
    last_close: float


class AuditEntry(BaseModel):
    id: int
    ts: str
    profile: str
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    use_ml: bool


class ExplainRequest(BaseModel):
    profile: str = Field(pattern="^(conservative|balanced|aggressive)$")
    weights: Dict[str, float]
    expected_return: float = Field(ge=-1.0, le=2.0)
    volatility: float = Field(ge=0.0, le=2.0)
    sharpe: float = Field(ge=-10.0, le=10.0)


class AgentTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    text: str = Field(min_length=1, max_length=2000)


class AgentChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: List[AgentTurn] = Field(default_factory=list, max_length=6)


class ExplainResponse(BaseModel):
    summary: str
    highlights: List[str]
    risk_note: str
    source: str
    cached: bool = False


class ProfileResponse(BaseModel):
    score: float
    profile: str
    label: str
    description: str
    target_vol_band: List[float]
    suitability_note: str
