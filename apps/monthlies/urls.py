from django.urls import path

from apps.monthlies.views import (
    MonthlyCreate,
    MonthlyDelete,
    MonthlyDetail,
    MonthlyList,
    MonthlySettle,
    MonthlyUpdate,
)

app_name = "monthlies"

urlpatterns = [
    path("", MonthlyList.as_view(), name="monthly-list"),
    path("create/", MonthlyCreate.as_view(), name="monthly-create"),
    path("<uuid:pk>/", MonthlyDetail.as_view(), name="monthly-detail"),
    path("update/<uuid:pk>/", MonthlyUpdate.as_view(), name="monthly-update"),
    path("delete/<uuid:pk>/", MonthlyDelete.as_view(), name="monthly-delete"),
    path("<uuid:pk>/settle/", MonthlySettle.as_view(), name="monthly-settle"),
]
