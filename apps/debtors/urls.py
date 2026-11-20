# Django imports
from django.urls import path

# App imports
from apps.debtors.views import (
    DebtorCreate,
    DebtorDelete,
    DebtorDetail,
    DebtorList,
    DebtorPay,
    DebtorUpdate,
)

# URL configuration for the debtor app
app_name = "debtors"


# URL patterns for the debtor app
urlpatterns = [
    path("", DebtorList.as_view(), name="debtor-list"),
    path("create/", DebtorCreate.as_view(), name="debtor-create"),
    path("<uuid:pk>/", DebtorDetail.as_view(), name="debtor-detail"),
    path("update/<uuid:pk>/", DebtorUpdate.as_view(), name="debtor-update"),
    path("delete/<uuid:pk>/", DebtorDelete.as_view(), name="debtor-delete"),
    path("<uuid:pk>/pay/", DebtorPay.as_view(), name="debtor-pay"),
]
