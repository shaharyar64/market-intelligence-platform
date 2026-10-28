from typing import List, Optional
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from shared.cache import cache_query, CACHE_TTL_5_MIN

from services.beer_cider_pricing_service.app.services.beer import (
    fetch_overview,
    fetch_distribution,
    fetch_pricing,
    fetch_availability,
    fetch_format_insights,
    fetch_products,
    fetch_export,
    fetch_brand_sales,
    fetch_brand_visibility_by_retailer,
    fetch_filters,
    fetch_retailers,
    fetch_price_trend,
    fetch_core_competition_pricing_comparison,
    fetch_promotion_sku_trending,
    fetch_promotion_sku_trending_core_competition,
    fetch_discount_trending,
    fetch_discount_trending_core_competition,
    fetch_discount_trending_core_competition_comparison,
    fetch_list_vs_promo_price_gap,
    fetch_list_vs_promo_price_gap_core_competition,
    fetch_availability_trending,
    fetch_availability_trending_core_competition_comparison,
    fetch_total_active_skus_trending,
    fetch_total_active_skus_trending_core_competition_comparison,
    fetch_out_of_stock_skus_trending,
    fetch_out_of_stock_skus_trending_core_competition_comparison,
    fetch_share_of_visibility_heineken_portfolio,
    fetch_can_vs_bottle_mix,
    fetch_pack_mix,
    fetch_can_vs_bottle_trend,
    fetch_pack_size_distribution_trend,
    fetch_price_trends_by_brand,
    fetch_promotion_depth_by_brand,
    fetch_promotion_depth_by_brand_trend,
    fetch_availability_by_brand,
    fetch_availability_by_brand_trend,
    fetch_hero_sku_tracker,
    fetch_hero_sku_trend,
    fetch_hero_sku_price_trend,
)

router = APIRouter(
    prefix="",
    tags=["Beer Cider Pricing"],
)


def build_response(data):
    return {"data": data, "success": True}


async def run_query(fetcher):
    try:
        data = await fetcher()
        return build_response(data)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(exc)},
        )


@router.get("/overview")
async def get_overview(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    local: bool = Query(False),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
        "local": local,
    }
    return await run_query(lambda: fetch_overview(filters))


@router.get("/distribution")
async def get_distribution():
    return await run_query(fetch_distribution)


@router.get("/pricing")
async def get_pricing(local: bool = Query(False)):
    return await run_query(lambda: fetch_pricing({"local": local}))


@router.get("/availability")
async def get_availability():
    return await run_query(fetch_availability)


@router.get("/format-insights")
async def get_format_insights():
    return await run_query(fetch_format_insights)


@router.get("/products")
async def get_products():
    return await run_query(fetch_products)


@router.get("/brand-sales")
async def get_brand_sales(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    local: bool = Query(False),
    date: Optional[str] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "brand": brand,
        "type": type,
        "quantity": quantity,
        "sku": sku,
        "sub_type": sub_type,
        "city": city,
        "local": local,
        "date": date,
    }
    return await run_query(
        lambda: cache_query(
            "brand_sales",
            filters,
            lambda: fetch_brand_sales(filters),
            ttl=CACHE_TTL_5_MIN,
        )
    )


@router.get("/brand-visibility-by-retailer")
async def get_brand_visibility_by_retailer(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    date: Optional[str] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "brand": brand,
        "type": type,
        "quantity": quantity,
        "sku": sku,
        "sub_type": sub_type,
        "city": city,
        "date": date,
    }
    return await run_query(
        lambda: cache_query(
            "brand_visibility_by_retailer",
            filters,
            lambda: fetch_brand_visibility_by_retailer(filters),
            ttl=CACHE_TTL_5_MIN,
        )
    )


@router.get("/export")
async def get_export(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
        "date": date,
    }
    return await run_query(lambda: fetch_export(filters, page=page, limit=limit))


@router.get("/filters")
async def get_filters(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    partial: bool = Query(False),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "brand": brand,
        "type": type,
        "quantity": quantity,
        "sku": sku,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(lambda: fetch_filters(filters, partial=partial))


@router.get("/retailers")
async def get_retailers(market: Optional[List[str]] = Query(None)):
    return await run_query(lambda: fetch_retailers(market))


@router.get("/price-trend")
async def get_price_trend(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    local: bool = Query(False),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
        "local": local,
    }
    return await run_query(lambda: fetch_price_trend(filters))


@router.get("/core-competition-pricing-comparison")
async def get_core_competition_pricing_comparison(
    market: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    local: bool = Query(False),
):
    filters = {
        "market": market,
        "city": city,
        "retailer": retailer,
        "comp": comp,
        "type": type,
        "sku": sku,
        "quantity": quantity,
        "local": local,
    }
    return await run_query(
        lambda: fetch_core_competition_pricing_comparison(filters)
    )


@router.get("/core-competition-comparison")
async def get_core_competition_comparison(
    market: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    local: bool = Query(False),
):
    filters = {
        "market": market,
        "comp": comp,
        "type": type,
        "sku": sku,
        "quantity": quantity,
        "local": local,
    }
    return await run_query(
        lambda: fetch_core_competition_pricing_comparison(filters)
    )


@router.get("/promotion-sku-trending")
async def get_promotion_sku_trending(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(lambda: fetch_promotion_sku_trending(filters))


@router.get("/promotion-sku-trending-core-competition")
async def get_promotion_sku_trending_core_competition(
    market: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "city": city,
        "comp": comp,
        "type": type,
        "sku": sku,
        "quantity": quantity,
    }
    return await run_query(
        lambda: fetch_promotion_sku_trending_core_competition(filters)
    )


@router.get("/discount-trending")
async def get_discount_trending(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(lambda: fetch_discount_trending(filters))


@router.get("/discount-trending-core-competition")
async def get_discount_trending_core_competition(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(
        lambda: fetch_discount_trending_core_competition(filters)
    )


@router.get("/discount-trending-core-competition-comparison")
async def get_discount_trending_core_competition_comparison(
    market: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "city": city,
        "comp": comp,
        "type": type,
        "sku": sku,
        "quantity": quantity,
    }
    return await run_query(
        lambda: fetch_discount_trending_core_competition_comparison(filters)
    )


@router.get("/list-vs-promo-price-gap")
async def get_list_vs_promo_price_gap(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    local: bool = Query(False),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
        "local": local,
    }
    return await run_query(lambda: fetch_list_vs_promo_price_gap(filters))


@router.get("/list-vs-promo-price-gap-core-competition")
async def get_list_vs_promo_price_gap_core_competition(
    market: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    local: bool = Query(False),
):
    filters = {
        "market": market,
        "city": city,
        "comp": comp,
        "type": type,
        "sku": sku,
        "quantity": quantity,
        "local": local,
    }
    return await run_query(
        lambda: fetch_list_vs_promo_price_gap_core_competition(filters)
    )


@router.get("/availability-trending")
async def get_availability_trending(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(lambda: fetch_availability_trending(filters))


@router.get("/availability-trending-core-competition-comparison")
async def get_availability_trending_core_competition_comparison(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(
        lambda: fetch_availability_trending_core_competition_comparison(filters)
    )


@router.get("/total-active-skus-trending")
async def get_total_active_skus_trending(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(lambda: fetch_total_active_skus_trending(filters))


@router.get("/total-active-skus-trending-core-competition-comparison")
async def get_total_active_skus_trending_core_competition_comparison(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(
        lambda: fetch_total_active_skus_trending_core_competition_comparison(filters)
    )


@router.get("/out-of-stock-skus-trending")
async def get_out_of_stock_skus_trending(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(lambda: fetch_out_of_stock_skus_trending(filters))


@router.get("/out-of-stock-skus-trending-core-competition-comparison")
async def get_out_of_stock_skus_trending_core_competition_comparison(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(
        lambda: fetch_out_of_stock_skus_trending_core_competition_comparison(filters)
    )


@router.get("/share-of-visibility-heineken-portfolio")
async def get_share_of_visibility_heineken_portfolio(
    market: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "city": city,
        "retailer": retailer,
        "comp": comp,
        "type": type,
        "sku": sku,
        "quantity": quantity,
    }
    return await run_query(
        lambda: fetch_share_of_visibility_heineken_portfolio(filters)
    )


@router.get("/can-vs-bottle-mix")
async def get_can_vs_bottle_mix(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(lambda: fetch_can_vs_bottle_mix(filters))


@router.get("/pack-mix")
async def get_pack_mix(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(lambda: fetch_pack_mix(filters))


@router.get("/can-vs-bottle-trend")
async def get_can_vs_bottle_trend(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(lambda: fetch_can_vs_bottle_trend(filters))


@router.get("/pack-size-distribution-trend")
async def get_pack_size_distribution_trend(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(lambda: fetch_pack_size_distribution_trend(filters))


@router.get("/price-trends-by-brand")
async def get_price_trends_by_brand(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    local: bool = Query(False),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
        "local": local,
    }
    return await run_query(lambda: fetch_price_trends_by_brand(filters))


@router.get("/promotion-depth-by-brand")
async def get_promotion_depth_by_brand(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(lambda: fetch_promotion_depth_by_brand(filters))


@router.get("/promotion-depth-by-brand-trend")
async def get_promotion_depth_by_brand_trend(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(lambda: fetch_promotion_depth_by_brand_trend(filters))


@router.get("/availability-by-brand")
async def get_availability_by_brand(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(lambda: fetch_availability_by_brand(filters))


@router.get("/availability-by-brand-trend")
async def get_availability_by_brand_trend(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "type": type,
        "brand": brand,
        "sku": sku,
        "quantity": quantity,
        "sub_type": sub_type,
        "city": city,
    }
    return await run_query(lambda: fetch_availability_by_brand_trend(filters))


@router.get("/hero-sku-tracker")
async def get_hero_sku_tracker(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    local: bool = Query(False),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "brand": brand,
        "type": type,
        "quantity": quantity,
        "sku": sku,
        "sub_type": sub_type,
        "city": city,
        "local": local,
    }
    return await run_query(
        lambda: cache_query(
            "hero_sku_tracker",
            filters,
            lambda: fetch_hero_sku_tracker(filters),
            ttl=CACHE_TTL_5_MIN,
        )
    )


@router.get("/hero-sku-price-trend")
async def get_hero_sku_price_trend(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    local: bool = Query(False),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "brand": brand,
        "type": type,
        "quantity": quantity,
        "sku": sku,
        "sub_type": sub_type,
        "city": city,
        "local": local,
        "start_date": start_date,
        "end_date": end_date,
    }
    return await run_query(
        lambda: cache_query(
            "hero_sku_price_trend",
            filters,
            lambda: fetch_hero_sku_price_trend(filters),
            ttl=CACHE_TTL_5_MIN,
        )
    )


@router.get("/hero-sku-trend")
async def get_hero_sku_trend(
    market: Optional[List[str]] = Query(None),
    retailer: Optional[List[str]] = Query(None),
    segment: Optional[List[str]] = Query(None),
    comp: Optional[List[str]] = Query(None),
    brand: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    quantity: Optional[List[str]] = Query(None),
    sku: Optional[List[int]] = Query(None),
    sub_type: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    local: bool = Query(False),
):
    filters = {
        "market": market,
        "retailer": retailer,
        "segment": segment,
        "comp": comp,
        "brand": brand,
        "type": type,
        "quantity": quantity,
        "sku": sku,
        "sub_type": sub_type,
        "city": city,
        "local": local,
    }
    return await run_query(
        lambda: cache_query(
            "hero_sku_trend",
            filters,
            lambda: fetch_hero_sku_trend(filters),
            ttl=CACHE_TTL_5_MIN,
        )
    )
