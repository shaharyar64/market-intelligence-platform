from pydantic import BaseModel
from typing import List, Dict, Any


class RevenueResponse(BaseModel):
    total_revenue: float
    currency: str


class KPIResponse(BaseModel):
    monthly_growth: float
    active_customers: int
    churn_rate: float


class CustomReportRequest(BaseModel):
    start_date: str
    end_date: str
    group_by: str
    filters: Dict[str, Any] | None = None
