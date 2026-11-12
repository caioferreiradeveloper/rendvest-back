from django.urls import path

from apps.transactions.views import (
    ExpenseCollectionView,
    ExpenseDetailView,
    IncomeCollectionView,
    IncomeDetailView,
    ListTransactions,
)

app_name = "transactions"

urlpatterns = [
    path("", ListTransactions.as_view(), name="transaction-list"),
    path("incomes/", IncomeCollectionView.as_view(), name="income-list"),
    path("incomes/<uuid:pk>/", IncomeDetailView.as_view(), name="income-detail"),
    path("expenses/", ExpenseCollectionView.as_view(), name="expense-list"),
    path("expenses/<uuid:pk>/", ExpenseDetailView.as_view(), name="expense-detail"),
]
