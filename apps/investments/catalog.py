import re

from django.core.cache import cache

from .bolsai import MarketDataUnavailable, get_market_data
from .brapi import fetch_brapi

CATALOG_CACHE_SECONDS = 3600
STOCK_TICKER = re.compile(r"[A-Z0-9]{4}(?:[3-8]|11)")


def catalog_items(path, field, limit):
    offset = 0
    while True:
        data = get_market_data(f"{path}&limit={limit}&offset={offset}", CATALOG_CACHE_SECONDS)
        items = data.get(field)
        total = data.get("total")
        if not isinstance(items, list) or not isinstance(total, int):
            raise MarketDataUnavailable()

        yield from items
        offset += len(items)
        if offset >= total:
            return
        if not items:
            raise MarketDataUnavailable()


def list_stocks():
    companies = {
        item["ticker_primary"][:4]: item
        for item in catalog_items("companies/?status=ATIVO", "data", 500)
        if item.get("ticker_primary")
    }
    tickers = set(catalog_items("stocks/?bdi_code=02", "tickers", 5000))
    tickers.update(company["ticker_primary"] for company in companies.values())
    return [
        {
            "ticker": ticker,
            "name": companies[ticker[:4]].get("trade_name")
            or companies[ticker[:4]].get("corporate_name"),
            "segment": companies[ticker[:4]].get("sector"),
        }
        for ticker in tickers
        if STOCK_TICKER.fullmatch(ticker) and ticker[:4] in companies
    ]


def list_funds():
    cache_key = "investments:brapi:fii-catalog"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = fetch_brapi("quote/list?type=fund&subType=fii")
    items = data.get("stocks")
    if not isinstance(items, list) or not items:
        raise MarketDataUnavailable()
    funds = [
        {"ticker": item["stock"], "name": item.get("name"), "segment": item.get("subsector")}
        for item in items
        if isinstance(item, dict) and item.get("subType") == "fii" and item.get("stock")
    ]
    if not funds:
        raise MarketDataUnavailable()
    cache.set(cache_key, funds, CATALOG_CACHE_SECONDS)
    return funds
