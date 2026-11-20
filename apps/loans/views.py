from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import generics, serializers
from rest_framework.exceptions import APIException
from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)

from apps.loans.models import Loan, LoanInstallment, LoanPayment
from apps.loans.serializers import LoanInstallmentSerializer, LoanPaymentSerializer, LoanSerializer
from apps.transactions.models import Transaction

# Core imports
from core.enums import Bank, Type


class LoanFilter(filters.FilterSet):
    type_bank = filters.ChoiceFilter(field_name="bank", choices=Bank.choices)

    class Meta:
        model = Loan
        fields = ["bank", "started_at", "first_due_date"]


class LoanHasPayments(APIException):
    status_code = 409
    default_detail = "Não é possível excluir um empréstimo que possui pagamentos registrados."
    default_code = "loan_has_payments"
    error_code = "RENDVEST_ERROR_0007"


class LoanQuerysetMixin:
    def get_queryset(self):
        return Loan.objects.filter(user=self.request.user)


class LoanListCreateView(generics.ListAPIView, generics.CreateAPIView):
    serializer_class = LoanSerializer
    filterset_class = LoanFilter
    ordering_fields = ["started_at", "contracted_amount", "term_months", "created_at"]
    ordering = ["-started_at", "-created_at"]

    def get_queryset(self):
        return Loan.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    get = ListModelMixin.list
    post = CreateModelMixin.create


class LoanDetailView(
    LoanQuerysetMixin,
    generics.RetrieveAPIView,
    generics.UpdateAPIView,
    generics.DestroyAPIView,
):
    serializer_class = LoanSerializer

    get = RetrieveModelMixin.retrieve
    put = UpdateModelMixin.update
    patch = UpdateModelMixin.partial_update
    delete = DestroyModelMixin.destroy

    def perform_destroy(self, instance):
        if instance.installments.filter(payments__isnull=False).exists():
            raise LoanHasPayments
        instance.delete()


class LoanInstallmentListView(generics.ListAPIView):
    serializer_class = LoanInstallmentSerializer

    def get_loan(self):
        if not hasattr(self, "_loan"):
            self._loan = get_object_or_404(
                Loan.objects.filter(user=self.request.user),
                pk=self.kwargs["loan_pk"],
            )
        return self._loan

    def get_queryset(self):
        return LoanInstallment.objects.filter(loan=self.get_loan()).order_by("number")


class LoanPaymentListCreateView(generics.ListAPIView, generics.CreateAPIView):
    serializer_class = LoanPaymentSerializer

    def get_loan(self):
        if not hasattr(self, "_loan"):
            self._loan = get_object_or_404(
                Loan.objects.filter(user=self.request.user),
                pk=self.kwargs["loan_pk"],
            )
        return self._loan

    def get_queryset(self):
        return LoanPayment.objects.filter(installment__loan=self.get_loan()).select_related(
            "installment",
            "expense_transaction",
        )

    @transaction.atomic
    def perform_create(self, serializer):
        loan = self.get_loan()
        installment = get_object_or_404(
            LoanInstallment.objects.select_for_update().filter(loan=loan),
            number=serializer.validated_data["installment_number"],
        )
        amount = serializer.validated_data["amount"]
        remaining_amount = installment.remaining_amount
        if amount > remaining_amount:
            raise serializers.ValidationError(
                {"amount": f"O valor não pode exceder o saldo da parcela (R$ {remaining_amount})."}
            )

        paid_at = serializer.validated_data.get("paid_at") or timezone.now()
        discount_amount = Decimal("0.00")
        if amount < remaining_amount:
            if timezone.localtime(paid_at).date() >= installment.due_date:
                raise serializers.ValidationError(
                    {
                        "amount": (
                            "Pagamento parcial não permitido após o vencimento. "
                            "Antes do vencimento, o valor informado quita a parcela "
                            "com desconto."
                        )
                    }
                )
            discount_amount = remaining_amount - amount

        interest_paid = installment.payments.aggregate(total=Sum("interest_portion"))["total"]
        interest_remaining = max(
            installment.interest_amount - (interest_paid or Decimal("0.00")),
            Decimal("0.00"),
        )
        interest_portion = min(amount, interest_remaining)
        principal_portion = amount - interest_portion
        expense = Transaction.objects.create(
            user=self.request.user,
            type=Type.EXPENSE,
            amount=amount,
            bank=serializer.validated_data.get("bank", loan.bank),
            category="Pagamento de empréstimo",
            description=f"Pagamento da parcela {installment.number} do empréstimo {loan.pk}",
            occurred_at=paid_at,
        )
        serializer.save(
            installment=installment,
            paid_at=paid_at,
            discount_amount=discount_amount,
            interest_portion=interest_portion,
            principal_portion=principal_portion,
            expense_transaction=expense,
        )

    get = ListModelMixin.list
    post = CreateModelMixin.create
