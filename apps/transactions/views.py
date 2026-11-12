from django_filters import rest_framework as filters
from rest_framework import generics
from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)

from apps.transactions.models import Transaction
from apps.transactions.serializers import TransactionSerializer


class TransactionFilter(filters.FilterSet):
    type_bank = filters.ChoiceFilter(field_name="bank", choices=Transaction.Bank.choices)

    class Meta:
        model = Transaction
        fields = ["bank", "category", "occurred_at"]


class AllTransactionFilter(TransactionFilter):
    class Meta(TransactionFilter.Meta):
        fields = ["type", "bank", "category", "occurred_at"]


class TransactionQuerysetMixin:
    transaction_type = None

    def get_queryset(self):
        return Transaction.objects.filter(
            user=self.request.user,
            type=self.transaction_type,
        )


class TransactionCreateMixin:
    transaction_type = None

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, type=self.transaction_type)


class ListTransactions(generics.ListAPIView):
    serializer_class = TransactionSerializer
    filterset_class = AllTransactionFilter
    ordering_fields = ["occurred_at", "amount", "created_at"]
    ordering = ["-occurred_at", "-created_at"]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)


class ListIncome(TransactionQuerysetMixin, generics.ListAPIView):
    serializer_class = TransactionSerializer
    transaction_type = Transaction.Type.INCOME
    filterset_class = TransactionFilter
    ordering_fields = ["occurred_at", "amount", "created_at"]
    ordering = ["-occurred_at", "-created_at"]


class CreateIncome(TransactionCreateMixin, generics.CreateAPIView):
    serializer_class = TransactionSerializer
    transaction_type = Transaction.Type.INCOME


class DetailIncome(TransactionQuerysetMixin, generics.RetrieveAPIView):
    serializer_class = TransactionSerializer
    transaction_type = Transaction.Type.INCOME


class UpdateIncome(TransactionQuerysetMixin, generics.UpdateAPIView):
    serializer_class = TransactionSerializer
    transaction_type = Transaction.Type.INCOME


class DeleteIncome(TransactionQuerysetMixin, generics.DestroyAPIView):
    serializer_class = TransactionSerializer
    transaction_type = Transaction.Type.INCOME


class IncomeCollectionView(ListIncome, CreateIncome):
    get = ListModelMixin.list
    post = CreateModelMixin.create


class IncomeDetailView(DetailIncome, UpdateIncome, DeleteIncome):
    get = RetrieveModelMixin.retrieve
    put = UpdateModelMixin.update
    patch = UpdateModelMixin.partial_update
    delete = DestroyModelMixin.destroy


class ListExpense(TransactionQuerysetMixin, generics.ListAPIView):
    serializer_class = TransactionSerializer
    transaction_type = Transaction.Type.EXPENSE
    filterset_class = TransactionFilter
    ordering_fields = ["occurred_at", "amount", "created_at"]
    ordering = ["-occurred_at", "-created_at"]


class CreateExpense(TransactionCreateMixin, generics.CreateAPIView):
    serializer_class = TransactionSerializer
    transaction_type = Transaction.Type.EXPENSE


class DetailExpense(TransactionQuerysetMixin, generics.RetrieveAPIView):
    serializer_class = TransactionSerializer
    transaction_type = Transaction.Type.EXPENSE


class UpdateExpense(TransactionQuerysetMixin, generics.UpdateAPIView):
    serializer_class = TransactionSerializer
    transaction_type = Transaction.Type.EXPENSE


class DeleteExpense(TransactionQuerysetMixin, generics.DestroyAPIView):
    serializer_class = TransactionSerializer
    transaction_type = Transaction.Type.EXPENSE


class ExpenseCollectionView(ListExpense, CreateExpense):
    get = ListModelMixin.list
    post = CreateModelMixin.create


class ExpenseDetailView(DetailExpense, UpdateExpense, DeleteExpense):
    get = RetrieveModelMixin.retrieve
    put = UpdateModelMixin.update
    patch = UpdateModelMixin.partial_update
    delete = DestroyModelMixin.destroy
