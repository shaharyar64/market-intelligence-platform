from pydantic import BaseModel, Field
from typing import List, Optional


# ✅ SOCIAL OVERVIEW
class SocialOverviewResponse(BaseModel):
    total_volume: int
    total_banks: int
    total_engagement: int
    total_reach: int
    avg_engagement: float


# ✅ PIE CHART
class DistributionItem(BaseModel):
    bank: Optional[str] = None
    total_posts: Optional[int] = None

    # engagement slices (present when bank filter is provided)
    likes: Optional[int] = None
    shares: Optional[int] = None
    comments: Optional[int] = None
    views: Optional[int] = None
    total_engagement: Optional[int] = None


class PostDistributionResponse(BaseModel):
    distribution: List[DistributionItem]


# ✅ LAST 6 MONTHS
class PostVolumePoint(BaseModel):
    month: str
    volume: int

class PostVolumeLast6MonthsResponse(BaseModel):
    data: List[PostVolumePoint]


# ✅ VOLUME TREND
class VolumeTrendPoint(BaseModel):
    period: str
    volume: int

class VolumeTrendResponse(BaseModel):
    trend: List[VolumeTrendPoint]


# ✅ ENGAGEMENT TREND
class EngagementTrendPoint(BaseModel):
    period: str
    engagement: int

class EngagementTrendResponse(BaseModel):
    trend: List[EngagementTrendPoint]


# ✅ BANK VOLUME GROWTH ("Fastest Growing")
class BankVolumeGrowthItem(BaseModel):
    bank: str
    growth: float = Field(
        description=(
            "Slope of monthly Share of Volume (0-100 scale) over time, in "
            "PERCENTAGE POINTS per month — not a fraction-of-1 and not a "
            "relative % change. E.g. 0.52 means share is rising ~0.52 "
            "percentage points/month; negative values indicate a declining share."
        )
    )
    current_share_of_volume: float = Field(
        description="Share of post volume (%) for the most recent month in range."
    )

class BankVolumeGrowthResponse(BaseModel):
    data: List[BankVolumeGrowthItem]


# ✅ FOLLOWERS
class BankFollowers(BaseModel):
    bank: str
    followers: Optional[int] = None

class BankFollowersResponse(BaseModel):
    followers: List[BankFollowers]


class BankPlatformFilters(BaseModel):
    banks: List[str]
    platforms: List[str]

class BankPlatformFiltersResponse(BaseModel):
    data: BankPlatformFilters



class SentimentItem(BaseModel):
    name: str
    avg_sentiment: float
    mentions: Optional[int] = None


class AvgSentimentTopicResponse(BaseModel):
    data: List[SentimentItem]


class AvgSentimentBankResponse(BaseModel):
    data: List[SentimentItem]


class TopTopicsResponse(BaseModel):
    data: List[SentimentItem]


class TopBanksResponse(BaseModel):
    data: List[SentimentItem]


class AssociationItem(BaseModel):
    association: str
    total_mentions: int

class AssociationTrendItem(BaseModel):
    association: str
    period: str
    total_mentions: int

class TopAssociationsResponse(BaseModel):
    data: List[AssociationItem]

class AssociationsDistributionResponse(BaseModel):
    data: List[AssociationItem]

class AssociationsTrendResponse(BaseModel):
    data: List[AssociationTrendItem]