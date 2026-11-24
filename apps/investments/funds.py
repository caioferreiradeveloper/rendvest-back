from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from .fund_data import get_fund
from .serializers import TickerParams


def investment_ticker(value):
    params = TickerParams(data={"ticker": value})
    params.is_valid(raise_exception=True)
    return params.validated_data["ticker"].upper()


class FundDataView(APIView):
    throttle_scope = "investment_research"
    section = "profile"

    @extend_schema(responses={200: dict})
    def get(self, request, ticker):
        fund = get_fund(investment_ticker(ticker))
        data = fund.data[self.section]
        if self.section == "prices":
            data = {"prices": data}
        return Response(data)


class FundRefreshView(APIView):
    throttle_scope = "fund_refresh"

    @extend_schema(request=None, responses={200: dict})
    def post(self, request, ticker):
        fund = get_fund(investment_ticker(ticker), force=True, allow_stale=False)
        return Response({"ticker": fund.ticker, "updated_at": fund.updated_at, **fund.data})
