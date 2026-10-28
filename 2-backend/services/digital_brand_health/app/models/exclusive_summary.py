from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


# ---------- 1. Top Digital Health Score ----------
class TopDigitalHealthItem(BaseModel):
    bank: str
    avg_score: float
    rank: Optional[int] = None
    ai_score: Optional[float] = None
    share_of_search_pct: Optional[float] = None
    rating: Optional[float] = None
    review_volume: Optional[int] = None
    social_sov_pct: Optional[float] = None
    engagement: Optional[int] = None


class TopDigitalHealthResponse(BaseModel):
    top_digital_health: List[TopDigitalHealthItem]


# ---------- 2. Digital Equity Trend Over Time ----------
class DigitalEquityTrendItem(BaseModel):
    period: str
    avg_score: float


class DigitalEquityTrendResponse(BaseModel):
    digital_equity_trend: List[DigitalEquityTrendItem]


# ---------- 3. Top 3 Banks Trend Over Time ----------
class Top3BanksTrendItem(BaseModel):
    period: str
    bank: str
    avg_score: float


class Top3BanksTrendResponse(BaseModel):
    top3_banks_trend: List[Top3BanksTrendItem]


class BrandIQSnapshotItem(TopDigitalHealthItem):
    project: Optional[str] = None
    calculated_at: Optional[datetime] = None


class BrandIQSnapshotResponse(BaseModel):
    snapshot: List[BrandIQSnapshotItem]


class BrandIQTrendItem(BaseModel):
    period: str
    bank: str
    avg_score: float
    project: Optional[str] = None
    calculated_at: Optional[datetime] = None


class BrandIQTrendResponse(BaseModel):
    trend: List[BrandIQTrendItem]
