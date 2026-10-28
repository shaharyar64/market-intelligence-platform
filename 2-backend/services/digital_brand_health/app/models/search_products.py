from pydantic import BaseModel, Field
from typing import List


class TopProduct(BaseModel):
    products: str
    avg_value: float

class Top5ProductsResponse(BaseModel):
    top5_products: List[TopProduct]


class ProductDistribution(BaseModel):
    product: str
    percentage: float

class ProductDistributionResponse(BaseModel):
    distribution: List[ProductDistribution]


class ProductTimePoint(BaseModel):
    product: str
    period: str
    value: float

class Top5ProductsOverTimeResponse(BaseModel):
    data: List[ProductTimePoint]


class ProductDistributionPoint(BaseModel):
    product: str
    period: str
    percentage: float = Field(description="Share of Search (%) for this product in this period, on the same 0-100 scale as /distribution.")

class ProductDistributionOverTimeResponse(BaseModel):
    data: List[ProductDistributionPoint]


class GrowingProduct(BaseModel):
    product: str
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

class TopGrowingProductsResponse(BaseModel):
    top_growing_products: List[GrowingProduct]


class ProductTrend(BaseModel):
    product: str
    period: str
    value: float

class TopGrowingProductsOverTimeResponse(BaseModel):
    data: List[ProductTrend]
