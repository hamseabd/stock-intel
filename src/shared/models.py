"""Data models used across the platform."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SharePosition:
    ticker: str
    shares: float
    cost_basis: float
    position_type: str = "shares"

    @property
    def total_cost(self) -> float:
        return self.shares * self.cost_basis


@dataclass
class OptionPosition:
    ticker: str
    option_type: str  # "put" or "call"
    strike: float
    expiry: str  # YYYY-MM-DD
    contracts: int = 1
    cost_basis: float = 0.0
    strategy: str = ""
    status: str = "open"
    position_type: str = "option"


@dataclass
class PnLResult:
    ticker: str
    shares: float
    cost_basis: float
    current_price: float
    market_value: float
    dollar_pnl: float
    pct_pnl: float


@dataclass
class OptionAnalysis:
    ticker: str
    option_type: str
    strike: float
    expiry: str
    underlying_price: float
    dte: int
    bid: float
    ask: float
    mid: float
    iv: float
    delta: float
    gamma: float
    theta: float
    vega: float
    intrinsic: float
    extrinsic: float
    volume: int
    open_interest: int
    itm: bool
    recommendation: str
    recommendation_reason: str


@dataclass
class FlowAlert:
    ticker: str
    strike: float
    expiry: str
    option_type: str
    volume: int
    open_interest: int
    volume_oi_ratio: float
    premium: float
    direction: str  # "bullish", "bearish", "neutral"


@dataclass
class CongressTrade:
    member: str
    party: str
    chamber: str
    state: str
    ticker: str
    tx_type: str  # "Purchase", "Sale"
    amount: str  # "$1,001 - $15,000" etc.
    trade_date: str
    filing_date: str
    committees: list = field(default_factory=list)
    owner: str = "Self"
    signals: list = field(default_factory=list)


@dataclass
class DarkPoolData:
    ticker: str
    date: str
    dark_volume: int
    total_volume: int
    dark_pct: float
    short_volume: int
    short_pct: float


@dataclass
class TechnicalSignals:
    ticker: str
    price: float
    rsi_14: float
    macd_line: float
    macd_signal: float
    macd_histogram: float
    sma_50: float
    sma_200: float
    bb_upper: float
    bb_middle: float
    bb_lower: float
    avg_volume: float
    current_volume: float
    support: float
    resistance: float
    overall_signal: str  # "bullish", "bearish", "neutral"


@dataclass
class PriceAlert:
    ticker: str
    direction: str  # "above" or "below"
    target_price: float
    chat_id: str
    active: bool = True


@dataclass
class AlertConfig:
    chat_id: str
    enabled: bool = True
    muted_until: Optional[str] = None  # ISO datetime
    congress: bool = True
    flow: bool = True
    darkpool: bool = True
    technicals: bool = True
    earnings: bool = True
    price: bool = True
    risk: bool = True
    news: bool = True
