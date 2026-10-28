from pydantic import BaseModel
from typing import List


class ReviewsPerBankItem(BaseModel):
    bank: str
    ratings: int


class TopRatedBanksItem(BaseModel):
    bank: str
    avg_rating: float


class RatedBanksItem(BaseModel):
    bank: str
    total_ratings: int


class RatedBanksResponse(BaseModel):
    items: List[RatedBanksItem]


class AvgSentimentByBankItem(BaseModel):
    bank: str
    avg_sentiment: float
    rating_1: int
    rating_2: int
    rating_3: int
    rating_4: int
    rating_5: int


class ReviewTopicsDistributionItem(BaseModel):
    topic: str
    review_count: int


class AvgRatingByTopicItem(BaseModel):
    topic: str
    avg_rating: float
    review_count: int