from services.digital_brand_health.app.utils.database import db
import polars as pl


data = {
    "views": {
        "With": 678528.217391,
        "Without": 89049.835443,
        "Difference": 589478.381948,
        "Difference %": 661.964594
    },
    "likes": {
        "With": 136.428571,
        "Without": 37.427102,
        "Difference": 99.001469,
        "Difference %": 264.518125
    },
    "comments": {
        "With": 5.178571,
        "Without": 3.875983,
        "Difference": 1.302588,
        "Difference %": 33.606658
    },
    "reach": {
        "With": 678528.217391,
        "Without": 89049.835443,
        "Difference": 589478.381948,
        "Difference %": 661.964594
    },
    "engagement": {
        "With": 141.607143,
        "Without": 41.303085,
        "Difference": 100.304058,
        "Difference %": 242.848826
    }
}


async def fetch_sponsership():
    result = data
    return result
