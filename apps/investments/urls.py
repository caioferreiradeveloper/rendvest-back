from django.urls import path

from .funds import FundDataView, FundRefreshView
from .views import AssetSearchView, InvestmentListCreateView, QuoteView

urlpatterns = [
    path("", InvestmentListCreateView.as_view(), name="investment-list"),
    path("funds/<str:ticker>/", FundDataView.as_view(), name="investment-fund-profile"),
    path(
        "funds/<str:ticker>/stats/",
        FundDataView.as_view(section="stats"),
        name="investment-fund-stats",
    ),
    path(
        "funds/<str:ticker>/prices/",
        FundDataView.as_view(section="prices"),
        name="investment-fund-prices",
    ),
    path(
        "funds/<str:ticker>/distributions/",
        FundDataView.as_view(section="distributions"),
        name="investment-fund-distributions",
    ),
    path(
        "funds/<str:ticker>/quote/",
        FundDataView.as_view(section="quote"),
        name="investment-fund-quote",
    ),
    path("funds/<str:ticker>/refresh/", FundRefreshView.as_view(), name="investment-fund-refresh"),
    path("assets/", AssetSearchView.as_view(), name="investment-assets"),
    path("quotes/<str:ticker>/", QuoteView.as_view(), name="investment-quote"),
]
