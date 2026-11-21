from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from .catalog import list_funds, list_stocks
from .quotes import get_quote
from .serializers import AssetSearchParams, AssetSearchResult, Quote, TickerParams

PAGE_SIZE = 20


class AssetSearchView(APIView):
    throttle_scope = "investment_research"

    @extend_schema(parameters=[AssetSearchParams], responses=AssetSearchResult)
    def get(self, request):
        params = AssetSearchParams(data=request.query_params)
        params.is_valid(raise_exception=True)
        filters = params.validated_data

        assets = list_stocks() if filters["type"] == "stock" else list_funds()
        query = slugify(filters["q"])
        matches = [
            asset
            for asset in assets
            if any(query in slugify(value or "") for value in asset.values())
        ]
        matches.sort(key=lambda asset: (slugify(asset["ticker"]) != query, asset["ticker"]))
        page = filters["page"]
        start = (page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        return Response(
            {
                "count": len(matches),
                "next_page": page + 1 if end < len(matches) else None,
                "results": matches[start:end],
            }
        )


class QuoteView(APIView):
    throttle_scope = "investment_research"

    @extend_schema(responses=Quote)
    def get(self, request, ticker):
        params = TickerParams(data={"ticker": ticker})
        params.is_valid(raise_exception=True)
        ticker = params.validated_data["ticker"].upper()

        return Response(get_quote(ticker))
