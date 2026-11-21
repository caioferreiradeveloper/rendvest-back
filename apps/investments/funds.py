from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from .bolsai import MarketDataUnavailable, get_market_data
from .serializers import TickerParams
from .snapshots import get_market_snapshot

PROFILE_FIELDS = (
    "name",
    "segment",
    "fund_type",
    "administrator",
    "reference_date",
    "close_price",
    "pvp",
    "dividend_yield_ttm",
    "net_asset_value",
    "total_shareholders",
)
PRICE_FIELDS = ("trade_date", "close", "adjusted_close", "traded_amount")
PAYMENT_FIELDS = (
    "reference_date",
    "record_date",
    "payment_date",
    "value_per_share",
    "dy_month_pct",
)


def investment_ticker(value):
    params = TickerParams(data={"ticker": value})
    params.is_valid(raise_exception=True)
    return params.validated_data["ticker"].upper()


def select_fields(record, fields):
    if not isinstance(record, dict):
        raise MarketDataUnavailable()
    return {field: record.get(field) for field in fields}


def select_rows(data, key, fields):
    rows = data.get(key)
    if not isinstance(rows, list):
        raise MarketDataUnavailable()
    return [select_fields(row, fields) for row in rows]


class FundProfileView(APIView):
    throttle_scope = "investment_research"

    @extend_schema(responses={"200": dict})
    def get(self, request, ticker):
        ticker = investment_ticker(ticker)
        return Response(
            get_market_snapshot(f"fiis/{ticker}", lambda data: select_fields(data, PROFILE_FIELDS))
        )


class FundPricesView(APIView):
    throttle_scope = "investment_research"

    @extend_schema(responses={"200": dict})
    def get(self, request, ticker):
        ticker = investment_ticker(ticker)
        return Response(
            get_market_snapshot(
                f"stocks/{ticker}/history?limit=270",
                lambda data: {"prices": select_rows(data, "prices", PRICE_FIELDS)},
            )
        )


class FundDistributionsView(APIView):
    throttle_scope = "investment_research"

    @extend_schema(responses={"200": dict})
    def get(self, request, ticker):
        ticker = investment_ticker(ticker)
        data = get_market_data(f"fiis/{ticker}/distributions?years=2", 3600, quote=True)
        return Response(
            {
                "dividend_yield_ttm": data.get("dividend_yield_ttm"),
                "payments": select_rows(data, "payments", PAYMENT_FIELDS),
            }
        )


class FundStatsView(APIView):
    throttle_scope = "investment_research"

    @extend_schema(responses={"200": dict})
    def get(self, request, ticker):
        ticker = investment_ticker(ticker)
        fields = ("trade_date", "daily_change_pct", "week_52_low", "week_52_high")
        return Response(
            get_market_snapshot(f"stocks/{ticker}/stats", lambda data: select_fields(data, fields))
        )
