# Django imports
from django.db import transaction
from django_filters import rest_framework as filters
from rest_framework import generics, serializers

# App imports
from apps.monthlies.invoices import validate_open_invoice
from apps.monthlies.models import Monthly
from apps.transactions.models import Transaction
from apps.transactions.serializers import TransactionSerializer

# Core imports
from core.enums import Bank


# Filter responsible for filtering transactions by type, bank, category, and occurrence date
class TransactionFilter(filters.FilterSet):
    type_bank = filters.ChoiceFilter(field_name="bank", choices=Bank.choices)
    invoice = filters.UUIDFilter(field_name="invoice_id")
    invoice_month = filters.DateFilter(input_formats=["%Y-%m"])

    class Meta:
        model = Transaction
        fields = ["type", "bank", "category", "occurred_at", "invoice", "invoice_month"]


# API view responsible for listing the authenticated user's transactions
class TransactionList(generics.ListAPIView):
    queryset = Transaction.objects.none()
    serializer_class = TransactionSerializer
    filterset_class = TransactionFilter
    ordering_fields = ["occurred_at", "amount", "created_at"]
    ordering = ["-occurred_at", "-created_at"]

    def get_queryset(self):
        queryset = Transaction.objects.filter(user=self.request.user)
        if not self.request.query_params.get("invoice"):
            queryset = queryset.filter(invoice__isnull=True)
        return queryset


# API view responsible for creating new transactions
class TransactionCreate(generics.CreateAPIView):
    serializer_class = TransactionSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# API view responsible for retrieving a specific transaction
class TransactionDetail(generics.RetrieveAPIView):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)


# API view responsible for updating an existing transaction
class TransactionUpdate(generics.UpdateAPIView):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).select_for_update()

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)


# API view responsible for deleting an existing transaction
class TransactionDelete(generics.DestroyAPIView):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).select_for_update()

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if instance.monthly_settlement_id:
            raise serializers.ValidationError(
                "Este lançamento foi gerado pela baixa da mensalidade."
            )
        if instance.invoice_id:
            invoice = Monthly.objects.select_for_update().get(pk=instance.invoice_id)
            validate_open_invoice(invoice, instance.invoice_month)
        super().perform_destroy(instance)
