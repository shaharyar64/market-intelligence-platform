from pydantic import BaseModel, Field
from typing import List


class TopBank(BaseModel):
    bank: str
    avg_value: float

class Top5BanksResponse(BaseModel):
    top5_banks: List[TopBank]


class BankDistribution(BaseModel):
    bank: str
    percentage: float

class BankDistributionResponse(BaseModel):
    distribution: List[BankDistribution]


class BankTimePoint(BaseModel):
    bank: str
    period: str
    value: float

class Top5BanksOverTimeResponse(BaseModel):
    data: List[BankTimePoint]


class BankDistributionPoint(BaseModel):
    bank: str
    period: str
    percentage: float = Field(description="Share of Search (%) for this bank in this period, on the same 0-100 scale as /distribution.")

class BankDistributionOverTimeResponse(BaseModel):
    data: List[BankDistributionPoint]


class GrowingBank(BaseModel):
    bank: str
    growth: float = Field(
        description=(
            "Slope of monthly Share of Search (0-100 scale) over time, in "
            "PERCENTAGE POINTS per month — not a fraction-of-1 and not a "
            "relative % change. E.g. 0.52 means share is rising ~0.52 "
            "percentage points/month; negative values indicate a declining share."
        )
    )
    current_share_of_search: float = Field(
        description="Share of Search (%) for the most recent month in range, on the same 0-100 scale as /distribution."
    )

class TopGrowingBanksResponse(BaseModel):
    top_growing_banks: List[GrowingBank]


class BankTrend(BaseModel):
    bank: str
    period: str
    value: float

class TopGrowingBanksOverTimeResponse(BaseModel):
    data: List[BankTrend]
