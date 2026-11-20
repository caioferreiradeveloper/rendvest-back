# Django imports
from django.urls import path

# App imports
from apps.transactions.views import (
    TransactionList,
    TransactionCreate,
    TransactionDetail,
    TransactionUpdate,
    TransactionDelete,
)

# URL configuration for the transaction app
app_name = "transactions"


# URL patterns for the transaction app
urlpatterns = [
    path("", TransactionList.as_view(), name="transaction-list"),
    path("create/", TransactionCreate.as_view(), name="transaction-create"),
    path("<uuid:pk>/", TransactionDetail.as_view(), name="transaction-detail"),
    path("update/<uuid:pk>/", TransactionUpdate.as_view(), name="transaction-update"),
    path("delete/<uuid:pk>/", TransactionDelete.as_view(), name="transaction-delete"),
]