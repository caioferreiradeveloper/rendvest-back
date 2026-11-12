from django.urls import path

from apps.loans.views import (
    LoanDetailView,
    LoanInstallmentListView,
    LoanListCreateView,
    LoanPaymentListCreateView,
)

app_name = "loans"

urlpatterns = [
    path("", LoanListCreateView.as_view(), name="loan-list"),
    path("<uuid:pk>/", LoanDetailView.as_view(), name="loan-detail"),
    path(
        "<uuid:loan_pk>/installments/", LoanInstallmentListView.as_view(), name="installment-list"
    ),
    path("<uuid:loan_pk>/payments/", LoanPaymentListCreateView.as_view(), name="payment-list"),
]
