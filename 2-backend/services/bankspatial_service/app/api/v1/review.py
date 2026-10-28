from fastapi import APIRouter
from services.bankspatial_service.app.services.review import (
    get_sentiment_kpis,
    get_sentiment_split_percentage,
    get_sentiment_score_distribution,
    get_reviews_per_bank,
    get_outlet_rating_analysis,
    get_sentiment_analysis,
    get_comments_per_topic,
    get_topic_sentiment_breakdown,
    get_bank_sentiment_breakdown,
    get_topic_distribution_percentage
)

router = APIRouter(
    prefix="/review",
    tags=["Bank Spatial Review"]
)


@router.get("/kpis")
async def fetch_sentiment_kpis(
    cluster: str = None,
    sub_cluster: str = None,
    zone: str = None,
    country: str = None
):
    return await get_sentiment_kpis(cluster, sub_cluster, zone, country)


@router.get("/sentiment-split")
async def fetch_sentiment_split_percentage(
    cluster: str = None,
    sub_cluster: str = None,
    zone: str = None,
    country: str = None
):
    return await get_sentiment_split_percentage(cluster, sub_cluster, zone, country)


@router.get("/sentiment-score-distribution")
async def fetch_sentiment_score_distribution(
    cluster: str = None,
    sub_cluster: str = None,
    zone: str = None,
    country: str = None
):
    return await get_sentiment_score_distribution(cluster, sub_cluster, zone, country)


@router.get("/reviews-per-bank")
async def fetch_reviews_per_bank(
    cluster: str = None,
    sub_cluster: str = None,
    zone: str = None,
    country: str = None
):
    return await get_reviews_per_bank(cluster, sub_cluster, zone, country)


@router.get("/outlet-rating-analysis")
async def fetch_outlet_rating_analysis(
    cluster: str = None,
    sub_cluster: str = None,
    zone: str = None,
    country: str = None
):
    return await get_outlet_rating_analysis(cluster, sub_cluster, zone, country)


@router.get("/sentiment-analysis")
async def fetch_sentiment_analysis(
    cluster: str = None,
    sub_cluster: str = None,
    zone: str = None,
    country: str = None
):
    return await get_sentiment_analysis(cluster, sub_cluster, zone, country)



@router.get("/comments-per-topic")
async def fetch_comments_per_topic(
    cluster: str = None,
    sub_cluster: str = None,
    zone: str = None,
    country: str = None
):
    return await get_comments_per_topic(cluster, sub_cluster, zone, country)


@router.get("/topic-sentiment-breakdown")
async def fetch_topic_sentiment_breakdown(
    cluster: str = None,
    sub_cluster: str = None,
    zone: str = None,
    country: str = None
):
    return await get_topic_sentiment_breakdown(cluster, sub_cluster, zone, country)


@router.get("/bank-sentiment-breakdown")
async def fetch_bank_sentiment_breakdown(
    cluster: str = None,
    sub_cluster: str = None,
    zone: str = None,
    country: str = None
):
    return await get_bank_sentiment_breakdown(cluster, sub_cluster, zone, country)



@router.get("/topic-distribution-percentage")
async def fetch_topic_distribution_percentage(
    cluster: str = None,
    sub_cluster: str = None,
    zone: str = None,
    country: str = None
):
    return await get_topic_distribution_percentage(cluster, sub_cluster, zone, country)