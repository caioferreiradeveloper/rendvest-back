# Django imports
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.dashboard.views import DashboardView

# URL patterns for the apps
urlpatterns = [
    path("api/v1/dashboard/", DashboardView.as_view(), name="dashboard"),
    path("api/v1/auth/", include("apps.authentication.urls")),
    path("api/v1/users/", include("apps.users.urls")),
    path("api/v1/transactions/", include("apps.transactions.urls")),
    path("api/v1/loans/", include("apps.loans.urls")),
    path("api/v1/debtors/", include("apps.debtors.urls")),
    path("api/v1/monthlies/", include("apps.monthlies.urls")),
    path("api/v1/wishlist/", include("apps.wishlist.urls")),
    path("api/v1/investments/", include("apps.investments.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
