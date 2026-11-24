from datetime import UTC, date, datetime

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from .bolsai import MarketDataUnavailable, get_market_data
from .brapi import fetch_brapi
from .catalog import list_funds
from .models import RealEstateFund
from .serializers import Quote
from .snapshots import REFRESH_INTERVAL

PROFILE_FIELDS = {
    "name": "name",
    "segment": "segmentoAtuacao",
    "fund_type": "segmentType",
    "administrator": "administratorName",
    "reference_date": "asOfDate",
    "pvp": "priceToNav",
    "dividend_yield_ttm": "dividendYield12m",
    "net_asset_value": "equity",
    "total_shareholders": "totalInvestors",
    "nav_per_share": "navPerShare",
    "monthly_return_pct": "monthlyReturn",
    "monthly_dividend_yield_pct": "dividendYield1m",
    "shares_outstanding": "sharesOutstanding",
    "total_assets": "totalAssets",
    "cnpj": "cnpj",
    "management_type": "tipoGestao",
}
PRICE_FIELDS = ("trade_date", "close", "adjusted_close", "traded_amount")
PAYMENT_FIELDS = (
    "reference_date",
    "record_date",
    "payment_date",
    "value_per_share",
    "dy_month_pct",
    "ex_date",
)


def rows(data, key):
    result = data.get(key, [])
    return [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []


def select_fields(data, fields):
    return {field: data.get(field) for field in fields}


def optional(fetch, *args, **kwargs):
    try:
        return fetch(*args, **kwargs)
    except (MarketDataUnavailable, NotFound):
        return {}


def iso_date(value):
    try:
        if isinstance(value, int | float):
            return datetime.fromtimestamp(value, UTC).date().isoformat()
        if isinstance(value, str):
            return date.fromisoformat(value[:10]).isoformat()
    except (ValueError, OverflowError, OSError):
        pass
    return None


def find_fund(ticker):
    for fund in list_funds():
        if fund["ticker"] == ticker:
            return {"name": fund["name"], "segment": fund["segment"]}
    raise NotFound()


def fund_profile(ticker, previous, quote, identity):
    data = optional(fetch_brapi, f"v2/fii/indicators?symbols={ticker}")
    indicators = (
        next((item for item in rows(data, "fiis") if item.get("symbol") == ticker), None)
        if "fiis" in data
        else None
    )
    if indicators:
        profile = {key: indicators.get(field) for key, field in PROFILE_FIELDS.items()}
        profile["reference_date"] = iso_date(profile["reference_date"])
        for key in ("dividend_yield_ttm", "monthly_return_pct", "monthly_dividend_yield_pct"):
            if isinstance(profile[key], int | float):
                profile[key] *= 100
    else:
        fallback = optional(get_market_data, f"fiis/{ticker}", quote=True)
        profile = select_fields(fallback, PROFILE_FIELDS) if fallback else {}
    return {
        **identity,
        **previous,
        **{k: v for k, v in profile.items() if v is not None},
        "close_price": quote["regularMarketPrice"],
        "logo_url": quote.get("logourl"),
    }


def fund_prices(previous, market, history):
    prices = {item["trade_date"]: item for item in previous}
    for row in rows(history, "prices"):
        day = iso_date(row.get("trade_date"))
        if day and row.get("close") is not None:
            prices[day] = {**select_fields(row, PRICE_FIELDS), "trade_date": day}
    for row in rows(market, "historicalDataPrice"):
        day = iso_date(row.get("date"))
        if day and row.get("close") is not None:
            prices[day] = {
                **prices.get(day, {}),
                "trade_date": day,
                "close": row.get("close"),
                "adjusted_close": row.get("adjustedClose"),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "volume": row.get("volume"),
            }
    return [prices[day] for day in sorted(prices)[-270:]]


def fund_distributions(ticker, previous, profile, prices):
    data = optional(fetch_brapi, f"v2/fii/dividends?symbols={ticker}")
    closes = {row["trade_date"]: row.get("close") for row in prices}
    payments = []
    for row in rows(data, "dividends"):
        if row.get("symbol") != ticker or row.get("label") != "RENDIMENTO":
            continue
        record_date = iso_date(row.get("lastDatePrior"))
        payment_date = iso_date(row.get("paymentDate"))
        rate = row.get("rawRate")
        if rate is None:
            rate = row.get("rate")
        if rate is None or not (record_date or payment_date):
            continue
        close = closes.get(record_date)
        yield_pct = (
            rate / close * 100
            if isinstance(rate, int | float) and isinstance(close, int | float) and close > 0
            else None
        )
        payments.append(
            {
                "reference_date": None,
                "record_date": record_date,
                "payment_date": payment_date,
                "value_per_share": rate,
                "dy_month_pct": yield_pct,
                "label": row["label"],
                "ex_date": iso_date(row.get("exDate")),
            }
        )
    dividend_yield = profile.get("dividend_yield_ttm")
    if not payments or any(not row["record_date"] or not row["payment_date"] for row in payments):
        fallback = optional(get_market_data, f"fiis/{ticker}/distributions?years=2", quote=True)
        if not rows(fallback, "payments"):
            fallback = optional(get_market_data, f"dividends/{ticker}?years=2", quote=True)
        if dividend_yield is None:
            dividend_yield = fallback.get("dividend_yield_ttm")
        supplements = [
            select_fields(row, PAYMENT_FIELDS)
            for row in rows(fallback, "payments")
            if str(row.get("type") or "Rendimento").casefold() == "rendimento"
            and row.get("value_per_share") is not None
        ] or previous
        for row in supplements:
            match = next(
                (
                    payment for payment in payments
                    if payment.get("value_per_share") == row.get("value_per_share")
                    and (
                        payment.get("payment_date")
                        and payment["payment_date"] == row.get("payment_date")
                        or payment.get("record_date")
                        and payment["record_date"] == row.get("record_date")
                    )
                    and all(
                        not payment.get(field) or not row.get(field) or payment[field] == row[field]
                        for field in ("record_date", "payment_date")
                    )
                ),
                None,
            )
            if match is None:
                payments.append(row)
            else:
                match.update({key: value for key, value in row.items() if match.get(key) is None})
    return {
        "dividend_yield_ttm": dividend_yield,
        "payments": sorted(
            payments,
            key=lambda item: item.get("payment_date") or item.get("record_date") or "",
            reverse=True,
        ),
    }


def collect_fund(ticker, previous):
    identity = {} if previous else find_fund(ticker)
    data = optional(fetch_brapi, f"quote/{ticker}?range=3mo&interval=1d")
    market = next((row for row in rows(data, "results") if row.get("symbol") == ticker), {})
    history = optional(get_market_data, f"stocks/{ticker}/history?limit=270", quote=True)
    prices = fund_prices(previous.get("prices", []), market, history)
    quote = Quote(
        data={
            "ticker": ticker,
            "price": market.get("regularMarketPrice"),
            "currency": market.get("currency"),
            "trade_date": iso_date(market.get("regularMarketTime")),
        }
    )
    if not quote.is_valid():
        fallback = optional(get_market_data, f"stocks/{ticker}/quote", quote=True)
        if (fallback.get("close") is None or not iso_date(fallback.get("trade_date"))) and prices:
            fallback = prices[-1]
        quote = Quote(
            data={
                "ticker": ticker,
                "price": fallback.get("close"),
                "currency": "BRL",
                "trade_date": fallback.get("trade_date"),
            }
        )
        if not quote.is_valid():
            raise MarketDataUnavailable()
        market = {
            **market,
            "regularMarketPrice": fallback["close"],
            "regularMarketOpen": fallback.get("open"),
            "regularMarketDayLow": fallback.get("low"),
            "regularMarketDayHigh": fallback.get("high"),
            "regularMarketVolume": fallback.get("volume"),
            "regularMarketTime": fallback["trade_date"],
        }
    serialized_quote = Quote(quote.validated_data).data
    profile = fund_profile(ticker, previous.get("profile", {}), market, identity)
    return {
        "quote": serialized_quote,
        "profile": profile,
        "prices": prices,
        "distributions": fund_distributions(
            ticker, previous.get("distributions", {}).get("payments", []), profile, prices
        ),
        "stats": {
            "trade_date": serialized_quote["trade_date"],
            "daily_change_pct": market.get("regularMarketChangePercent"),
            "week_52_low": market.get("fiftyTwoWeekLow"),
            "week_52_high": market.get("fiftyTwoWeekHigh"),
            "open": market.get("regularMarketOpen"),
            "day_low": market.get("regularMarketDayLow"),
            "day_high": market.get("regularMarketDayHigh"),
            "previous_close": market.get("regularMarketPreviousClose"),
            "volume": market.get("regularMarketVolume"),
            "quoted_at": market.get("regularMarketTime"),
        },
    }


@transaction.atomic
def get_fund(ticker, *, force=False, allow_stale=True):
    fund, _ = RealEstateFund.objects.select_for_update().get_or_create(ticker=ticker)
    if not force and fund.updated_at and timezone.now() - fund.updated_at < REFRESH_INTERVAL:
        return fund
    try:
        fund.data = collect_fund(ticker, fund.data)
    except (MarketDataUnavailable, NotFound):
        if allow_stale and fund.updated_at:
            return fund
        raise
    fund.updated_at = timezone.now()
    fund.save(update_fields=["data", "updated_at"])
    return fund
