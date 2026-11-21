from django.urls import path

from .funds import FundDistributionsView, FundPricesView, FundProfileView, FundStatsView
from .views import AssetSearchView, QuoteView

urlpatterns = [
    path("funds/<str:ticker>/", FundProfileView.as_view(), name="investment-fund-profile"),
    path("funds/<str:ticker>/stats/", FundStatsView.as_view(), name="investment-fund-stats"),
    path("funds/<str:ticker>/prices/", FundPricesView.as_view(), name="investment-fund-prices"),
    path(
        "funds/<str:ticker>/distributions/",
        FundDistributionsView.as_view(),
        name="investment-fund-distributions",
    ),
    path("assets/", AssetSearchView.as_view(), name="investment-assets"),
    path("quotes/<str:ticker>/", QuoteView.as_view(), name="investment-quote"),
]
